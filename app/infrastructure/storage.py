"""
Утилиты для управления временными файлами.
"""

import os
import uuid
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
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}{suffix}")
    logger.debug(f"Создан временный файл: {temp_path}")
    return temp_path


def cleanup_temp_files(file_paths: list) -> None:
    """
    Удаляет временные файлы и их директории.

    Args:
        file_paths: Список путей к файлам для удаления.
    """
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"Удалён временный файл: {path}")

                temp_dir = os.path.dirname(path)
                if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                    os.rmdir(temp_dir)
        except Exception as e:
            logger.warning(f"Не удалось очистить временный файл {path}: {e}")
