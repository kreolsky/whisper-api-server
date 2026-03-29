"""
Утилитарные функции для работы с аудио.
"""

import os
import subprocess
import wave
import numpy as np
from scipy.signal import resample as scipy_resample
import logging
from typing import Tuple

logger = logging.getLogger('app.audio_utils')


def load_audio(file_path: str, sr: int = 16000) -> Tuple[np.ndarray, int]:
    """
    Загрузка аудиофайла с использованием встроенной библиотеки wave.

    Args:
        file_path: Путь к аудиофайлу.
        sr: Целевая частота дискретизации.

    Returns:
        Кортеж (массив numpy, частота дискретизации).
    """
    try:
        with wave.open(file_path, 'rb') as wav_file:
            if wav_file.getnchannels() != 1:
                logger.warning(f"Файл {file_path} не моно-аудио")

            frames = wav_file.readframes(-1)
            audio_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            sampling_rate = wav_file.getframerate()

            if sampling_rate != sr:
                num_samples = int(len(audio_array) * sr / sampling_rate)
                audio_array = scipy_resample(audio_array, num_samples)
                sampling_rate = sr

            return audio_array, sampling_rate

    except Exception as e:
        logger.error(f"Ошибка при загрузке аудио {file_path}: {e}")
        raise


def get_audio_duration(file_path: str) -> float:
    """
    Определяет длительность аудиофайла с использованием ffprobe.

    Args:
        file_path: Путь к аудиофайлу.

    Returns:
        Длительность в секундах.
    """
    if not os.path.exists(file_path):
        raise Exception(f"Файл не существует: {file_path}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        return float(result.stdout.strip())
    except subprocess.TimeoutExpired:
        raise Exception(f"Таймаут при определении длительности файла {file_path}")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Ошибка ffprobe для файла {file_path}: {e.stderr}")
    except (ValueError, TypeError) as e:
        raise Exception(f"Ошибка при преобразовании длительности для файла {file_path}: {e}")
