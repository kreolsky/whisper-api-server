"""
Модуль transcription_service.py — сервис транскрибации аудиофайлов.
Таймаут реализован через threading.Thread + Event (Semaphore в транскрайберах
контролирует параллелизм).
"""

import time
import threading
import traceback
from typing import Dict, Tuple
import logging

from .config import AppConfig
from ..history import save_history

logger = logging.getLogger('app.transcription_service')


class TranscriptionService:
    """Сервис для транскрибации аудиофайлов."""

    def __init__(self, transcriber, config: AppConfig):
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
        language = params.get('language') or self.config.model.get('language', 'en')
        temperature = max(0.0, min(1.0, float(params.get('temperature', 0.0))))
        prompt = params.get('prompt', '')

        return_timestamps = params.get('return_timestamps', self.config.return_timestamps)
        if isinstance(return_timestamps, str):
            return_timestamps = return_timestamps.lower() in ('true', 't', 'yes', 'y', '1')

        try:
            start_time = time.time()
            timeout = self.config.transcription_timeout_s

            result_box = [None, None]
            done = threading.Event()

            def _run():
                try:
                    result_box[0] = self.transcriber.process_file(
                        file_path, return_timestamps=return_timestamps,
                        language=language, temperature=temperature,
                        prompt=prompt
                    )
                except Exception as exc:
                    result_box[1] = exc
                finally:
                    done.set()

            worker = threading.Thread(target=_run, daemon=True)
            worker.start()

            if not done.wait(timeout=timeout):
                logger.error("Транскрибация превысила таймаут %ds: %s", timeout, filename)
                return {"error": f"Transcription timed out after {timeout}s"}, 504

            if result_box[1] is not None:
                raise result_box[1]

            result, duration = result_box[0]
            processing_time = time.time() - start_time

            if return_timestamps:
                response = {
                    "segments": result.get("segments", []),
                    "text": result.get("text", ""),
                    "processing_time": processing_time,
                    "duration_seconds": duration,
                    "model": self.config.model_type
                }
            else:
                response = {
                    "text": result,
                    "processing_time": processing_time,
                    "duration_seconds": duration,
                    "model": self.config.model_type
                }

            save_history(response, filename, self.config)
            return response, 200

        except Exception as e:
            logger.error("Ошибка при транскрибации файла '%s': %s", filename, e)
            logger.error("Traceback: %s", traceback.format_exc())
            return {"error": str(e)}, 500
