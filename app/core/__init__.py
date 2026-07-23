"""Модуль core — основные компоненты сервиса распознавания речи."""

from .config import AppConfig
from .registry import register_model, discover_transcribers, get_transcriber_class
from .base import Transcriber


def create_transcriber(config: AppConfig) -> Transcriber:
    """
    Создание транскрайбера на основе типа модели в конфигурации.
    Использует registry-паттерн — модели регистрируются через @register_model.

    Args:
        config: Типизированная конфигурация приложения.

    Returns:
        Экземпляр транскрайбера.

    Raises:
        ValueError: Если указан неизвестный тип модели.
    """
    discover_transcribers()

    cls = get_transcriber_class(config.model_type)
    if cls is None:
        from .registry import get_registered_model_types
        available = ", ".join(get_registered_model_types())
        raise ValueError(f"Неизвестный тип модели: {config.model_type}. Доступные: {available}")

    return cls(config)
