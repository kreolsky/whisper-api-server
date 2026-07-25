"""
Модуль model_manager.py — хранит загруженные транскрайберы и маршрутизирует
запросы по имени модели.

Множество одновременно доступных моделей, GPU каждой и модель по умолчанию
задаются в config.json (loaded_models, device_id, model_type). Менеджер жадно
грузит все модели при старте. Ошибка загрузки одной модели (напр. OOM на занятой
GPU) не укладывает сервис: проблемная модель пропускается (graceful degradation),
а fail-fast срабатывает только если не загрузилась ни одна модель.
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
        self._failed: Dict[str, str] = {}

        for name in config.loaded_models:
            model_start = time.time()
            logger.info("Загрузка модели '%s' (config.loaded_models)", name)
            try:
                transcriber = create_transcriber(config.for_model(name))
            except Exception as e:
                # Graceful degradation: одна неудачная загрузка (напр. OOM на
                # занятой co-tenant'ом GPU) не должна укладывать весь сервис и
                # здоровую default-модель. Пропускаем; fail-fast — только если
                # в итоге не загрузилось ни одной модели.
                logger.error("Не удалось загрузить модель '%s': %s — пропуск", name, e)
                self._failed[name] = str(e)
                continue
            self._transcribers[name] = transcriber
            logger.info(
                "Модель '%s' загружена за %.2fs", name, time.time() - model_start,
            )

        if not self._transcribers:
            raise RuntimeError(
                "Не удалось загрузить ни одну модель из loaded_models="
                + repr(config.loaded_models)
            )

        if config.model_type not in self._transcribers:
            logger.error(
                "Модель по умолчанию '%s' не загрузилась — default переключён на '%s'",
                config.model_type, self.default_name,
            )

        logger.info(
            "ModelManager готов: загружено моделей — %d, по умолчанию — '%s', "
            "пропущено — %s",
            len(self._transcribers), self.default_name,
            ", ".join(self._failed) if self._failed else "нет",
        )

    @property
    def default_name(self) -> str:
        """Имя модели по умолчанию (для запросов без параметра model).

        Если заявленная default-модель (config.model_type) не загрузилась —
        откат на первую доступную загруженную модель.
        """
        if self.config.model_type in self._transcribers:
            return self.config.model_type
        return next(iter(self._transcribers))

    @property
    def is_ready(self) -> bool:
        """Готовы ли загруженные модели.

        Хотя бы одна модель загружена и все загруженные готовы. При graceful
        degradation это означает: процесс поднялся с рабочим набором моделей.
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
            "Модель '%s' недоступна или неизвестна (нет среди загруженных) — "
            "используется модель по умолчанию '%s'",
            requested, self.default_name,
        )
        name = self.default_name
        return name, self._transcribers[name]
