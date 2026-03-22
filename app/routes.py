"""
Модуль routes.py содержит классы для регистрации маршрутов API
для сервиса распознавания речи.
"""

import os
from flask import request, jsonify
from typing import Dict
import logging

from .core.transcription_service import TranscriptionService
from .audio.sources import get_uploaded_file, get_url_file, get_base64_file, get_local_file
from .infrastructure.validation import ValidationError
from .infrastructure.async_tasks import transcribe_audio_async, task_manager

logger = logging.getLogger('app.routes')


class Routes:
    """Класс для регистрации всех эндпоинтов API."""

    def __init__(self, app, transcriber, config: Dict, file_validator):
        self.app = app
        self.config = config
        self.transcription_service = TranscriptionService(transcriber, config)
        self.file_validator = file_validator
        self._max_size = self.config.get("file_validation", {}).get("max_file_size_mb", 100)
        self._register_routes()

    def _register_routes(self) -> None:
        @self.app.route('/', methods=['GET'])
        def index():
            """Корень. Отдаёт HTML клиент."""
            return self.app.send_static_file('index.html')

        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Эндпоинт для проверки статуса сервиса."""
            return jsonify({"status": "ok", "version": "1.0.0"}), 200

        @self.app.route('/config', methods=['GET'])
        def get_config():
            """Эндпоинт для получения конфигурации сервиса."""
            return jsonify(self.config), 200

        @self.app.route('/local/transcriptions', methods=['POST'])
        def local_transcribe():
            """Эндпоинт для локальной транскрибации файла по пути на сервере."""
            data = request.json

            if not data or "file_path" not in data:
                return jsonify({"error": "No file_path provided"}), 400

            file_path = data["file_path"]

            try:
                validated_path = self.file_validator.validate_local_file_path(
                    file_path,
                    allowed_directories=self.config.get("allowed_directories", [])
                )
            except ValidationError as e:
                client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
                logger.warning(f"Невалидный путь '{file_path}' от {client_ip}: {e}")
                return jsonify({"error": str(e)}), 400

            temp_path, filename, error = get_local_file(validated_path, self._max_size)
            if error:
                return jsonify({"error": error}), 400

            response, status_code = self.transcription_service.transcribe(temp_path, filename, data)
            return jsonify(response), status_code

        @self.app.route('/v1/models', methods=['GET'])
        def list_models():
            """Эндпоинт для получения списка доступных моделей."""
            return jsonify({
                "data": [{
                    "id": os.path.basename(self.config["model_path"]),
                    "object": "model",
                    "owned_by": "openai",
                    "permissions": []
                }],
                "object": "list"
            }), 200

        @self.app.route('/v1/models/<model_id>', methods=['GET'])
        def retrieve_model(model_id):
            """Эндпоинт для получения информации о конкретной модели."""
            if model_id == os.path.basename(self.config["model_path"]):
                return jsonify({
                    "id": model_id,
                    "object": "model",
                    "owned_by": "openai",
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

            # Валидация файла
            try:
                self.file_validator.validate_file_by_path(temp_path, filename)
            except ValidationError as e:
                logger.warning(f"Ошибка валидации файла '{filename}': {e}")
                return jsonify({"error": str(e)}), 400

            response, status_code = self.transcription_service.transcribe(temp_path, filename, dict(request.form))
            return jsonify(response), status_code

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

            try:
                self.file_validator.validate_file_by_path(temp_path, filename)
            except ValidationError as e:
                logger.warning(f"Ошибка валидации файла '{filename}': {e}")
                return jsonify({"error": str(e)}), 400

            response, status_code = self.transcription_service.transcribe(temp_path, filename, params)
            return jsonify(response), status_code

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

            try:
                self.file_validator.validate_file_by_path(temp_path, filename)
            except ValidationError as e:
                logger.warning(f"Ошибка валидации файла '{filename}': {e}")
                return jsonify({"error": str(e)}), 400

            response, status_code = self.transcription_service.transcribe(temp_path, filename, params)
            return jsonify(response), status_code

        @self.app.route('/v1/audio/transcriptions/async', methods=['POST'])
        def transcribe_async():
            """Эндпоинт для асинхронной транскрибации аудиофайла."""
            temp_path, filename, error = get_uploaded_file(request.files, self._max_size)
            if error:
                return jsonify({"error": error}), 400

            try:
                self.file_validator.validate_file_by_path(temp_path, filename)
            except ValidationError as e:
                return jsonify({"error": str(e)}), 400

            task_id = transcribe_audio_async(temp_path, self.transcription_service.transcriber)
            return jsonify({"task_id": task_id}), 202

        @self.app.route('/v1/tasks/<task_id>', methods=['GET'])
        def get_task_status(task_id):
            """Эндпоинт для получения статуса асинхронной задачи."""
            task_info = task_manager.get_task_status(task_id)

            if not task_info:
                return jsonify({"error": "Task not found"}), 404

            response = {"task_id": task_id, "status": task_info["status"]}

            if task_info["status"] == "completed":
                response["result"] = task_info["result"]
            elif task_info["status"] == "failed":
                response["error"] = task_info["error"]

            return jsonify(response)
