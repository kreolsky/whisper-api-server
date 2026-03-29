"""
Модуль history.py — сохранение истории транскрибации в JSON-файлы.
"""

import os
import json
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

        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        timestamp_ms = int(now.timestamp() * 1000)
        random_tag = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        base_filename = os.path.basename(original_filename)

        date_dir = os.path.join(_history_root, date_str)
        os.makedirs(date_dir, exist_ok=True)

        history_path = os.path.join(date_dir, f"{timestamp_ms}_{base_filename}_{random_tag}.json")

        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"Результат сохранён в историю: {history_path}")
        return history_path

    except Exception as e:
        logger.error(f"Ошибка при сохранении истории: {e}")
        return None
