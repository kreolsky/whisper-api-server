"""
Модуль file_manager.py содержит классы для централизованного управления временными файлами.
Предоставляет унифицированный интерфейс для создания, отслеживания и очистки временных файлов.
"""

import os
import uuid
import tempfile
import contextlib
from typing import List, Tuple, Optional, Generator
from .utils import logger


class TempFileManager:
    """
    Класс для централизованного управления временными файлами.
    
    Предоставляет методы для создания временных файлов и их последующей очистки.
    Использует контекстные менеджеры для автоматической очистки ресурсов.
    """
    
    def __init__(self):
        """
        Инициализация менеджера временных файлов.
        """
        self.temp_files = []
        self.temp_dirs = []
    
    def create_temp_file(self, suffix: str = ".wav") -> Tuple[str, str]:
        """
        Создает временный файл с уникальным именем.
        
        Args:
            suffix: Расширение временного файла.
            
        Returns:
            Кортеж (путь к файлу, путь к временной директории).
        """
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, f"{uuid.uuid4()}{suffix}")
        
        self.temp_files.append(temp_file)
        self.temp_dirs.append(temp_dir)
        
        logger.debug(f"Создан временный файл: {temp_file}")
        return temp_file, temp_dir
    
    def cleanup_temp_files(self, file_paths: Optional[List[str]] = None) -> None:
        """
        Очищает временные файлы и директории.
        
        Args:
            file_paths: Список путей к файлам для очистки. Если None, очищает все отслеживаемые файлы.
        """
        paths_to_clean = file_paths if file_paths is not None else self.temp_files
        
        for path in paths_to_clean:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.debug(f"Удален временный файл: {path}")
                    
                    # Попытка удалить директорию, если она пуста
                    temp_dir = os.path.dirname(path)
                    if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
                        logger.debug(f"Удалена временная директория: {temp_dir}")
                        
                        # Удаление из списка отслеживаемых директорий
                        if temp_dir in self.temp_dirs:
                            self.temp_dirs.remove(temp_dir)
            except Exception as e:
                logger.warning(f"Не удалось очистить временный файл {path}: {e}")
        
        # Удаление файлов из списка отслеживаемых
        if file_paths is None:
            self.temp_files.clear()
        else:
            for path in file_paths:
                if path in self.temp_files:
                    self.temp_files.remove(path)
    
    @contextlib.contextmanager
    def temp_file(self, suffix: str = ".wav") -> Generator[str, None, None]:
        """
        Контекстный менеджер для создания и автоматической очистки временного файла.
        
        Args:
            suffix: Расширение временного файла.
            
        Yields:
            Путь к временному файлу.
        """
        temp_file, _ = self.create_temp_file(suffix)
        try:
            yield temp_file
        finally:
            self.cleanup_temp_files([temp_file])
    
    def cleanup_all(self) -> None:
        """
        Очищает все отслеживаемые временные файлы и директории.
        """
        self.cleanup_temp_files()
        for temp_dir in self.temp_dirs:
            try:
                if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                    os.rmdir(temp_dir)
                    logger.debug(f"Удалена временная директория: {temp_dir}")
            except Exception as e:
                logger.warning(f"Не удалось очистить временную директорию {temp_dir}: {e}")
        self.temp_dirs.clear()


# Глобальный экземпляр менеджера временных файлов
temp_file_manager = TempFileManager()