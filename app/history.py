"""
Модуль history.py — сохранение истории транскрибации в JSON-файлы.
"""

import os
import json
import shutil
import datetime
import random
import string
import threading
from typing import Dict, Any, Optional
import logging

from .core.config import AppConfig

logger = logging.getLogger('app.history')

_history_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "history")

_cleanup_lock = threading.Lock()
_cleanup_counter = 0
_CLEANUP_INTERVAL = 100


def save_history(result: Dict[str, Any], original_filename: str, config: AppConfig) -> Optional[str]:
    """
    Сохраняет результат транскрибации в файл истории.

    Args:
        result: Результат транскрибации.
        original_filename: Исходное имя аудиофайла.
        config: Типизированная конфигурация.

    Returns:
        Путь к сохранённому файлу или None.
    """
    if not config.enable_history:
        return None

    try:
        os.makedirs(_history_root, exist_ok=True)

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        timestamp_ms = int(now.timestamp() * 1000)
        random_tag = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        base_filename = os.path.basename(original_filename)

        date_dir = os.path.join(_history_root, date_str)
        os.makedirs(date_dir, exist_ok=True)

        history_path = os.path.join(date_dir, f"{timestamp_ms}_{base_filename}_{random_tag}.json")

        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info("Результат сохранён в историю: %s", history_path)

        should_cleanup = False
        with _cleanup_lock:
            global _cleanup_counter
            _cleanup_counter += 1
            if _cleanup_counter >= _CLEANUP_INTERVAL:
                _cleanup_counter = 0
                should_cleanup = True

        if should_cleanup:
            _cleanup_old_history(config)

        return history_path

    except Exception as e:
        logger.error("Ошибка при сохранении истории: %s", e)
        return None


def _cleanup_old_history(config: AppConfig) -> None:
    """
    Удаляет директории истории старше max_history_days дней.

    Args:
        config: Типизированная конфигурация.
    """
    max_days = config.max_history_days
    if max_days <= 0:
        return

    cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=max_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    try:
        for entry in os.listdir(_history_root):
            entry_path = os.path.join(_history_root, entry)
            if not os.path.isdir(entry_path):
                continue
            if len(entry) == 10 and entry < cutoff_str:
                shutil.rmtree(entry_path, ignore_errors=True)
                logger.info("Удалена старая директория истории: %s", entry)
    except Exception as e:
        logger.warning("Ошибка при очистке старой истории: %s", e)
