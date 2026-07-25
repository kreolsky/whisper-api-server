"""
Модуль model_manager.py — хранит загруженные транскрайберы и маршрутизирует
запросы по имени модели.

Множество одновременно доступных моделей, GPU каждой и модель по умолчанию
задаются в config.json (loaded_models, device_id, model_type). Менеджер жадно
грузит все модели при старте и при ошибке любой из них падает (fail fast) — как
и прежнее поведение с одной моделью.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

from .base import Transcriber
from .config import AppConfig

logger = logging.getLogger('app.model_manager')


class ModelManager:
    """Хранит загруженные транскрайберы и маршрутизирует запросы по имени модели."""

    def __init__(self, config: AppConfig):
        # Импорт внутри метода, чтобы избежать цикла: create_transcriber живёт в
        # app.core.__init__, который сам импортирует ModelManager.
        from . import create_transcriber

        self.config = config
        self._transcribers: Dict[str, Transcriber] = {}

        for name in config.loaded_models:
            model_start = time.time()
            logger.info("Загрузка модели '%s' (config.loaded_models)", name)
            try:
                transcriber = create_transcriber(config.for_model(name))
            except Exception as e:
                logger.error("Не удалось загрузить модель '%s': %s", name, e)
                raise
            self._transcribers[name] = transcriber
            logger.info(
                "Модель '%s' загружена за %.2fs", name, time.time() - model_start,
            )

        logger.info(
            "ModelManager готов: загружено моделей — %d, по умолчанию — '%s'",
            len(self._transcribers), self.default_name,
        )

    @property
    def default_name(self) -> str:
        """Имя модели по умолчанию (для запросов без параметра model)."""
        return self.config.model_type

    @property
    def is_ready(self) -> bool:
        """Готовы ли все загруженные модели.

        Структурный инвариант: загрузка жадная и падает при ошибке, поэтому поле
        равно True, как только процесс поднялся. Служит лишь защитной проверкой.
        """
        return bool(self._transcribers) and all(
            t.is_ready for t in self._transcribers.values()
        )

    def available(self) -> List[str]:
        """Имена загруженных моделей."""
        return list(self._transcribers.keys())

    def resolve(self, requested: Optional[str]) -> Tuple[str, Transcriber]:
        """Разрешает запрошенное имя модели в (имя, транскрайбер).

        - None/пустая строка → модель по умолчанию.
        - Точное совпадение среди загруженных → эта модель.
        - Иначе → модель по умолчанию + предупреждение в логе (не 400, чтобы не
          ломать OpenAI SDK / UI, шлющие model='whisper-1').
        """
        if not requested:
            name = self.default_name
            return name, self._transcribers[name]

        if requested in self._transcribers:
            return requested, self._transcribers[requested]

        logger.warning(
            "Неизвестная модель '%s' — используется модель по умолчанию '%s'",
            requested, self.default_name,
        )
        name = self.default_name
        return name, self._transcribers[name]
