"""
Модуль history_logger.py содержит класс HistoryLogger для журналирования результатов
транскрибации.
"""

import os
import json
import datetime
import random
import string
from typing import Dict, Any, Optional

from .utils import logger

class HistoryLogger:
    """Класс для сохранения истории транскрибации."""
    
    def __init__(self, config: Dict):
        """
        Инициализация логгера истории.
        
        Args:
            config: Словарь с конфигурацией.
        """
        self.config = config
        self.history_enabled = config.get("enable_history", False)
        self.history_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "history")
        
        # Создаем корневую директорию истории, если она не существует
        if self.history_enabled and not os.path.exists(self.history_root):
            os.makedirs(self.history_root)
            logger.info(f"Создана директория для истории транскрибации: {self.history_root}")
    
    def save(self, result: Dict[str, Any], original_filename: str) -> Optional[str]:
        """
        Сохраняет результат транскрибации в файл истории.
        
        Args:
            result: Результат транскрибации.
            original_filename: Исходное имя аудиофайла.
            
        Returns:
            Путь к сохраненному файлу истории или None, если сохранение отключено.
        """
        if not self.history_enabled:
            logger.debug("История транскрибации отключена в конфигурации")
            return None
            
        try:
            # Получаем текущую дату и время
            now = datetime.datetime.now()
            date_str = now.strftime("%Y-%m-%d")

            # Получаем текущий таймстамп в миллисекундах
            timestamp_ms = int(datetime.datetime.now().timestamp() * 1000)
            
            # Генерируем 4-символьную случайную метку
            random_tag = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            
            # Получаем только имя файла без пути
            base_filename = os.path.basename(original_filename)
            
            # Создаем имя файла истории
            history_filename = f"{timestamp_ms}_{base_filename}_{random_tag}.json"
            
            # Путь к директории для текущей даты
            date_dir = os.path.join(self.history_root, date_str)
            
            # Создаем директорию для текущей даты, если она не существует
            if not os.path.exists(date_dir):
                os.makedirs(date_dir)
                
            # Полный путь к файлу истории
            history_path = os.path.join(date_dir, history_filename)
            
            # Сохраняем результат в JSON файл
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Результат транскрибации сохранен в историю: {history_path}")
            return history_path
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении истории транскрибации: {e}")
            return None
