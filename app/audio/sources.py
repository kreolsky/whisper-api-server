"""
Модуль sources.py содержит функции для получения аудиофайлов
из различных источников (загруженные файлы, URL, base64, локальные файлы).
"""

import os
import uuid
import tempfile
import base64
import requests
from typing import Tuple, Optional
import logging

logger = logging.getLogger('app.audio_sources')


def _check_size(size_bytes: int, max_size_mb: int) -> Optional[str]:
    """Проверяет размер файла. Возвращает сообщение об ошибке или None."""
    if size_bytes > max_size_mb * 1024 * 1024:
        return f"File exceeds maximum size of {max_size_mb}MB"
    return None


def _make_temp_path(suffix: str = ".wav") -> str:
    """Создаёт путь для временного файла."""
    temp_dir = tempfile.mkdtemp()
    return os.path.join(temp_dir, f"{uuid.uuid4()}{suffix}")


def get_uploaded_file(request_files, max_file_size_mb: int = 100) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Получает аудиофайл из загруженных файлов Flask.

    Returns:
        Кортеж (путь к temp-файлу, имя файла, сообщение об ошибке).
    """
    if 'file' not in request_files:
        return None, None, "No file part"

    file = request_files['file']

    if file.filename == '':
        return None, None, "No selected file"

    # Проверка размера
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    error = _check_size(size, max_file_size_mb)
    if error:
        return None, None, error

    # Сохраняем во временный файл
    temp_path = _make_temp_path()
    file.save(temp_path)

    return temp_path, file.filename, None


def get_url_file(url: str, max_file_size_mb: int = 100) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Получает аудиофайл по URL.

    Returns:
        Кортеж (путь к temp-файлу, имя файла, сообщение об ошибке).
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Проверка размера по Content-Length
        content_length = response.headers.get('Content-Length')
        if content_length:
            error = _check_size(int(content_length), max_file_size_mb)
            if error:
                return None, None, error

        temp_path = _make_temp_path()
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return temp_path, os.path.basename(temp_path), None

    except Exception as e:
        logger.error(f"Ошибка при получении файла по URL {url}: {e}")
        return None, None, f"Error retrieving file from URL: {str(e)}"


def get_base64_file(base64_data: str, max_file_size_mb: int = 100) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Получает аудиофайл из base64 данных.

    Returns:
        Кортеж (путь к temp-файлу, имя файла, сообщение об ошибке).
    """
    try:
        audio_data = base64.b64decode(base64_data)

        error = _check_size(len(audio_data), max_file_size_mb)
        if error:
            return None, None, error

        temp_path = _make_temp_path()
        with open(temp_path, 'wb') as f:
            f.write(audio_data)

        return temp_path, os.path.basename(temp_path), None

    except Exception as e:
        logger.error(f"Ошибка при декодировании base64 данных: {e}")
        return None, None, f"Error decoding base64 data: {str(e)}"


def get_local_file(file_path: str, max_file_size_mb: int = 100) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Получает локальный аудиофайл.

    Returns:
        Кортеж (путь к файлу, имя файла, сообщение об ошибке).
        Примечание: возвращает оригинальный путь, не копирует файл.
    """
    if not os.path.exists(file_path):
        return None, None, f"File not found: {file_path}"

    try:
        error = _check_size(os.path.getsize(file_path), max_file_size_mb)
        if error:
            return None, None, error

        return file_path, os.path.basename(file_path), None

    except Exception as e:
        logger.error(f"Ошибка при открытии локального файла {file_path}: {e}")
        return None, None, f"Error opening local file: {str(e)}"
