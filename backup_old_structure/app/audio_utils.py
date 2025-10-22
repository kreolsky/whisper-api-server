"""
Модуль audio_utils.py содержит утилитарные функции для работы с аудио.
"""

import os
import subprocess
import wave
import numpy as np
import logging
from typing import Tuple

logger = logging.getLogger('app.audio_utils')


class AudioUtils:
    """Утилитарный класс для работы с аудио."""
    
    @staticmethod
    def load_audio(file_path: str, sr: int = 16000) -> Tuple[np.ndarray, int]:
        """
        Загрузка аудиофайла с использованием встроенной библиотеки wave.

        Args:
            file_path: Путь к аудиофайлу.
            sr: Целевая частота дискретизации.

        Returns:
            Кортеж (массив numpy, частота дискретизации).
            
        Raises:
            Exception: Если не удалось загрузить аудиофайл.
        """
        try:
            # Открываем WAV файл
            with wave.open(file_path, 'rb') as wav_file:
                # Проверяем, что это моно-аудио
                if wav_file.getnchannels() != 1:
                    logger.warning(f"Файл {file_path} не моно-аудио, конвертируем в моно")
                
                # Читаем аудиоданные
                frames = wav_file.readframes(-1)
                # Конвертируем 16-битные целые числа в float32 в диапазоне [-1.0, 1.0]
                # 32768.0 - это 2^15, максимальное значение для 16-битного знакового целого
                audio_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Получаем частоту дискретизации
                sampling_rate = wav_file.getframerate()
                
                # Если частота дискретизации не совпадает с целевой, выполняем ресемплинг
                if sampling_rate != sr:
                    from scipy.signal import resample
                    num_samples = int(len(audio_array) * sr / sampling_rate)
                    audio_array = resample(audio_array, num_samples)
                    sampling_rate = sr
                
                return audio_array, sampling_rate
                
        except Exception as e:
            logger.error(f"Ошибка при загрузке аудио {file_path}: {e}")
            raise
    
    @staticmethod
    def get_audio_duration(file_path: str) -> float:
        """
        Определяет длительность аудиофайла с использованием ffprobe.
        
        Args:
            file_path: Путь к аудиофайлу.
            
        Returns:
            Длительность в секундах.
        """
        try:
            # Проверяем, что файл существует
            if not os.path.exists(file_path):
                logger.error(f"Файл не существует: {file_path}")
                raise Exception(f"Файл не существует: {file_path}")
                
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10  # Ограничение по времени выполнения
            )
            
            duration = float(result.stdout.strip())
            return duration
            
        except subprocess.TimeoutExpired:
            logger.error(f"Таймаут при определении длительности файла {file_path}")
            raise Exception(f"Таймаут при определении длительности файла {file_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при выполнении ffprobe для файла {file_path}: {e.stderr}")
            raise Exception(f"Ошибка при выполнении ffprobe для файла {file_path}: {e.stderr}")
        except (ValueError, TypeError) as e:
            logger.error(f"Ошибка при преобразовании длительности для файла {file_path}: {e}")
            raise Exception(f"Ошибка при преобразовании длительности для файла {file_path}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при определении длительности файла {file_path}: {e}")
            raise Exception(f"Неожиданная ошибка при определении длительности файла {file_path}: {e}")
