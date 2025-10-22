"""
Модуль audio_sources.py содержит абстрактный класс AudioSource и его конкретные реализации
для обработки различных источников аудиофайлов (загруженные файлы, URL, base64, локальные файлы).
"""

import os
import uuid
import tempfile
import base64
import requests
import abc
from typing import Dict, Tuple, Optional, BinaryIO

from .utils import logger

class AudioSource(abc.ABC):
    """Абстрактный класс для различных источников аудиофайлов.
    
    Определяет интерфейс для различных источников аудио и предоставляет общие
    методы для работы с аудиофайлами, такие как проверка размера файла.
    """
    
    def __init__(self, max_file_size_mb: int = 100):
        """
        Инициализация источника аудио.
        
        Args:
            max_file_size_mb: Максимальный размер файла в МБ.
        """
        self.max_file_size_mb = max_file_size_mb
        
    @abc.abstractmethod
    def get_audio_file(self) -> Tuple[Optional[BinaryIO], Optional[str], Optional[str]]:
        """
        Получает аудиофайл из источника.
        
        Returns:
            Кортеж (файловый объект, имя файла, сообщение об ошибке).
            В случае ошибки, возвращает (None, None, сообщение об ошибке).
        """
        pass
        
    def check_file_size(self, file: BinaryIO) -> Tuple[bool, Optional[str]]:
        """
        Проверяет размер файла.
        
        Args:
            file: Файловый объект для проверки.
            
        Returns:
            Кортеж (результат проверки, сообщение об ошибке).
            Если проверка пройдена, сообщение об ошибке будет None.
        """
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)  # Сброс указателя файла после проверки размера
        
        if file_length > self.max_file_size_mb * 1024 * 1024:
            return False, f"File exceeds maximum size of {self.max_file_size_mb}MB"
        
        return True, None


class FakeFile:
    """Имитирует файловый объект для унификации обработки из разных источников.
    
    Позволяет обрабатывать файлы из различных источников (локальный путь, URL, base64)
    как стандартные файловые объекты Flask, обеспечивая совместимость с существующей 
    логикой обработки файлов.
    """
    
    def __init__(self, file: BinaryIO, filename: str):
        """
        Инициализация объекта FakeFile.
        
        Args:
            file: Исходный файловый объект или поток.
            filename: Имя файла для метаданных.
        """
        self.file = file
        self.filename = filename

    def read(self):
        """Чтение содержимого файла."""
        return self.file.read()

    def seek(self, offset: int, whence: int = 0):
        """Перемещение позиции чтения."""
        self.file.seek(offset, whence)

    def tell(self):
        """Получение текущей позиции чтения."""
        return self.file.tell()

    def save(self, destination: str):
        """
        Сохраняет содержимое файла в указанное место назначения.
        
        Args:
            destination: Путь для сохранения файла.
        """
        with open(destination, 'wb') as f:
            content = self.file.read()
            f.write(content)
            self.file.seek(0)  # Сброс указателя после чтения

    @property
    def name(self):
        """Возвращает имя файла."""
        return self.filename


class UploadedFileSource(AudioSource):
    """Источник аудио для файлов, загруженных через HTTP-запрос."""
    
    def __init__(self, request_files, max_file_size_mb: int = 100):
        """
        Инициализация источника для загруженных файлов.
        
        Args:
            request_files: Объект request.files из Flask.
            max_file_size_mb: Максимальный размер файла в МБ.
        """
        super().__init__(max_file_size_mb)
        self.request_files = request_files
        
    def get_audio_file(self) -> Tuple[Optional[BinaryIO], Optional[str], Optional[str]]:
        """
        Получает аудиофайл из загруженных файлов.
        
        Returns:
            Кортеж (файловый объект, имя файла, сообщение об ошибке).
        """
        if 'file' not in self.request_files:
            return None, None, "No file part"
            
        file = self.request_files['file']
        
        if file.filename == '':
            return None, None, "No selected file"
            
        # Проверка размера файла
        is_valid, error_message = self.check_file_size(file)
        if not is_valid:
            return None, None, error_message
            
        return file, file.filename, None


