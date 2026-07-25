"""
Модуль config.py — типизированная конфигурация приложения.
Все дефолты централизованы в dataclass-определениях.
"""

import dataclasses
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger('app.config')


_DEFAULT_EXTENSIONS = [
    ".wav", ".mp3", ".ogg", ".flac", ".m4a", ".oga", ".aac", ".webm", ".3gp", ".opus"
]
_DEFAULT_MIME_TYPES = [
    "audio/wav", "audio/mpeg", "audio/ogg", "audio/flac", "audio/mp4",
    "audio/aac", "audio/webm", "audio/opus"
]
_DEFAULT_EXCLUDE_ENDPOINTS = ["/health", "/static"]


@dataclass
class FileValidationConfig:
    max_file_size_mb: int = 100
    allowed_extensions: List[str] = field(default_factory=lambda: list(_DEFAULT_EXTENSIONS))
    allowed_mime_types: List[str] = field(default_factory=lambda: list(_DEFAULT_MIME_TYPES))


@dataclass
class RequestLoggingConfig:
    exclude_endpoints: List[str] = field(default_factory=lambda: list(_DEFAULT_EXCLUDE_ENDPOINTS))


@dataclass
class AppConfig:
    model_type: str = "whisper"
    models: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    model: Dict[str, Any] = field(default_factory=dict)
    loaded_models: List[str] = field(default_factory=list)
    service_port: int = 5042
    return_timestamps: bool = False
    audio_rate: int = 16000
    enable_history: bool = True
    max_history_days: int = 30
    max_concurrent_inference: int = 1
    shutdown_timeout_s: int = 30
    transcription_timeout_s: int = 300
    channel_timeout_s: int = 300
    file_validation: FileValidationConfig = field(default_factory=FileValidationConfig)
    log_level: str = "INFO"
    log_file: str = "logs/whisper_api.log"
    request_logging: RequestLoggingConfig = field(default_factory=RequestLoggingConfig)
    version: str = "1.0.0"
    longform_threshold_s: float = 25.0

    def for_model(self, name: str) -> "AppConfig":
        """Возвращает копию конфига с активной моделью name.

        Транскрайберы читают config.model / config.model_type — этот метод подменяет
        их так, чтобы один экземпляр GigaAMTranscriber загружал именно указанную
        модель. Словарь models разделяется по ссылке (поверхностная копия),
        поэтому транскрайберы обязаны относиться к конфигу как к read-only.
        """
        return dataclasses.replace(
            self,
            model_type=name,
            model=dict(self.models.get(name, {})),
        )


_PUBLIC_CONFIG_KEYS = frozenset({
    "model_type", "loaded_models", "version", "service_port", "return_timestamps",
    "audio_rate", "enable_history", "max_history_days",
    "max_concurrent_inference", "log_level",
})


def load_config(config_path: str) -> AppConfig:
    """
    Загружает конфигурацию из JSON-файла и возвращает типизированный AppConfig.

    Args:
        config_path: Путь к файлу конфигурации.

    Returns:
        Экземпляр AppConfig.

    Raises:
        FileNotFoundError: Если файл конфигурации не найден.
        json.JSONDecodeError: Если файл содержит некорректный JSON.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw: Dict[str, Any] = json.load(f)

        model_type = raw.get("model_type", "whisper")
        models = raw.get("models", {})
        model_config = models.get(model_type, {})
        if not model_config:
            logger.warning("Секция models.%s пуста или отсутствует", model_type)

        # Модель по умолчанию обязательна — без неё сервис бесполезен.
        if model_type not in models:
            raise ValueError(
                f"Модель по умолчанию '{model_type}' отсутствует в секции models"
            )

        # Список одновременно загружаемых моделей. Если ключа нет — ведём себя как
        # раньше: одна модель (модель по умолчанию).
        loaded_models = raw.get("loaded_models") or [model_type]

        # Модель по умолчанию обязана быть в loaded_models — добавляем в начало.
        if model_type not in loaded_models:
            loaded_models.insert(0, model_type)

        # Каждое имя должно иметь секцию models.<name>; иначе пропускаем с ошибкой.
        valid_models: List[str] = []
        for name in loaded_models:
            if name in models:
                valid_models.append(name)
            else:
                logger.error(
                    "Модель '%s' указана в loaded_models, но секция models.%s "
                    "отсутствует — пропуск", name, name,
                )
        loaded_models = valid_models

        fv = raw.get("file_validation", {})
        file_validation = FileValidationConfig(
            max_file_size_mb=fv.get("max_file_size_mb", 100),
            allowed_extensions=fv.get("allowed_extensions", list(_DEFAULT_EXTENSIONS)),
            allowed_mime_types=fv.get("allowed_mime_types", list(_DEFAULT_MIME_TYPES)),
        )

        rl = raw.get("request_logging", {})
        request_logging = RequestLoggingConfig(
            exclude_endpoints=rl.get("exclude_endpoints", list(_DEFAULT_EXCLUDE_ENDPOINTS)),
        )

        config = AppConfig(
            model_type=model_type,
            models=models,
            model=dict(model_config),
            loaded_models=loaded_models,
            service_port=raw.get("service_port", AppConfig.service_port),
            return_timestamps=raw.get("return_timestamps", AppConfig.return_timestamps),
            audio_rate=raw.get("audio_rate", AppConfig.audio_rate),
            enable_history=raw.get("enable_history", AppConfig.enable_history),
            max_history_days=raw.get("max_history_days", AppConfig.max_history_days),
            max_concurrent_inference=raw.get("max_concurrent_inference", AppConfig.max_concurrent_inference),
            shutdown_timeout_s=raw.get("shutdown_timeout_s", AppConfig.shutdown_timeout_s),
            transcription_timeout_s=raw.get("transcription_timeout_s", AppConfig.transcription_timeout_s),
            channel_timeout_s=raw.get("channel_timeout_s", AppConfig.channel_timeout_s),
            file_validation=file_validation,
            log_level=raw.get("log_level", AppConfig.log_level),
            log_file=raw.get("log_file", AppConfig.log_file),
            request_logging=request_logging,
            version=raw.get("version", AppConfig.version),
            longform_threshold_s=raw.get("longform_threshold_s", AppConfig.longform_threshold_s),
        )

        logger.info("Конфигурация загружена из %s (model_type=%s)", config_path, model_type)
        return config

    except FileNotFoundError as e:
        logger.error("Файл конфигурации не найден: %s", e)
        raise
    except json.JSONDecodeError as e:
        logger.error("Ошибка при загрузке конфигурации: %s", e)
        raise


def config_to_public_dict(config: AppConfig) -> Dict[str, Any]:
    """Возвращает словарь с безопасными для публичного API ключами."""
    return {k: getattr(config, k) for k in _PUBLIC_CONFIG_KEYS}
