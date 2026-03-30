"""
Модуль history.py — сохранение истории транскрибации в JSON-файлы.
"""

import os
import json
import shutil
import datetime
import random
import string
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger('app.history')

# Корневая директория истории (относительно корня проекта)
_history_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "history")


def save_history(result: Dict[str, Any], original_filename: str, config: Dict) -> Optional[str]:
    """
    Сохраняет результат транскрибации в файл истории.

    Args:
        result: Результат транскрибации.
        original_filename: Исходное имя аудиофайла.
        config: Конфигурация (проверяется enable_history).

    Returns:
        Путь к сохранённому файлу или None.
    """
    if not config.get("enable_history", False):
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
        _cleanup_old_history(config)
        return history_path

    except Exception as e:
        logger.error("Ошибка при сохранении истории: %s", e)
        return None


def _cleanup_old_history(config: Dict) -> None:
    """
    Удаляет директории истории старше max_history_days дней.

    Args:
        config: Конфигурация (проверяется max_history_days).
    """
    max_days = config.get("max_history_days", 30)
    if max_days <= 0:
        return

    cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=max_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    try:
        for entry in os.listdir(_history_root):
            entry_path = os.path.join(_history_root, entry)
            if not os.path.isdir(entry_path):
                continue
            # Директории имеют формат YYYY-MM-DD
            if len(entry) == 10 and entry < cutoff_str:
                shutil.rmtree(entry_path, ignore_errors=True)
                logger.info("Удалена старая директория истории: %s", entry)
    except Exception as e:
        logger.warning("Ошибка при очистке старой истории: %s", e)
