"""
Модуль cache.py содержит функции для кэширования данных.
"""

import time
from typing import Dict, Any, Optional, Callable
from functools import wraps
from .utils import logger


class SimpleCache:
    """
    Простой кэш на основе словаря с поддержкой TTL (Time To Live).
    
    Attributes:
        cache (Dict): Словарь для хранения кэшированных данных.
        ttl (int): Время жизни кэша в секундах.
    """
    
    def __init__(self, ttl: int = 300):
        """
        Инициализация кэша.
        
        Args:
            ttl: Время жизни кэша в секундах (по умолчанию 5 минут).
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """
        Получение значения из кэша.
        
        Args:
            key: Ключ для получения значения.
            
        Returns:
            Кэшированное значение или None, если ключ не найден или срок действия истек.
        """
        if key in self.cache:
            item = self.cache[key]
            if time.time() - item["timestamp"] < self.ttl:
                logger.debug(f"Кэш hit для ключа: {key}")
                return item["value"]
            else:
                # Удаление просроченного элемента
                del self.cache[key]
                logger.debug(f"Кэш expired для ключа: {key}")
        
        logger.debug(f"Кэш miss для ключа: {key}")
        return None
    
    def set(self, key: str, value: Any) -> None:
        """
        Установка значения в кэш.
        
        Args:
            key: Ключ для хранения значения.
            value: Значение для кэширования.
        """
        self.cache[key] = {
            "value": value,
            "timestamp": time.time()
        }
        logger.debug(f"Значение кэшировано для ключа: {key}")
    
    def clear(self) -> None:
        """
        Очистка кэша.
        """
        self.cache.clear()
        logger.debug("Кэш очищен")
    
    def delete(self, key: str) -> bool:
        """
        Удаление значения из кэша.
        
        Args:
            key: Ключ для удаления.
            
        Returns:
            True, если ключ был удален, иначе False.
        """
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Значение удалено из кэша для ключа: {key}")
            return True
        return False


# Глобальные экземпляры кэша
model_cache = SimpleCache(ttl=3600)  # Кэш для метаданных модели (1 час)
config_cache = SimpleCache(ttl=300)   # Кэш для конфигурации (5 минут)


def cache_result(cache_instance: SimpleCache, key_prefix: str = ""):
    """
    Декоратор для кэширования результатов функции.
    
    Args:
        cache_instance: Экземпляр кэша.
        key_prefix: Префикс для ключа кэша.
        
    Returns:
        Декорированная функция.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Генерация ключа кэша на основе имени функции и аргументов
            cache_key = f"{key_prefix}{func.__name__}_{str(args)}_{str(kwargs)}"
            
            # Попытка получить результат из кэша
            cached_result = cache_instance.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Если результат не в кэше, вызываем функцию
            result = func(*args, **kwargs)
            
            # Сохраняем результат в кэш
            cache_instance.set(cache_key, result)
            
            return result
        return wrapper
    return decorator