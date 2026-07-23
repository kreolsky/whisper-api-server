"""Тестовый набор для nnp-whisper-api-server."""

import json
import os
import time
import tempfile
from dataclasses import asdict
from unittest.mock import patch, MagicMock

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
        from app.core.config import load_config
        from app.core import create_transcriber

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
        from app.history import save_history, _history_root

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
            model={"language": "ru"},
            return_timestamps=return_timestamps,
            enable_history=False,
        )
        return TranscriptionService(transcriber, config)

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
            model={},
            enable_history=False,
        )
        service = TranscriptionService(transcriber, config)
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
            model={},
            return_timestamps=True,
            enable_history=False,
        )
        service = TranscriptionService(transcriber, config)
        response, status = service.transcribe("/fake.wav", "test.wav", {"return_timestamps": "true"})
        assert status == 200
        assert "segments" in response
        assert response["model"] == "gigaam"
