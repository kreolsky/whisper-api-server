"""
Модуль transcriber.py содержит класс WhisperTranscriber, который использует модель Whisper от 
OpenAI для транскрибации аудиофайлов в текст. Класс включает в себя методы для загрузки модели, 
обработки аудио (с использованием класса AudioProcessor), и выполнения транскрибации. 
Обрабатывает выбор устройства (CPU, CUDA, MPS) для выполнения вычислений и обеспечивает 
возможность использования Flash Attention 2 для ускорения работы модели на поддерживаемых GPU.
"""

import time
import threading
import traceback
from typing import Dict, Tuple, Union
import logging

import numpy as np
import torch
from transformers import (
    WhisperForConditionalGeneration,
    WhisperProcessor,
    pipeline,
)

from ..audio.processor import AudioProcessor
from ..audio.utils import load_audio
from ..infrastructure.storage import cleanup_temp_files

logger = logging.getLogger('app.transcriber')


class WhisperTranscriber:
    """
    Класс для распознавания речи с помощью модели Whisper.
    
    Attributes:
        config (Dict): Словарь с параметрами конфигурации.
        model_path (str): Путь к модели Whisper.
        language (str): Язык распознавания.
        chunk_length_s (int): Длина аудиочанка в секундах.
        batch_size (int): Размер пакета для обработки.
        max_new_tokens (int): Максимальное количество новых токенов для генерации.
        return_timestamps (bool): Флаг возврата временных меток.
        temperature (float): Параметр температуры для генерации.
        torch_dtype (torch.dtype): Оптимальный тип данных для тензоров.
        audio_processor (AudioProcessor): Объект для обработки аудио.
        device (torch.device): Устройство для вычислений.
        model (WhisperForConditionalGeneration): Загруженная модель Whisper.
        processor (WhisperProcessor): Процессор для модели Whisper.
        asr_pipeline (pipeline): Пайплайн для автоматического распознавания речи.
    """
    
    def __init__(self, config: Dict):
        """
        Инициализация транскрайбера.

        Args:
            config: Словарь с параметрами конфигурации.
        """
        self.config = config
        self.model_path = config["model_path"]
        self.language = config["language"]
        self.chunk_length_s = config["chunk_length_s"]
        self.batch_size = config["batch_size"]
        self.max_new_tokens = config["max_new_tokens"]
        self.return_timestamps = config["return_timestamps"]
        self.temperature = config["temperature"]

        # Lock для потокобезопасного доступа к модели —
        # Waitress обслуживает запросы в нескольких потоках,
        # а HuggingFace pipeline не является thread-safe
        self._inference_lock = threading.Lock()

        # Создаем объект для обработки аудио
        self.audio_processor = AudioProcessor(config)

        # Определяем устройство для вычислений
        self.device = self._get_device()

        # Оптимальный тип для тензоров (зависит от устройства)
        self.torch_dtype = self._get_torch_dtype()

        # Загружаем модель при инициализации
        self._load_model()

    def _get_device(self) -> torch.device:
        """
        Определение доступного устройства для вычислений.
        
        Returns:
            Объект устройства PyTorch.
        """
        if torch.cuda.is_available():
            # Получаем device_id из конфигурации, по умолчанию 0
            device_id = self.config.get("device_id", 0)
            
            # Проверяем, что device_id является целым числом
            if not isinstance(device_id, int):
                logger.warning("device_id должен быть целым числом, получено: %s. Используем значение по умолчанию 0", device_id)
                device_id = 0
            
            # Проверяем, доступен ли запрошенный GPU
            device_count = torch.cuda.device_count()
            if device_id >= device_count:
                logger.warning("Запрошенный GPU с индексом %s недоступен. Доступно GPU: %s. Используем GPU с индексом 0", device_id, device_count)
                device_id = 0
            
            logger.info("Используется CUDA GPU с индексом %s для вычислений", device_id)
            return torch.device(f"cuda:{device_id}")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            logger.info("Используется MPS (Apple Silicon) для вычислений")
            # Обходное решение для MPS: PyTorch проверяет is_initialized()
            # при создании тензоров на MPS-устройстве, что вызывает ошибку
            # в однопроцессном режиме.
            # TODO: Удалить после обновления до PyTorch >= 2.5
            setattr(torch.distributed, "is_initialized", lambda: False)
            return torch.device("mps")
        else:
            logger.info("Используется CPU для вычислений")
            return torch.device("cpu")

    def _get_torch_dtype(self) -> torch.dtype:
        """
        Определяет оптимальный тип данных для тензоров в зависимости от устройства.
        
        Returns:
            torch.float32 для CPU, torch.bfloat16 для GPU/MPS.
        """
        if self.device.type == "cpu":
            return torch.float32
        return torch.bfloat16

    def _load_model(self) -> None:
        """
        Загрузка модели и процессора.
        
        Raises:
            Exception: Если не удалось загрузить модель.
        """
        logger.info("Загрузка модели из %s", self.model_path)

        model_kwargs = dict(
            torch_dtype=self.torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        )

        use_flash_attn = False
        if self.device.type == "cuda":
            # Flash Attention 2 требует архитектуру Ampere или новее (compute capability >= 8.0)
            capability = torch.cuda.get_device_capability(self.device.index)
            if capability[0] >= 8:
                use_flash_attn = True
                logger.info("GPU поддерживает Flash Attention 2 (compute capability: %d.%d)", *capability)
            else:
                logger.info("GPU не поддерживает Flash Attention 2 (compute capability: %d.%d), используется стандартный режим", *capability)

        try:
            if use_flash_attn:
                model_kwargs["attn_implementation"] = "flash_attention_2"
            self.model = WhisperForConditionalGeneration.from_pretrained(
                self.model_path, **model_kwargs
            ).to(self.device)
            if use_flash_attn:
                logger.info("Используется Flash Attention 2")
        except Exception as e:
            logger.warning("Не удалось загрузить модель с Flash Attention: %s", e)
            model_kwargs.pop("attn_implementation", None)
            self.model = WhisperForConditionalGeneration.from_pretrained(
                self.model_path, **model_kwargs
            ).to(self.device)

        self.processor = WhisperProcessor.from_pretrained(self.model_path)

        self.asr_pipeline = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=self.processor.tokenizer,
            feature_extractor=self.processor.feature_extractor,
            chunk_length_s=self.chunk_length_s,
            batch_size=self.batch_size,
            return_timestamps=self.return_timestamps,
            torch_dtype=self.torch_dtype,
            device=self.device,
        )

        logger.info("Модель успешно загружена и готова к использованию")

    def transcribe(self, audio_path: str, return_timestamps: bool = None,
                   language: str = None, temperature: float = None,
                   prompt: str = None) -> Union[str, Dict]:
        """
        Транскрибация аудиофайла.

        Args:
            audio_path: Путь к обработанному аудиофайлу.
            return_timestamps: Флаг возврата временных меток. Если None — берётся из конфига.
            language: Язык распознавания. Если None — берётся из конфига.
            temperature: Параметр температуры для генерации. Если None — берётся из конфига.
            prompt: Текстовая подсказка для модели (имена, термины, контекст).

        Returns:
            В зависимости от параметра return_timestamps:
            - Если return_timestamps=False: строка с распознанным текстом
            - Если return_timestamps=True: словарь с ключами "segments" (список словарей с ключами start_time_ms, end_time_ms, text) и "text" (полный текст)
        """
        if return_timestamps is None:
            return_timestamps = self.return_timestamps
        if language is None:
            language = self.language
        if temperature is None:
            temperature = self.temperature

        logger.info("Начало транскрибации файла: %s", audio_path)

        try:
            # Загрузка аудио в формате numpy array
            audio_array, sampling_rate = load_audio(audio_path, sr=16000)

            # Транскрибация с корректным форматом данных
            generate_kwargs = {
                "language": language,
                "max_new_tokens": self.max_new_tokens,
                "temperature": temperature,
            }
            if prompt:
                generate_kwargs["prompt_ids"] = self.processor.get_prompt_ids(
                    prompt, return_tensors="pt"
                ).to(self.device)

            with self._inference_lock:
                result = self.asr_pipeline(
                    {"raw": audio_array, "sampling_rate": sampling_rate},
                    generate_kwargs=generate_kwargs,
                    return_timestamps=return_timestamps,
                )
            
            # Если временные метки не запрошены, возвращаем только текст
            if not return_timestamps:
                transcribed_text = result.get("text", "")
                logger.info("Транскрибация завершена: получено %s символов текста", len(transcribed_text))
                return transcribed_text
            
            # Если временные метки запрошены, обрабатываем и форматируем результат
            segments = []
            full_text = result.get("text", "")
            
            if "chunks" in result:
                # Для новых версий модели Whisper
                for chunk in result["chunks"]:
                    start_time = chunk.get("timestamp", [0, 0])[0]
                    end_time = chunk.get("timestamp", [0, 0])[1]
                    text = chunk.get("text", "").strip()
                    
                    segments.append({
                        "start_time_ms": int(start_time * 1000),
                        "end_time_ms": int(end_time * 1000),
                        "text": text
                    })
            elif hasattr(result, "get") and "segments" in result:
                # Для старых версий модели Whisper
                for segment in result["segments"]:
                    start_time = segment.get("start", 0)
                    end_time = segment.get("end", 0)
                    text = segment.get("text", "").strip()
                    
                    segments.append({
                        "start_time_ms": int(start_time * 1000),
                        "end_time_ms": int(end_time * 1000),
                        "text": text
                    })
            else:
                logger.warning("Временные метки запрошены, но не найдены в результате транскрибации")
            
            logger.info("Транскрибация с временными метками завершена: получено %s сегментов", len(segments))
            
            # Возвращаем словарь с сегментами и полным текстом
            return {
                "segments": segments,
                "text": full_text
            }
            
        except Exception as e:
            logger.error("Ошибка в процессе транскрибации аудиофайла '%s': %s", audio_path, e)
            logger.error("Тип исключения: %s", type(e).__name__)
            logger.error("Traceback: %s", traceback.format_exc())
            raise

    def process_file(self, input_path: str, return_timestamps: bool = None,
                     language: str = None, temperature: float = None,
                     prompt: str = None) -> Union[str, Dict]:
        """
        Полный процесс обработки и транскрибации аудиофайла.

        Args:
            input_path: Путь к исходному аудиофайлу.
            return_timestamps: Флаг возврата временных меток. Если None — берётся из конфига.
            language: Язык распознавания. Если None — берётся из конфига.
            temperature: Параметр температуры для генерации. Если None — берётся из конфига.
            prompt: Текстовая подсказка для модели (имена, термины, контекст).

        Returns:
            В зависимости от параметра return_timestamps:
            - Если return_timestamps=False: строка с распознанным текстом
            - Если return_timestamps=True: словарь с ключами "segments" и "text"
        """
        start_time = time.time()
        logger.info("Начало обработки файла: %s", input_path)
        
        temp_files = []
        
        try:
            # Обработка аудио (конвертация, нормализация, добавление тишины)
            processed_path, temp_files = self.audio_processor.process_audio(input_path)
            
            # Транскрибация
            result = self.transcribe(processed_path, return_timestamps=return_timestamps,
                                     language=language, temperature=temperature,
                                     prompt=prompt)
            
            elapsed_time = time.time() - start_time
            logger.info("Обработка и транскрибация завершены за %.2f секунд", elapsed_time)
            
            return result
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error("Ошибка при обработке файла '%s' через %.2f секунд: %s", input_path, elapsed_time, e)
            logger.error("Тип исключения: %s", type(e).__name__)
            logger.error("Traceback: %s", traceback.format_exc())
            raise
            
        finally:
            # Очистка временных файлов
            cleanup_temp_files(temp_files)