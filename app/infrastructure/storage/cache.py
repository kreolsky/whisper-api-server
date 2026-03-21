"""
Модуль cache.py содержит функции для кэширования данных.
"""

import time
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger('app.cache')


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


# Глобальный экземпляр кэша
model_cache = SimpleCache(ttl=3600)  # Кэш для метаданных модели (1 час)