"""
Модуль processor.py содержит класс AudioProcessor, предназначенный для предобработки аудиофайлов 
перед их использованием в системах распознавания речи. Класс предоставляет методы для конвертации 
аудио в формат WAV с частотой дискретизации 16 кГц, нормализации уровня громкости, 
добавления тишины в начало записи, а также для удаления временных файлов, созданных в процессе обработки. 
"""

import os
import subprocess
from typing import Dict, Tuple
import logging

from ..infrastructure.storage import create_temp_file, cleanup_temp_files

logger = logging.getLogger('app.audio_processor')


class AudioProcessor:
    """
    Класс для предобработки аудиофайлов перед распознаванием.
    
    Attributes:
        config (Dict): Словарь с параметрами конфигурации.
        norm_level (str): Уровень нормализации аудио.
        compand_params (str): Параметры компрессора аудио.
    """
    
    def __init__(self, config: Dict):
        """
        Инициализация обработчика аудио.
        
        Args:
            config: Словарь с параметрами конфигурации.
        """
        self.config = config
        self.norm_level = config.get("norm_level", "-0.5")
        self.compand_params = config.get("compand_params", "0.3,1 -90,-90,-70,-70,-60,-20,0,0 -5 0 0.2")

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
        audio_rate = self.config["audio_rate"]

        # Создаем временный файл для WAV
        output_path = create_temp_file(".wav")
        
        # Команда для конвертации
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-y",
            "-i", input_path,
            "-ar", f"{audio_rate}",
            "-ac", "1",  # Монофонический звук
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
        # Создаем временный файл для нормализованного аудио
        output_path = create_temp_file("_normalized.wav")
        
        # Команда для нормализации аудио с помощью sox
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
        # Создаем временный файл
        output_path = create_temp_file("_silence.wav")
        
        # Команда для добавления тишины в начало файла
        cmd = [
            "sox",
            input_path,
            output_path,
            "pad", "2.0", "1.0"  # Добавление тишины в начале и в конце (секунды)
        ]
        
        logger.info("Добавление тишины: %s", " ".join(cmd))
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("Тишина добавлена: %s", output_path)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error("Ошибка при добавлении тишины: %s", e.stderr.decode())
            raise
    
    def process_audio(self, input_path: str) -> Tuple[str, list]:
        """
        Полная обработка аудиофайла: конвертация, нормализация и добавление тишины.
        
        Args:
            input_path: Путь к исходному аудиофайлу.
            
        Returns:
            Кортеж: (путь к обработанному файлу, список временных файлов для удаления)
            
        Raises:
            Exception: Если произошла ошибка при обработке аудио.
        """
        temp_files = []
        
        try:
            # Конвертация в WAV
            wav_path = self.convert_to_wav(input_path)
            if wav_path != input_path:  # Если был создан временный файл
                temp_files.append(wav_path)
            
            # Нормализация
            normalized_path = self.normalize_audio(wav_path)
            temp_files.append(normalized_path)

            # Добавление тишины
            silence_path = self.add_silence(normalized_path)
            temp_files.append(silence_path)
            
            return silence_path, temp_files
        
        except Exception as e:
            logger.error("Ошибка при обработке аудио %s: %s", input_path, e)
            cleanup_temp_files(temp_files)
            raise