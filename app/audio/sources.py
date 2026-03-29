"""
Модуль sources.py содержит функции для получения аудиофайлов
из различных источников (загруженные файлы, URL, base64).
"""

import os
import uuid
import tempfile
import base64
from urllib.parse import urlparse
import magic
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
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return None, None, f"Unsupported URL scheme: {parsed.scheme}. Only http/https allowed"

        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Проверка размера по Content-Length
        content_length = response.headers.get('Content-Length')
        if content_length:
            error = _check_size(int(content_length), max_file_size_mb)
            if error:
                return None, None, error

        # Извлекаем имя файла из Content-Disposition или URL
        original_name = None
        cd = response.headers.get('Content-Disposition', '')
        if 'filename=' in cd:
            original_name = cd.split('filename=')[-1].strip('" ')
        if not original_name:
            url_path = parsed.path.rstrip('/')
            if url_path:
                original_name = os.path.basename(url_path)

        temp_path = _make_temp_path()
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return temp_path, original_name or os.path.basename(temp_path), None

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

        # Определяем формат по содержимому
        mime_to_ext = {
            "audio/mpeg": ".mp3",
            "audio/ogg": ".ogg",
            "audio/flac": ".flac",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
            "audio/aac": ".aac",
            "audio/webm": ".webm",
        }
        detected_mime = magic.from_buffer(audio_data[:1024], mime=True)
        suffix = mime_to_ext.get(detected_mime, ".wav")

        temp_path = _make_temp_path(suffix)
        with open(temp_path, 'wb') as f:
            f.write(audio_data)

        return temp_path, os.path.basename(temp_path), None

    except Exception as e:
        logger.error(f"Ошибка при декодировании base64 данных: {e}")
        return None, None, f"Error decoding base64 data: {str(e)}"
