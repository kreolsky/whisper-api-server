"""
Утилиты для управления временными файлами.
"""

import os
import tempfile
import logging

logger = logging.getLogger('app.file_manager')


def create_temp_file(suffix: str = ".wav") -> str:
    """
    Создаёт временный файл с уникальным именем.

    Args:
        suffix: Расширение временного файла.

    Returns:
        Путь к временному файлу.
    """
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    logger.debug("Создан временный файл: %s", temp_path)
    return temp_path


def cleanup_temp_files(file_paths: list) -> None:
    """
    Удаляет временные файлы.

    Args:
        file_paths: Список путей к файлам для удаления.
    """
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug("Удалён временный файл: %s", path)
        except Exception as e:
            logger.warning("Не удалось очистить временный файл %s: %s", path, e)