class URLSource(AudioSource):
    """Источник аудио для файлов, доступных по URL."""
    
    def __init__(self, url: str, max_file_size_mb: int = 100):
        """
        Инициализация источника для файлов по URL.
        
        Args:
            url: URL аудиофайла.
            max_file_size_mb: Максимальный размер файла в МБ.
        """
        super().__init__(max_file_size_mb)
        self.url = url
        self.temp_file_path = None
        self.temp_dir = None
        
    def get_audio_file(self) -> Tuple[Optional[BinaryIO], Optional[str], Optional[str]]:
        """
        Получает аудиофайл по URL.
        
        Returns:
            Кортеж (файловый объект, имя файла, сообщение об ошибке).
        """
        try:
            # Скачиваем файл по URL
            response = requests.get(self.url, stream=True)
            response.raise_for_status()
            
            # Проверка размера файла (если сервер предоставил информацию о размере)
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > self.max_file_size_mb * 1024 * 1024:
                return None, None, f"File exceeds maximum size of {self.max_file_size_mb}MB"
                
            # Сохраняем файл во временный файл
            self.temp_dir = tempfile.mkdtemp()
            self.temp_file_path = os.path.join(self.temp_dir, str(uuid.uuid4()) + ".wav")
            
            with open(self.temp_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            # Открываем файл для обработки
            file = open(self.temp_file_path, 'rb')
            
            # Создаем объект файла, как будто он пришел из request.files
            fake_file = FakeFile(file, os.path.basename(self.temp_file_path))
            
            return fake_file, fake_file.filename, None
            
        except Exception as e:
            logger.error(f"Ошибка при получении файла по URL {self.url}: {e}")
            self.cleanup()
            return None, None, f"Error retrieving file from URL: {str(e)}"
            
    def cleanup(self):
        """Очищает временные файлы и директории."""
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            os.remove(self.temp_file_path)
        if self.temp_dir and os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)


class Base64Source(AudioSource):
    """Источник аудио для файлов, закодированных в base64."""
    
    def __init__(self, base64_data: str, max_file_size_mb: int = 100):
        """
        Инициализация источника для base64 файлов.
        
        Args:
            base64_data: Данные аудиофайла в формате base64.
            max_file_size_mb: Максимальный размер файла в МБ.
        """
        super().__init__(max_file_size_mb)
        self.base64_data = base64_data
        self.temp_file_path = None
        self.temp_dir = None
        
    def get_audio_file(self) -> Tuple[Optional[BinaryIO], Optional[str], Optional[str]]:
        """
        Получает аудиофайл из base64 данных.
        
        Returns:
            Кортеж (файловый объект, имя файла, сообщение об ошибке).
        """
        try:
            # Декодируем base64
            audio_data = base64.b64decode(self.base64_data)
            
            # Проверка размера файла
            if len(audio_data) > self.max_file_size_mb * 1024 * 1024:
                return None, None, f"File exceeds maximum size of {self.max_file_size_mb}MB"
                
            # Сохраняем файл во временный файл
            self.temp_dir = tempfile.mkdtemp()
            self.temp_file_path = os.path.join(self.temp_dir, str(uuid.uuid4()) + ".wav")
            
            with open(self.temp_file_path, 'wb') as f:
                f.write(audio_data)
                
            # Открываем файл для обработки
            file = open(self.temp_file_path, 'rb')
            
            # Создаем объект файла, как будто он пришел из request.files
            fake_file = FakeFile(file, os.path.basename(self.temp_file_path))
            
            return fake_file, fake_file.filename, None
            
        except Exception as e:
            logger.error(f"Ошибка при декодировании base64 данных: {e}")
            self.cleanup()
            return None, None, f"Error decoding base64 data: {str(e)}"
            
    def cleanup(self):
        """Очищает временные файлы и директории."""
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            os.remove(self.temp_file_path)
        if self.temp_dir and os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)


class LocalFileSource(AudioSource):
    """Источник аудио для локальных файлов на сервере."""
    
    def __init__(self, file_path: str, max_file_size_mb: int = 100):
        """
        Инициализация источника для локальных файлов.
        
        Args:
            file_path: Путь к локальному файлу.
            max_file_size_mb: Максимальный размер файла в МБ.
        """
        super().__init__(max_file_size_mb)
        self.file_path = file_path
        
    def get_audio_file(self) -> Tuple[Optional[BinaryIO], Optional[str], Optional[str]]:
        """
        Получает локальный аудиофайл.
        
        Returns:
            Кортеж (файловый объект, имя файла, сообщение об ошибке).
        """
        if not os.path.exists(self.file_path):
            return None, None, f"File not found: {self.file_path}"
            
        try:
            # Проверка размера файла
            file_size = os.path.getsize(self.file_path)
            if file_size > self.max_file_size_mb * 1024 * 1024:
                return None, None, f"File exceeds maximum size of {self.max_file_size_mb}MB"
                
            # Открываем файл для обработки
            file = open(self.file_path, 'rb')
            
            # Создаем объект файла, как будто он пришел из request.files
            fake_file = FakeFile(file, os.path.basename(self.file_path))
            
            return fake_file, fake_file.filename, None
            
        except Exception as e:
            logger.error(f"Ошибка при открытии локального файла {self.file_path}: {e}")
            return None, None, f"Error opening local file: {str(e)}"
