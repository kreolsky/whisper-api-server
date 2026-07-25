"""Тестовый набор для nnp-whisper-api-server."""

import json
import os
import tempfile
import time
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import AppConfig, FileValidationConfig, config_to_public_dict


def _make_config_dict(model_type="whisper", extra_model_keys=None, **overrides):
    """Создаёт тестовый словарь конфигурации."""
    config = {
        "model_type": model_type,
        "models": {
            "whisper": {
                "model_path": "/fake/whisper-model",
                "language": "ru",
                "chunk_length_s": 28,
                "batch_size": 6,
                "max_new_tokens": 384,
                "temperature": 0.01,
                "device_id": 0,
            },
            "gigaam": {
                "model_path": "/fake/gigaam-model",
                "variant": "v3_e2e_rnnt",
                "segmentation_model": "/fake/seg-model",
            },
        },
        "service_port": 5042,
        "return_timestamps": False,
        "enable_history": True,
    }
    if extra_model_keys:
        config["models"][model_type].update(extra_model_keys)
    config.update(overrides)
    return config


def _write_config(tmpdir, **kwargs):
    """Записывает тестовый конфиг в JSON-файл и возвращает путь."""
    config = _make_config_dict(**kwargs)
    path = os.path.join(tmpdir, "config.json")
    with open(path, "w") as f:
        json.dump(config, f)
    return path


def _make_manager(transcribers, config):
    """Собирает ModelManager без реальной загрузки моделей (bypass __init__).

    Транскрайберы — заглушки; config задаёт default_name (config.model_type) и
    список доступных моделей.
    """
    from app.core.model_manager import ModelManager

    mgr = ModelManager.__new__(ModelManager)
    mgr.config = config
    mgr._transcribers = dict(transcribers)
    return mgr


class TestConfig:
    """Тесты загрузки и структуры конфигурации."""

    def test_load_config_whisper(self, tmp_path):
        from app.core.config import load_config

        path = _write_config(str(tmp_path), model_type="whisper")
        config = load_config(path)

        assert isinstance(config, AppConfig)
        assert config.model_type == "whisper"
        assert config.model["model_path"] == "/fake/whisper-model"
        assert config.model["language"] == "ru"

    def test_load_config_gigaam(self, tmp_path):
        from app.core.config import load_config

        path = _write_config(str(tmp_path), model_type="gigaam")
        config = load_config(path)

        assert config.model_type == "gigaam"
        assert config.model["variant"] == "v3_e2e_rnnt"
        assert config.model["segmentation_model"] == "/fake/seg-model"

    def test_load_config_missing_file(self):
        from app.core.config import load_config

        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.json")

    def test_models_section_preserved(self, tmp_path):
        from app.core.config import load_config

        path = _write_config(str(tmp_path))
        config = load_config(path)

        assert "whisper" in config.models
        assert "gigaam" in config.models

    def test_service_keys(self, tmp_path):
        from app.core.config import load_config

        path = _write_config(str(tmp_path))
        config = load_config(path)

        assert config.service_port == 5042
        assert config.enable_history is True

    def test_defaults_applied(self, tmp_path):
        from app.core.config import load_config

        path = _write_config(str(tmp_path))
        config = load_config(path)

        assert config.shutdown_timeout_s == AppConfig.shutdown_timeout_s
        assert config.transcription_timeout_s == AppConfig.transcription_timeout_s
        assert config.version == AppConfig.version

    def test_public_dict_whitelist(self, tmp_path):
        from app.core.config import load_config

        path = _write_config(str(tmp_path))
        config = load_config(path)
        public = config_to_public_dict(config)

        assert "model_path" not in public
        assert "model" not in public
        assert "version" in public
        assert "model_type" in public


