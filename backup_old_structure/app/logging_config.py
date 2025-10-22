"""
Модуль logging_config.py содержит централизованную настройку логирования.
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_level=logging.INFO, log_file=None):
    """
    Настройка логирования для всего приложения.
    
    Args:
        log_level: Уровень логирования (по умолчанию INFO).
        log_file: Путь к файлу для записи логов (опционально).
    """
    # Создаем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Очищаем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Создаем улучшенный форматтер с поддержкой дополнительных полей
    class CustomFormatter(logging.Formatter):
        def format(self, record):
            # Добавляем поле type если оно отсутствует
            if not hasattr(record, 'type'):
                record.type = 'general'
            return super().format(record)
    
    formatter = CustomFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(type)s] %(message)s'
    )
    
    # Добавляем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Добавляем обработчик для записи в файл, если указан путь
    if log_file:
        # Создаем директорию для файла логов, если она не существует
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10 МБ
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Устанавливаем уровень логирования для логгеров в других модулях
    logging.getLogger('app').setLevel(log_level)
    logging.getLogger('app.request').setLevel(log_level)
    
    return root_logger