"""
Модуль validation.py содержит классы и функции для валидации входных данных.
"""

import os
import magic
from typing import Dict, List
import logging

# Получаем логгер из централизованной настройки
logger = logging.getLogger('app.validators')


class ValidationError(Exception):
    """Исключение для ошибок валидации."""
    pass


# Маппинг MIME-типов контейнерных форматов: video/* → audio/* эквивалент
_MIME_EQUIVALENTS = {
    "video/webm": "audio/webm",
    "video/ogg": "audio/ogg",
    "video/mp4": "audio/mp4",
}


class FileValidator:
    """
    Класс для валидации файлов.
    
    Проверяет тип файла, размер и другие параметры на основе конфигурации.
    """
    
    def __init__(self, config: Dict):
        """
        Инициализация валидатора файлов.
        
        Args:
            config: Словарь с параметрами конфигурации.
        """
        self.validation_config = config.get("file_validation", {})
        self.max_file_size_mb = self.validation_config.get("max_file_size_mb", 100)
        self.allowed_extensions = self.validation_config.get("allowed_extensions", 
                                                             [".wav", ".mp3", ".ogg", ".flac", ".m4a"])
        self.allowed_mime_types = self.validation_config.get("allowed_mime_types", 
                                                            ["audio/wav", "audio/mpeg", "audio/ogg", 
                                                             "audio/flac", "audio/mp4"])
    
    def _validate_file_extension(self, filename: str) -> None:
        """
        Валидирует расширение файла.
        
        Args:
            filename: Имя файла.
            
        Raises:
            ValidationError: Если расширение файла не входит в список разрешенных.
        """
        if not any(filename.lower().endswith(ext.lower()) for ext in self.allowed_extensions):
            # Логирование попытки загрузки файла с неразрешенным расширением
            file_extension = os.path.splitext(filename)[1]
            logger.warning("Попытка загрузки файла с неразрешенным расширением '%s'. "
                          "Имя файла: %s. Разрешенные расширения: %s", file_extension, filename, ", ".join(self.allowed_extensions))
            
            raise ValidationError(f"Расширение файла не разрешено. "
                                 f"Разрешенные расширения: {', '.join(self.allowed_extensions)}")
    
    def validate_file_by_path(self, file_path: str, filename: str) -> bool:
        """
        Валидирует файл по пути на диске.

        Args:
            file_path: Путь к файлу.
            filename: Имя файла (для проверки расширения).

        Returns:
            True, если файл прошел валидацию.

        Raises:
            ValidationError: Если файл не прошел валидацию.
        """
        # Проверка расширения
        self._validate_file_extension(filename)

        # Проверка размера
        file_size = os.path.getsize(file_path)
        max_size_bytes = self.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise ValidationError(f"Размер файла ({file_size / (1024*1024):.2f} МБ) "
                                 f"превышает максимально допустимый ({self.max_file_size_mb} МБ)")

        # Проверка MIME-типа
        try:
            mime_type = magic.from_file(file_path, mime=True)
            normalized = _MIME_EQUIVALENTS.get(mime_type, mime_type)
            if normalized not in self.allowed_mime_types:
                raise ValidationError(f"MIME-тип файла ({mime_type}) не разрешен. "
                                     f"Разрешенные MIME-типы: {', '.join(self.allowed_mime_types)}")
        except ValidationError:
            raise
        except Exception as e:
            logger.warning("Не удалось определить MIME-тип файла: %s", e)

        return True
