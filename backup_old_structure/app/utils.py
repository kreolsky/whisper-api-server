"""
Модуль utils.py содержит утилиты и вспомогательные функции.
"""

import logging
import functools
from flask import request

# Получаем логгер из централизованной настройки
logger = logging.getLogger('app.utils')


def log_invalid_file_request(func):
    """
    Декоратор для логирования запросов с невалидными файлами.
    
    Args:
        func: Декорируемая функция.
        
    Returns:
        Обернутая функция с логированием ошибок валидации файлов.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Получение информации о запросе
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
            endpoint = request.endpoint or 'unknown'
            method = request.method or 'unknown'
            
            # Получение имени файла из запроса
            filename = 'unknown'
            if 'file' in request.files:
                filename = request.files['file'].filename
            elif request.is_json:
                data = request.get_json()
                if data and 'file' in data:
                    filename = data.get('filename', 'base64_data')
            
            # Логирование обращения к API с невалидным файлом
            logger.warning(f"Обращение к эндпоинту {method} {endpoint} с невалидным файлом '{filename}' "
                          f"от клиента {client_ip}. Ошибка: {str(e)}")
            
            # Пробрасываем исключение дальше
            raise
    return wrapper
