"""
Модуль routes.py — регистрация маршрутов API.
"""

from __future__ import annotations

import logging
from typing import Dict, TYPE_CHECKING

from flask import Flask, request, jsonify

from .core.config import AppConfig, config_to_public_dict
from .core.transcription_service import TranscriptionService
from .audio.sources import get_uploaded_file, get_url_file, get_base64_file
from .infrastructure.validation import ValidationError
from .infrastructure.storage import cleanup_temp_files
from .infrastructure.async_tasks import AsyncTaskManager

if TYPE_CHECKING:
    from .core.base import Transcriber
    from .infrastructure.validation import FileValidator

logger = logging.getLogger('app.routes')


class Routes:
    """Класс для регистрации всех эндпоинтов API."""

    def __init__(self, app: Flask, transcriber: Transcriber,
                 config: AppConfig, file_validator: FileValidator,
                 task_manager: AsyncTaskManager):
        self.app = app
        self.config = config
        self.transcription_service = TranscriptionService(transcriber, config)
        self.file_validator = file_validator
        self.task_manager = task_manager
        self._max_size = config.file_validation.max_file_size_mb
        self._register_routes()

    def _transcribe_and_respond(self, temp_path: str, filename: str, params: Dict):
        """Общий пайплайн валидации → транскрибации → ответа с cleanup."""
        try:
            self.file_validator.validate_file_by_path(temp_path, filename)
            response, status_code = self.transcription_service.transcribe(temp_path, filename, params)
            return jsonify(response), status_code
        except ValidationError as e:
            logger.warning("Ошибка валидации файла '%s': %s", filename, e)
            return jsonify({"error": str(e)}), 400
        finally:
            cleanup_temp_files([temp_path])

    def _register_routes(self) -> None:
        @self.app.route('/', methods=['GET'])
        def index():
            """Корень. Отдаёт HTML клиент."""
            return self.app.send_static_file('index.html')

        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Эндпоинт для проверки статуса сервиса."""
            if not self.transcription_service.transcriber.is_ready:
                return jsonify({"status": "unhealthy", "error": "Model not loaded"}), 503
            return jsonify({
                "status": "ok",
                "version": self.config.version,
                "model": self.config.model_type
            }), 200

        @self.app.route('/config', methods=['GET'])
        def get_config():
            """Эндпоинт для получения безопасной конфигурации сервиса."""
            return jsonify(config_to_public_dict(self.config)), 200

        @self.app.route('/v1/models', methods=['GET'])
        def list_models():
            """Эндпоинт для получения списка доступных моделей."""
            model_id = self.config.model_type
            return jsonify({
                "data": [{
                    "id": model_id,
                    "object": "model",
                    "owned_by": "ai-sage" if model_id == "gigaam" else "openai",
                    "permissions": []
                }],
                "object": "list"
            }), 200

        @self.app.route('/v1/models/<model_id>', methods=['GET'])
        def retrieve_model(model_id):
            """Эндпоинт для получения информации о конкретной модели."""
            active_id = self.config.model_type
            if model_id == active_id:
                return jsonify({
                    "id": model_id,
                    "object": "model",
                    "owned_by": "ai-sage" if model_id == "gigaam" else "openai",
                    "permissions": []
                }), 200
            return jsonify({
                "error": "Model not found",
                "details": f"Model '{model_id}' does not exist"
            }), 404

        @self.app.route('/v1/audio/transcriptions', methods=['POST'])
        def openai_transcribe_endpoint():
            """Эндпоинт для транскрибации аудиофайла (multipart-форма)."""
            temp_path, filename, error = get_uploaded_file(request.files, self._max_size)
            if error:
                return jsonify({"error": error}), 400
            return self._transcribe_and_respond(temp_path, filename, dict(request.form))

        @self.app.route('/v1/audio/transcriptions/url', methods=['POST'])
        def transcribe_from_url():
            """Эндпоинт для транскрибации аудиофайла по URL."""
            data = request.json

            if not data or "url" not in data:
                return jsonify({
                    "error": "No URL provided",
                    "details": "Please provide 'url' in the JSON request"
                }), 400

            url = data["url"]
            params = {k: v for k, v in data.items() if k != "url"}

            temp_path, filename, error = get_url_file(url, self._max_size)
            if error:
                return jsonify({"error": error}), 400
            return self._transcribe_and_respond(temp_path, filename, params)

        @self.app.route('/v1/audio/transcriptions/base64', methods=['POST'])
        def transcribe_from_base64():
            """Эндпоинт для транскрибации аудио, закодированного в base64."""
            data = request.json

            if not data or "file" not in data:
                return jsonify({
                    "error": "No base64 file provided",
                    "details": "Please provide 'file' in the JSON request"
                }), 400

            base64_data = data["file"]
            params = {k: v for k, v in data.items() if k != "file"}

            temp_path, filename, error = get_base64_file(base64_data, self._max_size)
            if error:
                return jsonify({"error": error}), 400
            return self._transcribe_and_respond(temp_path, filename, params)

        @self.app.route('/v1/audio/transcriptions/async', methods=['POST'])
        def transcribe_async():
            """Эндпоинт для асинхронной транскрибации аудиофайла."""
            temp_path, filename, error = get_uploaded_file(request.files, self._max_size)
            if error:
                return jsonify({"error": error}), 400

            try:
                self.file_validator.validate_file_by_path(temp_path, filename)
            except ValidationError as e:
                cleanup_temp_files([temp_path])
                return jsonify({"error": str(e)}), 400

            params = dict(request.form)

            def _do_async_transcribe():
                try:
                    return self.transcription_service.transcribe(temp_path, "async_task", params)
                finally:
                    cleanup_temp_files([temp_path])

            task_id = self.task_manager.run_task(_do_async_transcribe)
            return jsonify({"task_id": task_id}), 202

        @self.app.route('/v1/tasks/<task_id>', methods=['GET'])
        def get_task_status(task_id):
            """Эндпоинт для получения статуса асинхронной задачи."""
            task_info = self.task_manager.get_task_status(task_id)

            if not task_info:
                return jsonify({"error": "Task not found"}), 404

            response = {"task_id": task_id, "status": task_info["status"]}

            if task_info["status"] == "completed":
                response["result"] = task_info["result"]
            elif task_info["status"] == "failed":
                response["error"] = task_info["error"]

            return jsonify(response)
