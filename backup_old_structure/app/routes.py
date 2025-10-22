"""
Модуль routes.py содержит классы для регистрации маршрутов API
для сервиса распознавания речи.
"""

import os
from flask import request, jsonify
from typing import Dict

from .transcriber_service import TranscriptionService
from .audio_sources import (
    UploadedFileSource,
    URLSource,
    Base64Source,
    LocalFileSource
)
from .validators import ValidationError
from .async_tasks import transcribe_audio_async, task_manager
from .cache import model_cache
from .utils import logger, log_invalid_file_request


class Routes:
    """
    Класс для регистрации всех эндпоинтов API.
    
    Attributes:
        app (Flask): Flask-приложение.
        config (Dict): Словарь с конфигурацией.
        transcription_service (TranscriptionService): Сервис транскрибации.
        file_validator (FileValidator): Валидатор файлов.
    """

    def __init__(self, app, transcriber, config: Dict, file_validator):
        """
        Инициализация маршрутов.

        Args:
            app: Flask-приложение.
            transcriber: Экземпляр транскрайбера.
            config: Словарь с конфигурацией.
            file_validator: Валидатор файлов.
        """
        self.app = app
        self.config = config
        self.transcription_service = TranscriptionService(transcriber, config)
        self.file_validator = file_validator

        # Регистрация маршрутов
        self._register_routes()

    def _register_routes(self) -> None:
        """
        Регистрация всех эндпоинтов.
        """
        @self.app.route('/', methods=['GET'])
        def index():
            """Корень. Отдаёт HTML клиент."""
            return self.app.send_static_file('index.html')

        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Эндпоинт для проверки статуса сервиса."""
            return jsonify({
                "status": "ok",
                "version": self.config.get("version", "1.0.0")
            }), 200

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
            
            # Валидация пути к файлу
            try:
                validated_path = self.file_validator.validate_local_file_path(
                    file_path, 
                    allowed_directories=self.config.get("allowed_directories", [])
                )
            except ValidationError as e:
                # Логирование обращения к API с невалидным путем к файлу
                client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
                logger.warning(f"Обращение к эндпоинту /local/transcriptions с невалидным путем к файлу '{file_path}' "
                              f"от клиента {client_ip}. Ошибка: {str(e)}")
                return jsonify({"error": str(e)}), 400
            
            source = LocalFileSource(validated_path, self.config.get("file_validation", {}).get("max_file_size_mb", 100))
            response, status_code = self.transcription_service.transcribe_from_source(source, data)
            return jsonify(response), status_code

        @self.app.route('/v1/models', methods=['GET'])
        def list_models():
            """Эндпоинт для получения списка доступных моделей."""
            return jsonify({
                "data": [
                    {
                        "id": os.path.basename(self.config["model_path"]),
                        "object": "model",
                        "owned_by": "openai",
                        "permissions": []
                    }
                ],
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
            else:
                return jsonify({
                    "error": "Model not found",
                    "details": f"Model '{model_id}' does not exist"
                }), 404

        def _handle_transcription_request():
            """Общая функция для обработки запросов транскрибации."""
            source = UploadedFileSource(request.files, self.config.get("file_validation", {}).get("max_file_size_mb", 100))
            response, status_code = self.transcription_service.transcribe_from_source(source, request.form, self.file_validator)
            return jsonify(response), status_code

        @self.app.route('/v1/audio/transcriptions', methods=['POST'])
        @log_invalid_file_request
        def openai_transcribe_endpoint():
            """Эндпоинт для транскрибации аудиофайла (multipart-форма)."""
            return _handle_transcription_request()

        @self.app.route('/v1/audio/transcriptions/url', methods=['POST'])
        @log_invalid_file_request
        def transcribe_from_url():
            """Эндпоинт для транскрибации аудиофайла по URL."""
            data = request.json

            if not data or "url" not in data:
                return jsonify({
                    "error": "No URL provided",
                    "details": "Please provide 'url' in the JSON request"
                }), 400

            url = data["url"]
            # Извлекаем параметры транскрибации, если они есть
            params = {k: v for k, v in data.items() if k != "url"}

            source = URLSource(url, self.config.get("file_validation", {}).get("max_file_size_mb", 100))
            response, status_code = self.transcription_service.transcribe_from_source(source, params, self.file_validator)
            return jsonify(response), status_code

        @self.app.route('/v1/audio/transcriptions/base64', methods=['POST'])
        @log_invalid_file_request
        def transcribe_from_base64():
            """Эндпоинт для транскрибации аудио, закодированного в base64."""
            data = request.json

            if not data or "file" not in data:
                return jsonify({
                    "error": "No base64 file provided",
                    "details": "Please provide 'file' in the JSON request"
                }), 400

            base64_data = data["file"]
            # Извлекаем параметры транскрибации, если они есть
            params = {k: v for k, v in data.items() if k != "file"}

            source = Base64Source(base64_data, self.config.get("file_validation", {}).get("max_file_size_mb", 100))
            response, status_code = self.transcription_service.transcribe_from_source(source, params, self.file_validator)
            return jsonify(response), status_code

        @self.app.route('/v1/audio/transcriptions/multipart', methods=['POST'])
        @log_invalid_file_request
        def transcribe_multipart():
            """Эндпоинт для транскрибации аудиофайла, загруженного через форму."""
            return _handle_transcription_request()
        
        @self.app.route('/v1/audio/transcriptions/async', methods=['POST'])
        @log_invalid_file_request
        def transcribe_async():
            """Эндпоинт для асинхронной транскрибации аудиофайла."""
            source = UploadedFileSource(request.files, self.config.get("file_validation", {}).get("max_file_size_mb", 100))
            
            # Получаем файл
            file, filename, error = source.get_audio_file()
            
            if error:
                return jsonify({"error": error}), 400
            
            if not file:
                return jsonify({"error": "Failed to get audio file"}), 400
            
            # Валидация файла
            try:
                self.file_validator.validate_file(file, filename)
            except ValidationError as e:
                return jsonify({"error": str(e)}), 400
            
            # Сохраняем файл во временный файл
            from .file_manager import temp_file_manager
            with temp_file_manager.temp_file() as temp_path:
                file.save(temp_path)
                
                # Запускаем асинхронную транскрибацию
                task_id = transcribe_audio_async(temp_path, self.transcription_service.transcriber)
                
                return jsonify({"task_id": task_id}), 202
        
        @self.app.route('/v1/tasks/<task_id>', methods=['GET'])
        def get_task_status(task_id):
            """Эндпоинт для получения статуса асинхронной задачи."""
            task_info = task_manager.get_task_status(task_id)
            
            if not task_info:
                return jsonify({"error": "Task not found"}), 404
            
            response = {
                "task_id": task_id,
                "status": task_info["status"]
            }
            
            if task_info["status"] == "completed":
                response["result"] = task_info["result"]
            elif task_info["status"] == "failed":
                response["error"] = task_info["error"]
            
            return jsonify(response)
