"""
Модуль audio_processor.py содержит класс AudioProcessor, предназначенный для предобработки аудиофайлов 
перед их использованием в системах распознавания речи. Класс предоставляет методы для конвертации 
аудио в формат WAV с частотой дискретизации 16 кГц, нормализации уровня громкости, 
добавления тишины в начало записи, а также для удаления временных файлов, созданных в процессе обработки. 
"""

import os
import subprocess
import uuid
from typing import Dict, Tuple

from .file_manager import temp_file_manager
from .context_managers import open_file
from .utils import logger


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
        self.audio_speed_factor = config.get("audio_speed_factor", 1.25)
    
    def convert_to_wav(self, input_path: str) -> str:
        """
        Конвертация входного аудиофайла в WAV формат с частотой дискретизации 16 кГц.
        
        Args:
            input_path: Путь к исходному аудиофайлу.
            
        Returns:
            Путь к сконвертированному WAV-файлу.
            
        Raises:
            subprocess.CalledProcessError: Если произошла ошибка при конвертации.
        """
        audio_rate = self.config["audio_rate"]

        # Проверка расширения файла
        if input_path.lower().endswith('.wav'):
            # Проверяем, нужно ли преобразовывать WAV-файл (например, если частота не 16 кГц)
            try:
                info = subprocess.check_output(['soxi', input_path]).decode()
                if f'{audio_rate} Hz' in info:
                    logger.info(f"Файл {input_path} уже в формате WAV с частотой {audio_rate} Гц")
                    return input_path
            except subprocess.CalledProcessError:
                logger.warning(f"Не удалось получить информацию о WAV-файле {input_path}")
                # Продолжаем конвертацию, чтобы быть уверенными в формате

        # Создаем временный файл для WAV
        output_path, _ = temp_file_manager.create_temp_file(".wav")
        
        # Команда для конвертации
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-i", input_path,
            "-ar", f"{audio_rate}",
            "-ac", "1",  # Монофонический звук
            output_path
        ]
        
        logger.info(f"Конвертация в WAV: {' '.join(cmd)}")
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Файл конвертирован в WAV: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при конвертации в WAV: {e.stderr.decode()}")
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
        output_path, _ = temp_file_manager.create_temp_file("_normalized.wav")
        
        # Команда для нормализации аудио с помощью sox
        cmd = [
            "sox", 
            input_path, 
            output_path, 
            "norm", self.norm_level,
            "compand"
        ] + self.compand_params.split()
        
        logger.info(f"Нормализация аудио: {' '.join(cmd)}")
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Аудио нормализовано: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при нормализации аудио: {e.stderr.decode()}")
            raise
    
    def speed_up_audio(self, input_path: str) -> str:
        """
        Ускоряет воспроизведение аудиофайла с использованием FFmpeg.
        
        Args:
            input_path: Путь к WAV-файлу.
            
        Returns:
            Путь к ускоренному WAV-файлу.
            
        Raises:
            subprocess.CalledProcessError: Если произошла ошибка при ускорении.
        """
        # Если ускорение не требуется (коэффициент = 1.0), возвращаем исходный файл
        if float(self.audio_speed_factor) == 1.0:
            logger.info(f"Ускорение не требуется (коэффициент = {self.audio_speed_factor})")
            return input_path
        
        # Создаем временный файл для ускоренного аудио
        output_path, _ = temp_file_manager.create_temp_file("_speedup.wav")
        
        # Команда для ускорения аудио с помощью FFmpeg
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-i", input_path,
            "-filter:a", f"atempo={self.audio_speed_factor}",
            output_path
        ]
        
        logger.info(f"Ускорение аудио в {self.audio_speed_factor}x: {' '.join(cmd)}")
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Аудио ускорено: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при ускорении аудио: {e.stderr.decode()}")
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
        output_path, _ = temp_file_manager.create_temp_file("_silence.wav")
        
        # Команда для добавления тишины в начало файла
        cmd = [
            "sox",
            input_path,
            output_path,
            "pad", "2.0", "1.0"  # Добавление тишины в начале и в конце (секунды)
        ]
        
        logger.info(f"Добавление тишины: {' '.join(cmd)}")
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Тишина добавлена: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при добавлении тишины: {e.stderr.decode()}")
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
            
            # УСКОРЕНИЕ ЗВУКА (НОВЫЙ ШАГ)
            speedup_path = self.speed_up_audio(normalized_path)
            if speedup_path != normalized_path:  # Если был создан временный файл
                temp_files.append(speedup_path)
            
            # Добавление тишины
            silence_path = self.add_silence(speedup_path)
            temp_files.append(silence_path)
            
            return silence_path, temp_files
        
        except Exception as e:
            logger.error(f"Ошибка при обработке аудио {input_path}: {e}")
            temp_file_manager.cleanup_temp_files(temp_files)
            raise
