"""
Модуль context_managers.py содержит контекстные менеджеры для управления ресурсами.
"""

import os
import contextlib
from typing import Generator, BinaryIO
from .utils import logger


@contextlib.contextmanager
def open_file(file_path: str, mode: str = 'rb') -> Generator[BinaryIO, None, None]:
    """
    Контекстный менеджер для безопасного открытия и закрытия файлов.
    
    Args:
        file_path: Путь к файлу.
        mode: Режим открытия файла.
        
    Yields:
        Файловый объект.
    """
    file_obj = None
    try:
        file_obj = open(file_path, mode)
        yield file_obj
    except Exception as e:
        logger.error(f"Ошибка при работе с файлом {file_path}: {e}")
        raise
    finally:
        if file_obj:
            file_obj.close()


@contextlib.contextmanager
def audio_file(file_path: str) -> Generator[BinaryIO, None, None]:
    """
    Контекстный менеджер для работы с аудиофайлами.
    
    Args:
        file_path: Путь к аудиофайлу.
        
    Yields:
        Файловый объект в бинарном режиме.
    """
    with open_file(file_path, 'rb') as f:
        yield f