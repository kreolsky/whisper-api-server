"""
Модуль transcriber_service.py содержит класс TranscriptionService,
который отвечает за обработку и транскрибацию аудиофайлов.
"""

import os
import uuid
import tempfile
import time
import traceback
from typing import Dict, Tuple

from .utils import logger
from .audio_utils import AudioUtils
from .history_logger import HistoryLogger
from .audio_sources import AudioSource
from .validators import FileValidator, ValidationError


class TranscriptionService:
    """
    Сервис для обработки и транскрибации аудиофайлов.
    
    Attributes:
        transcriber: Экземпляр транскрайбера.
        config (Dict): Словарь с конфигурацией.
        max_file_size_mb (int): Максимальный размер файла в МБ.
        history (HistoryLogger): Объект журналирования.
    """

    def __init__(self, transcriber, config: Dict):
        """
        Инициализация сервиса транскрибации.

        Args:
            transcriber: Экземпляр транскрайбера.
            config: Словарь с конфигурацией.
        """
        self.transcriber = transcriber
        self.config = config
        self.max_file_size_mb = self.config.get("file_validation", {}).get("max_file_size_mb", 100)

        # Объект журналирования
        self.history = HistoryLogger(config)

    # Метод get_audio_duration удален, так как его функциональность перенесена в AudioUtils

    def transcribe_from_source(self, source: AudioSource, params: Dict = None, file_validator: FileValidator = None) -> Tuple[Dict, int]:
        """
        Транскрибирует аудиофайл из указанного источника.

        Args:
            source: Источник аудиофайла.
            params: Дополнительные параметры для транскрибации.
            file_validator: Валидатор файлов.

        Returns:
            Кортеж (JSON-ответ, HTTP-код).
        """
        # Получаем файл из источника
        file, filename, error = source.get_audio_file()

        # Обрабатываем ошибки получения файла
        if error:
            logger.warning(f"Ошибка получения файла из источника: {error}")
            return {"error": error}, 400

        if not file:
            logger.warning("Не удалось получить аудиофайл из источника")
            return {"error": "Failed to get audio file"}, 400
        
        # Валидация файла, если предоставлен валидатор
        if file_validator:
            try:
                file_validator.validate_file(file, filename)
            except ValidationError as e:
                # Логирование ошибки валидации
                logger.warning(f"Ошибка валидации файла '{filename}': {str(e)}")
                return {"error": str(e)}, 400

        # Извлекаем параметры из запроса, если они есть
        params = params or {}
        language = params.get('language', self.config.get('language', 'en'))
        temperature = float(params.get('temperature', 0.0))
        prompt = params.get('prompt', '')

        # Проверяем, запрошены ли временные метки
        return_timestamps = params.get('return_timestamps', self.config.get('return_timestamps', False))
        # Преобразуем строковое значение в булево, если необходимо
        if isinstance(return_timestamps, str):
            return_timestamps = return_timestamps.lower() in ('true', 't', 'yes', 'y', '1')

        # Временно изменяем настройку return_timestamps в транскрайбере
        original_return_timestamps = self.transcriber.return_timestamps
        self.transcriber.return_timestamps = return_timestamps

        # Сохраняем файл во временный файл
        from .file_manager import temp_file_manager
        with temp_file_manager.temp_file() as temp_file_path:
            file.save(temp_file_path)

            # Определяем длительность аудиофайла
            try:
                duration = AudioUtils.get_audio_duration(temp_file_path)
            except Exception as e:
                logger.error(f"Ошибка при определении длительности файла: {e}")
                return {"error": f"Не удалось определить длительность аудиофайла: {e}"}, 500

            # Для файлов из внешних источников (URL, base64), закрываем их и выполняем очистку
            if hasattr(source, 'cleanup'):
                file.file.close()  # Закрываем файловый объект
                source.cleanup()  # Очищаем временные файлы источника

            try:
                start_time = time.time()
                result = self.transcriber.process_file(temp_file_path)
                processing_time = time.time() - start_time

                # Формируем ответ в зависимости от return_timestamps
                if return_timestamps:
                    response = {
                        "segments": result.get("segments", []),
                        "text": result.get("text", ""),
                        "processing_time": processing_time,
                        "response_size_bytes": len(str(result).encode('utf-8')),
                        "duration_seconds": duration,
                        "model": os.path.basename(self.config["model_path"])
                    }
                else:
                    # Если не запрашивались временные метки, result - это строка
                    response = {
                        "text": result,
                        "processing_time": processing_time,
                        "response_size_bytes": len(str(result).encode('utf-8')),
                        "duration_seconds": duration,
                        "model": os.path.basename(self.config["model_path"])
                    }

                # Журналирование результата
                self.history.save(response, filename)

                return response, 200

            except Exception as e:
                logger.error(f"Ошибка при транскрибации файла '{filename}': {str(e)}")
                logger.error(f"Тип исключения: {type(e).__name__}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return {"error": str(e)}, 500

            finally:
                # Восстанавливаем оригинальное значение return_timestamps
                self.transcriber.return_timestamps = original_return_timestamps
