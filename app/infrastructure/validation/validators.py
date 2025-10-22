"""
Модуль validators.py содержит классы и функции для валидации входных данных.
"""

import os
import magic
from typing import Dict, List, BinaryIO, Optional
import logging

# Получаем логгер из централизованной настройки
logger = logging.getLogger('app.validators')


class ValidationError(Exception):
    """Исключение для ошибок валидации."""
    pass


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
    
    def validate_file(self, file: BinaryIO, filename: str) -> bool:
        """
        Валидирует файл на основе конфигурации.
        
        Args:
            file: Файловый объект.
            filename: Имя файла.
            
        Returns:
            True, если файл прошел валидацию.
            
        Raises:
            ValidationError: Если файл не прошел валидацию.
        """
        try:
            # Проверка размера файла
            self._validate_file_size(file)
            
            # Проверка расширения файла
            self._validate_file_extension(filename)
            
            # Проверка MIME-типа файла
            self._validate_file_mime_type(file)
            
            return True
        except ValidationError as e:
            # Логирование общей ошибки валидации
            logger.warning(f"Ошибка валидации файла '{filename}': {str(e)}")
            raise
    
    def _validate_file_size(self, file: BinaryIO) -> None:
        """
        Валидирует размер файла.
        
        Args:
            file: Файловый объект.
            
        Raises:
            ValidationError: Если размер файла превышает максимально допустимый.
        """
        # Сохранение текущей позиции
        current_position = file.tell()
        
        # Переход в конец файла для определения размера
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        
        # Возврат к исходной позиции
        file.seek(current_position)
        
        max_size_bytes = self.max_file_size_mb * 1024 * 1024
        if file_length > max_size_bytes:
            logger.warning(f"Попытка загрузки файла размером {file_length / (1024*1024):.2f} МБ, "
                          f"что превышает максимально допустимый размер {self.max_file_size_mb} МБ")
            
            raise ValidationError(f"Размер файла ({file_length / (1024*1024):.2f} МБ) "
                                 f"превышает максимально допустимый ({self.max_file_size_mb} МБ)")
    
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
            logger.warning(f"Попытка загрузки файла с неразрешенным расширением '{file_extension}'. "
                          f"Имя файла: {filename}. Разрешенные расширения: {', '.join(self.allowed_extensions)}")
            
            raise ValidationError(f"Расширение файла не разрешено. "
                                 f"Разрешенные расширения: {', '.join(self.allowed_extensions)}")
    
    def _validate_file_mime_type(self, file: BinaryIO) -> None:
        """
        Валидирует MIME-тип файла.
        
        Args:
            file: Файловый объект.
            
        Raises:
            ValidationError: Если MIME-тип файла не входит в список разрешенных.
        """
        # Сохранение текущей позиции
        current_position = file.tell()
        
        try:
            # Чтение первых байтов для определения MIME-типа
            header = file.read(1024)
            mime_type = magic.from_buffer(header, mime=True)
            
            # Возврат к исходной позиции
            file.seek(current_position)
            
            if mime_type not in self.allowed_mime_types:
                # Логирование попытки загрузки файла с неразрешенным MIME-типом
                logger.warning(f"Попытка загрузки файла с неразрешенным MIME-типом '{mime_type}'. "
                              f"Разрешенные MIME-типы: {', '.join(self.allowed_mime_types)}")
                
                raise ValidationError(f"MIME-тип файла ({mime_type}) не разрешен. "
                                     f"Разрешенные MIME-типы: {', '.join(self.allowed_mime_types)}")
        except Exception as e:
            # Возврат к исходной позиции в случае ошибки
            file.seek(current_position)
            logger.warning(f"Не удалось определить MIME-тип файла: {e}")
            # Не прерываем валидацию, если не удалось определить MIME-тип
    
    @staticmethod
    def validate_local_file_path(file_path: str, allowed_directories: Optional[List[str]] = None) -> str:
        """
        Валидирует путь к локальному файлу для предотвращения атак обхода пути.
        
        Args:
            file_path: Путь к файлу.
            allowed_directories: Список разрешенных директорий.
            
        Returns:
            Нормализованный и проверенный путь к файлу.
            
        Raises:
            ValidationError: Если путь к файлу небезопасен.
        """
        # Нормализация пути
        normalized_path = os.path.normpath(file_path)
        
        # Если указаны разрешенные директории, проверяем, что путь находится в одной из них
        if allowed_directories:
            for allowed_dir in allowed_directories:
                full_allowed_path = os.path.abspath(allowed_dir)
                full_file_path = os.path.abspath(os.path.join(full_allowed_path, normalized_path))
                
                if full_file_path.startswith(full_allowed_path):
                    return full_file_path
            
            logger.warning(f"Попытка доступа к файлу вне разрешенных директорий: {file_path}")
            raise ValidationError("Путь к файлу не находится в разрешенных директориях")
        
        # Если разрешенные директории не указаны, просто возвращаем нормализованный путь
        return normalized_path