class TestRegistry:
    """Тесты registry-паттерна для моделей."""

    def test_discover_transcribers(self):
        from app.core.registry import discover_transcribers, get_registered_model_types

        discover_transcribers()
        types = get_registered_model_types()
        assert "whisper" in types
        assert "gigaam" in types

    def test_create_transcriber_unknown(self, tmp_path):
        from app.core import create_transcriber
        from app.core.config import load_config

        path = _write_config(str(tmp_path))
        config = load_config(path)
        config.model_type = "unknown_model"

        with pytest.raises(ValueError, match="Неизвестный тип модели"):
            create_transcriber(config)


class TestFileValidator:
    """Тесты валидатора файлов."""

    def _make_config(self) -> AppConfig:
        return AppConfig(
            file_validation=FileValidationConfig(
                max_file_size_mb=10,
                allowed_extensions=[".wav", ".mp3"],
                allowed_mime_types=["audio/wav", "audio/mpeg"],
            )
        )

    def test_valid_extension(self):
        from app.infrastructure.validation import FileValidator

        validator = FileValidator(self._make_config())
        assert validator._validate_file_extension("test.wav") is None
        assert validator._validate_file_extension("test.mp3") is None

    def test_invalid_extension(self):
        from app.infrastructure.validation import FileValidator, ValidationError

        validator = FileValidator(self._make_config())
        with pytest.raises(ValidationError, match="Расширение файла не разрешено"):
            validator._validate_file_extension("test.exe")

    def test_case_insensitive_extension(self):
        from app.infrastructure.validation import FileValidator

        validator = FileValidator(self._make_config())
        assert validator._validate_file_extension("test.WAV") is None

    def test_missing_file_validation_raises(self):
        from app.infrastructure.validation import FileValidator

        config = AppConfig(file_validation=FileValidationConfig(
            max_file_size_mb=0,
            allowed_extensions=[],
            allowed_mime_types=[],
        ))
        with pytest.raises(KeyError, match="file_validation"):
            FileValidator(config)


