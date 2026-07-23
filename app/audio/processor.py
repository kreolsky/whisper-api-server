"""
Модуль processor.py — предобработка аудиофайлов (Whisper-специфичная).
Конвертация в WAV 16kHz, нормализация sox, добавление тишины.
"""

import os
import subprocess
from typing import Tuple
import logging

from ..core.config import AppConfig
from ..infrastructure.storage import create_temp_file, cleanup_temp_files
from .utils import get_audio_duration

logger = logging.getLogger('app.audio_processor')


class AudioProcessor:
    """
    Класс для предобработки аудиофайлов перед распознаванием (Whisper-пайплайн).

    Attributes:
        config: Типизированная конфигурация.
        norm_level: Уровень нормализации аудио.
        compand_params: Параметры компрессора аудио.
    """

    def __init__(self, config: AppConfig):
        """
        Инициализация обработчика аудио.

        Args:
            config: Типизированная конфигурация приложения.
        """
        self.config = config
        model_config = config.model
        self.norm_level = model_config.get("norm_level", "-0.5")
        self.compand_params = model_config.get("compand_params", "0.3,1 -90,-90,-70,-70,-60,-20,0,0 -5 0 0.2")

    def convert_to_wav(self, input_path: str) -> str:
        """
        Конвертация входного аудиофайла в WAV формат с частотой дискретизации 16 кГц (моно).

        Args:
            input_path: Путь к исходному аудиофайлу.

        Returns:
            Путь к сконвертированному WAV-файлу.

        Raises:
            subprocess.CalledProcessError: Если произошла ошибка при конвертации.
        """
        audio_rate = self.config.audio_rate

        output_path = create_temp_file(".wav")

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-y",
            "-i", input_path,
            "-ar", f"{audio_rate}",
            "-ac", "1",
            output_path
        ]

        logger.debug("Конвертация в WAV: %s", " ".join(cmd))

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("Файл конвертирован в WAV: %s", output_path)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error("Ошибка при конвертации в WAV: %s", e.stderr.decode())
            raise

    def normalize_audio(self, input_path: str) -> str:
        """
        Нормализация аудиофайла с использованием sox.

        Args:
            input_path: Путь к WAV-файлу.

        Returns:
            Путь к нормализованному WAV-файлу.

        Raises:
            subprocess.CalledProcessError: Если произошла ошибка при нормализации.
        """
        output_path = create_temp_file("_normalized.wav")

        cmd = [
            "sox",
            input_path,
            output_path,
            "norm", self.norm_level,
            "compand"
        ] + self.compand_params.split()

        logger.debug("Нормализация аудио: %s", " ".join(cmd))

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("Аудио нормализовано: %s", output_path)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error("Ошибка при нормализации аудио: %s", e.stderr.decode())
            raise

    def add_silence(self, input_path: str) -> str:
        """
        Добавляет тишину в начало аудиофайла.

        Args:
            input_path: Путь к аудиофайлу.

        Returns:
            Путь к аудиофайлу с добавленной тишиной.

        Raises:
            subprocess.CalledProcessError: Если произошла ошибка при добавлении тишины.
        """
        output_path = create_temp_file("_silence.wav")

        cmd = [
            "sox",
            input_path,
            output_path,
            "pad", "2.0", "1.0"
        ]

        logger.info("Добавление тишины: %s", " ".join(cmd))

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("Тишина добавлена: %s", output_path)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error("Ошибка при добавлении тишины: %s", e.stderr.decode())
            raise

    def process_audio(self, input_path: str) -> Tuple[str, list, float]:
        """
        Полная обработка аудиофайла: конвертация, нормализация и добавление тишины.

        Args:
            input_path: Путь к исходному аудиофайлу.

        Returns:
            Кортеж: (путь к обработанному файлу, список временных файлов для удаления, длительность в секундах)

        Raises:
            Exception: Если произошла ошибка при обработке аудио.
        """
        temp_files = []

        try:
            wav_path = self.convert_to_wav(input_path)
            if wav_path != input_path:
                temp_files.append(wav_path)

            duration = get_audio_duration(wav_path)

            normalized_path = self.normalize_audio(wav_path)
            temp_files.append(normalized_path)

            silence_path = self.add_silence(normalized_path)
            temp_files.append(silence_path)

            return silence_path, temp_files, duration

        except Exception as e:
            logger.error("Ошибка при обработке аудио %s: %s", input_path, e)
            cleanup_temp_files(temp_files)
            raise
