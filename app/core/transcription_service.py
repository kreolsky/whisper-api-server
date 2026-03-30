"""
Модуль transcription_service.py содержит класс TranscriptionService,
который отвечает за транскрибацию аудиофайлов.
"""

import json
import os
import time
import traceback
from typing import Dict, Tuple
import logging

from ..audio.utils import get_audio_duration
from ..history import save_history

logger = logging.getLogger('app.transcription_service')


class TranscriptionService:
    """Сервис для транскрибации аудиофайлов."""

    def __init__(self, transcriber, config: Dict):
        self.transcriber = transcriber
        self.config = config

    def transcribe(self, file_path: str, filename: str, params: Dict = None) -> Tuple[Dict, int]:
        """
        Транскрибирует аудиофайл по пути.

        Args:
            file_path: Путь к аудиофайлу.
            filename: Имя файла (для логов и истории).
            params: Дополнительные параметры для транскрибации.

        Returns:
            Кортеж (JSON-ответ, HTTP-код).
        """
        params = params or {}
        language = params.get('language') or self.config.get('language', 'en')
        temperature = max(0.0, min(1.0, float(params.get('temperature', 0.0))))
        prompt = params.get('prompt', '')

        # Проверяем, запрошены ли временные метки
        return_timestamps = params.get('return_timestamps', self.config.get('return_timestamps', False))
        if isinstance(return_timestamps, str):
            return_timestamps = return_timestamps.lower() in ('true', 't', 'yes', 'y', '1')

        try:
            # Определяем длительность аудиофайла
            try:
                duration = get_audio_duration(file_path)
            except Exception as e:
                logger.error("Ошибка при определении длительности файла: %s", e)
                return {"error": f"Не удалось определить длительность аудиофайла: {e}"}, 500

            start_time = time.time()
            result = self.transcriber.process_file(
                file_path, return_timestamps=return_timestamps,
                language=language, temperature=temperature,
                prompt=prompt
            )
            processing_time = time.time() - start_time

            # Формируем ответ
            if return_timestamps:
                response = {
                    "segments": result.get("segments", []),
                    "text": result.get("text", ""),
                    "processing_time": processing_time,
                    "response_size_bytes": 0,
                    "duration_seconds": duration,
                    "model": os.path.basename(self.config["model_path"])
                }
            else:
                response = {
                    "text": result,
                    "processing_time": processing_time,
                    "response_size_bytes": 0,
                    "duration_seconds": duration,
                    "model": os.path.basename(self.config["model_path"])
                }

            response["response_size_bytes"] = len(json.dumps(response, ensure_ascii=False).encode('utf-8'))

            save_history(response, filename, self.config)
            return response, 200

        except Exception as e:
            logger.error("Ошибка при транскрибации файла '%s': %s", filename, e)
            logger.error("Traceback: %s", traceback.format_exc())
            return {"error": str(e)}, 500