class TestHistory:
    """Тесты модуля истории."""

    def _make_config(self, enable=True, max_days=30) -> AppConfig:
        return AppConfig(enable_history=enable, max_history_days=max_days)

    def test_save_disabled(self, tmp_path):
        from app.history import save_history

        config = self._make_config(enable=False)
        result = save_history({"text": "hello"}, "test.wav", config)
        assert result is None

    def test_save_creates_file(self, tmp_path):
        from app.history import _history_root, save_history

        config = self._make_config()
        with patch("app.history._history_root", str(tmp_path)):
            result = save_history({"text": "hello"}, "test.wav", config)

        assert result is not None
        assert os.path.exists(result)
        with open(result) as f:
            data = json.load(f)
        assert data["text"] == "hello"

    def test_cleanup_removes_old_dirs(self, tmp_path):
        import shutil
        from datetime import datetime, timedelta, timezone

        from app.history import _cleanup_old_history

        old_date = (datetime.now(tz=timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
        old_dir = os.path.join(str(tmp_path), old_date)
        os.makedirs(old_dir)
        with open(os.path.join(old_dir, "test.json"), "w") as f:
            f.write("{}")

        config = self._make_config(max_days=30)
        with patch("app.history._history_root", str(tmp_path)):
            _cleanup_old_history(config)

        assert not os.path.exists(old_dir)


class TestAsyncTaskManager:
    """Тесты менеджера асинхронных задач."""

    def test_run_task_success(self):
        from app.infrastructure.async_tasks import AsyncTaskManager

        manager = AsyncTaskManager()
        task_id = manager.run_task(lambda: "result")
        time.sleep(0.5)

        status = manager.get_task_status(task_id)
        assert status is not None
        assert status["status"] == "completed"
        assert status["result"] == "result"

    def test_run_task_failure(self):
        from app.infrastructure.async_tasks import AsyncTaskManager

        def _fail():
            raise RuntimeError("fail")

        manager = AsyncTaskManager()
        task_id = manager.run_task(_fail)
        time.sleep(0.5)

        status = manager.get_task_status(task_id)
        assert status is not None
        assert status["status"] == "failed"
        assert "fail" in status["error"]

    def test_get_nonexistent_task(self):
        from app.infrastructure.async_tasks import AsyncTaskManager

        manager = AsyncTaskManager()
        assert manager.get_task_status("nonexistent") is None

    def test_cleanup_old_tasks(self):
        from app.infrastructure.async_tasks import AsyncTaskManager

        manager = AsyncTaskManager()
        task_id = manager.run_task(lambda: "old")
        time.sleep(0.5)

        with manager._lock:
            manager.tasks[task_id]["completed_at"] = time.time() - 7200

        with manager._lock:
            manager._cleanup_old_tasks()

        assert manager.get_task_status(task_id) is None


class TestTranscriptionService:
    """Тесты сервиса транскрибации с mock-транскрайбером."""

    def _make_service(self, model_type="whisper", return_timestamps=False):
        from app.core.transcription_service import TranscriptionService

        transcriber = MagicMock()
        if return_timestamps:
            transcriber.process_file.return_value = (
                {"text": "hello", "segments": [{"start_time_ms": 0, "end_time_ms": 1000, "text": "hello"}]},
                5.0,
            )
        else:
            transcriber.process_file.return_value = ("hello", 5.0)

        config = AppConfig(
            model_type=model_type,
            models={model_type: {"language": "ru"}},
            model={"language": "ru"},
            loaded_models=[model_type],
            return_timestamps=return_timestamps,
            enable_history=False,
        )
        manager = _make_manager({model_type: transcriber}, config)
        return TranscriptionService(manager, config)

    def test_transcribe_success(self):
        service = self._make_service()
        response, status = service.transcribe("/fake.wav", "test.wav")
        assert status == 200
        assert response["text"] == "hello"
        assert response["model"] == "whisper"

    def test_transcribe_error(self):
        from app.core.transcription_service import TranscriptionService

        transcriber = MagicMock()
        transcriber.process_file.side_effect = RuntimeError("boom")
        config = AppConfig(
            model_type="whisper",
            models={"whisper": {}},
            model={},
            loaded_models=["whisper"],
            enable_history=False,
        )
        manager = _make_manager({"whisper": transcriber}, config)
        service = TranscriptionService(manager, config)
        response, status = service.transcribe("/fake.wav", "test.wav")
        assert status == 500
        assert "boom" in response["error"]

    def test_transcribe_with_timestamps(self):
        from app.core.transcription_service import TranscriptionService

        transcriber = MagicMock()
        transcriber.process_file.return_value = (
            {"text": "hello world", "segments": [{"start_time_ms": 0, "end_time_ms": 1000, "text": "hello"}]},
            3.0,
        )
        config = AppConfig(
            model_type="gigaam",
            models={"gigaam": {}},
            model={},
            loaded_models=["gigaam"],
            return_timestamps=True,
            enable_history=False,
        )
        manager = _make_manager({"gigaam": transcriber}, config)
        service = TranscriptionService(manager, config)
        response, status = service.transcribe("/fake.wav", "test.wav", {"return_timestamps": "true"})
        assert status == 200
        assert "segments" in response
        assert response["model"] == "gigaam"


class TestMultiModelConfig:
    """Тесты multi-model полей конфигурации и AppConfig.for_model."""

    def _make_raw(self, model_type="gigaam", models=None, loaded_models=None):
        raw = {
            "model_type": model_type,
            "models": models or {
                "gigaam": {"variant": "v3_e2e_rnnt"},
                "gigaam-multilingual": {"variant": "multilingual_large_ctc"},
            },
        }
        if loaded_models is not None:
            raw["loaded_models"] = loaded_models
        return raw

    def _write_raw(self, tmp_path, raw):
        from app.core.config import load_config

        path = os.path.join(str(tmp_path), "config.json")
        with open(path, "w") as f:
            json.dump(raw, f)
        return load_config(path)

    def test_loaded_models_defaults_to_model_type(self, tmp_path):
        raw = self._make_raw(model_type="gigaam")  # без loaded_models
        config = self._write_raw(tmp_path, raw)
        assert config.loaded_models == ["gigaam"]

    def test_loaded_models_prepends_model_type(self, tmp_path):
        raw = self._make_raw(
            model_type="gigaam",
            loaded_models=["gigaam-multilingual"],
        )
        config = self._write_raw(tmp_path, raw)
        # model_type дописан в начало, обе модели валидны.
        assert config.loaded_models == ["gigaam", "gigaam-multilingual"]

    def test_loaded_models_skips_entry_without_section(self, tmp_path, caplog):
        import logging as _logging

        raw = self._make_raw(
            model_type="gigaam",
            loaded_models=["gigaam", "ghost", "gigaam-multilingual"],
        )
        with caplog.at_level(_logging.ERROR, logger="app.config"):
            config = self._write_raw(tmp_path, raw)
        assert config.loaded_models == ["gigaam", "gigaam-multilingual"]
        assert any("ghost" in rec.getMessage() for rec in caplog.records)

    def test_missing_default_model_section_fails_fast(self, tmp_path):
        raw = {
            "model_type": "ghost",
            "models": {"gigaam": {"variant": "v3_e2e_rnnt"}},
        }
        with pytest.raises(ValueError, match="ghost"):
            self._write_raw(tmp_path, raw)

    def test_for_model_returns_independent_copy(self, tmp_path):
        raw = self._make_raw(model_type="gigaam")
        config = self._write_raw(tmp_path, raw)

        view = config.for_model("gigaam-multilingual")
        assert view is not config
        assert view.model_type == "gigaam-multilingual"
        assert view.model["variant"] == "multilingual_large_ctc"
        # Оригинал не изменился.
        assert config.model_type == "gigaam"
        # Словарь модели — независимая копия.
        view.model["mut"] = 1
        assert "mut" not in config.models["gigaam-multilingual"]


class TestModelManagerResolve:
    """Тесты маршрутизации ModelManager.resolve (без реальных моделей)."""

    def _make_manager(self):
        config = AppConfig(
            model_type="a",
            models={"a": {}, "b": {}},
            loaded_models=["a", "b"],
            enable_history=False,
        )
        stub_a = MagicMock(name="a")
        stub_b = MagicMock(name="b")
        return _make_manager({"a": stub_a, "b": stub_b}, config), stub_a, stub_b

    def test_resolve_none_returns_default(self):
        mgr, stub_a, _ = self._make_manager()
        name, t = mgr.resolve(None)
        assert name == "a"
        assert t is stub_a

    def test_resolve_empty_string_returns_default(self):
        mgr, stub_a, _ = self._make_manager()
        name, t = mgr.resolve("")
        assert name == "a"
        assert t is stub_a

    def test_resolve_exact_match(self):
        mgr, _, stub_b = self._make_manager()
        name, t = mgr.resolve("b")
        assert name == "b"
        assert t is stub_b

    def test_resolve_unknown_falls_back_with_warning(self, caplog):
        import logging as _logging

        mgr, stub_a, _ = self._make_manager()
        with caplog.at_level(_logging.WARNING, logger="app.model_manager"):
            name, t = mgr.resolve("whisper-1")
        assert name == "a"
        assert t is stub_a
        assert any("whisper-1" in rec.getMessage() for rec in caplog.records)

    def test_available_and_is_ready(self):
        mgr, stub_a, stub_b = self._make_manager()
        assert set(mgr.available()) == {"a", "b"}
        assert mgr.is_ready is True

    def test_is_ready_false_when_a_model_not_ready(self):
        config = AppConfig(
            model_type="a", models={"a": {}}, loaded_models=["a"], enable_history=False,
        )
        stub = MagicMock()
        stub.is_ready = False
        mgr = _make_manager({"a": stub}, config)
        assert mgr.is_ready is False


class TestTranscriptionServiceRouting:
    """Маршрутизация запроса на выбранную модель в TranscriptionService."""

    def test_params_model_hits_selected_stub(self):
        from app.core.transcription_service import TranscriptionService

        config = AppConfig(
            model_type="a",
            models={"a": {}, "b": {}},
            loaded_models=["a", "b"],
            enable_history=False,
        )
        stub_a = MagicMock()
        stub_a.process_file.return_value = ("from-a", 1.0)
        stub_b = MagicMock()
        stub_b.process_file.return_value = ("from-b", 2.0)
        manager = _make_manager({"a": stub_a, "b": stub_b}, config)

        service = TranscriptionService(manager, config)
        response, status = service.transcribe("/x.wav", "x.wav", {"model": "b"})

        assert status == 200
        assert response["model"] == "b"
        assert response["text"] == "from-b"
        stub_b.process_file.assert_called_once()
        stub_a.process_file.assert_not_called()

    def test_unknown_model_falls_back_to_default(self):
        from app.core.transcription_service import TranscriptionService

        config = AppConfig(
            model_type="a",
            models={"a": {}, "b": {}},
            loaded_models=["a", "b"],
            enable_history=False,
        )
        stub_a = MagicMock()
        stub_a.process_file.return_value = ("from-a", 1.0)
        stub_b = MagicMock()
        manager = _make_manager({"a": stub_a, "b": stub_b}, config)

        service = TranscriptionService(manager, config)
        response, status = service.transcribe("/x.wav", "x.wav", {"model": "whisper-1"})

        assert status == 200
        assert response["model"] == "a"
        stub_a.process_file.assert_called_once()
        stub_b.process_file.assert_not_called()


class TestResolveDevice:
    """Тесты app.core.device.resolve_device с замоканным torch.cuda."""

    def _patch_cuda(self, mock_torch, available=True, count=2):
        mock_torch.cuda.is_available.return_value = available
        mock_torch.cuda.device_count.return_value = count
        mock_torch.backends.mps.is_available.return_value = False
        # torch.device(...) возвращает переданную строку как есть.
        mock_torch.device.side_effect = lambda s: s
        return mock_torch

    def test_valid_device_id(self):
        from unittest.mock import patch

        from app.core import device as device_mod

        with patch.object(device_mod, "torch") as mock_torch:
            self._patch_cuda(mock_torch, available=True, count=2)
            assert device_mod.resolve_device({"device_id": 1}) == "cuda:1"

    def test_out_of_range_device_id_falls_back_to_zero(self, caplog):
        import logging as _logging
        from unittest.mock import patch

        from app.core import device as device_mod

        with patch.object(device_mod, "torch") as mock_torch:
            self._patch_cuda(mock_torch, available=True, count=2)
            with caplog.at_level(_logging.WARNING, logger="app.device"):
                assert device_mod.resolve_device({"device_id": 5}) == "cuda:0"
            assert any("недоступен" in r.getMessage() for r in caplog.records)

    def test_negative_device_id_falls_back_to_zero(self):
        from unittest.mock import patch

        from app.core import device as device_mod

        with patch.object(device_mod, "torch") as mock_torch:
            self._patch_cuda(mock_torch, available=True, count=2)
            assert device_mod.resolve_device({"device_id": -1}) == "cuda:0"

    def test_bool_device_id_falls_back_to_zero(self):
        from unittest.mock import patch

        from app.core import device as device_mod

        with patch.object(device_mod, "torch") as mock_torch:
            self._patch_cuda(mock_torch, available=True, count=2)
            assert device_mod.resolve_device({"device_id": True}) == "cuda:0"

    def test_non_int_device_id_falls_back_to_zero(self):
        from unittest.mock import patch

        from app.core import device as device_mod

        with patch.object(device_mod, "torch") as mock_torch:
            self._patch_cuda(mock_torch, available=True, count=2)
            assert device_mod.resolve_device({"device_id": "1"}) == "cuda:0"

    def test_no_cuda_falls_back_to_cpu(self):
        from unittest.mock import patch

        from app.core import device as device_mod

        with patch.object(device_mod, "torch") as mock_torch:
            self._patch_cuda(mock_torch, available=False, count=0)
            assert device_mod.resolve_device({}) == "cpu"
