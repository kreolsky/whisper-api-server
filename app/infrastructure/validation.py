"""
Модуль validation.py — валидация входных данных (файлы, MIME-типы).
"""

import os
import magic
from typing import List
import logging

from ..core.config import AppConfig, FileValidationConfig

logger = logging.getLogger('app.validators')


class ValidationError(Exception):
    """Исключение для ошибок валидации."""
    pass


_MIME_EQUIVALENTS = {
    "audio/x-wav": "audio/wav",
    "audio/x-m4a": "audio/mp4",
    "audio/x-hx-aac-adts": "audio/aac",
    "video/webm": "audio/webm",
    "video/ogg": "audio/ogg",
    "video/mp4": "audio/mp4",
    "video/3gpp": "audio/mp4",
    "audio/opus": "audio/ogg",
}


class FileValidator:
    """
    Класс для валидации файлов.

    Проверяет тип файла, размер и другие параметры на основе конфигурации.
    """

    def __init__(self, config: AppConfig):
        """
        Инициализация валидатора файлов.

        Args:
            config: Типизированная конфигурация приложения.

        Raises:
            KeyError: Если в конфигурации отсутствуют обязательные ключи file_validation.
        """
        fv = config.file_validation
        if not fv.max_file_size_mb or not fv.allowed_extensions or not fv.allowed_mime_types:
            raise KeyError("В секции 'file_validation' отсутствуют обязательные ключи")

        self.max_file_size_mb = fv.max_file_size_mb
        self.allowed_extensions: List[str] = fv.allowed_extensions
        self.allowed_mime_types: List[str] = fv.allowed_mime_types

    def _validate_file_extension(self, filename: str) -> None:
        """
        Валидирует расширение файла.

        Args:
            filename: Имя файла.

        Returns:
            None при успешной валидации.

        Raises:
            ValidationError: Если расширение файла не входит в список разрешенных.
        """
        if not any(filename.lower().endswith(ext.lower()) for ext in self.allowed_extensions):
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
        self._validate_file_extension(filename)

        file_size = os.path.getsize(file_path)
        max_size_bytes = self.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise ValidationError(f"Размер файла ({file_size / (1024*1024):.2f} МБ) "
                                 f"превышает максимально допустимый ({self.max_file_size_mb} МБ)")

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
