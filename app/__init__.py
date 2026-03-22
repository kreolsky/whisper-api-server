"""
Главный модуль приложения, содержащий класс WhisperServiceAPI для инициализации
и запуска сервиса распознавания речи.
"""

import os
import logging
from flask import Flask
from flask_cors import CORS
from typing import Dict
import waitress

from .core.transcriber import WhisperTranscriber
from .core.config import load_config
from .routes import Routes
from .infrastructure.validation import FileValidator
from .infrastructure.log import setup_logging, RequestLogger


class WhisperServiceAPI:
    """
    Класс для API сервиса распознавания речи.
    
    Attributes:
        config (Dict): Словарь с параметрами конфигурации.
        port (int): Порт для сервиса.
        transcriber (WhisperTranscriber): Экземпляр транскрайбера.
        app (Flask): Flask-приложение.
        file_validator (FileValidator): Валидатор файлов.
    """

    def __init__(self, config_path: str):
        """
        Инициализация API сервиса.

        Args:
            config_path: Путь к конфигурационному файлу.
        """
        # Загрузка конфигурации
        self.config = load_config(config_path)
        
        # Установка уровня логирования
        log_level = getattr(logging, self.config.get('log_level', 'INFO').upper())
        log_file = self.config.get('log_file')
        setup_logging(log_level=log_level, log_file=log_file)
        
        # Получаем логгер для этого модуля
        self.logger = logging.getLogger('app')
        self.logger.info("Инициализация WhisperServiceAPI")
        
        # Инициализация Flask приложения
        self.app = Flask(__name__)
        CORS(self.app)
        self.port = self.config["service_port"]
        
        # Инициализация компонентов
        self.transcriber = WhisperTranscriber(self.config)
        self.file_validator = FileValidator(self.config)
        
        # Настройка логирования запросов
        request_logger_config = self.config.get('request_logging', {})
        request_logger = RequestLogger(self.app, request_logger_config)
        
        # Регистрация маршрутов
        routes = Routes(self.app, self.transcriber, self.config, self.file_validator)
        
        self.logger.info("WhisperServiceAPI успешно инициализирован")

    def run(self) -> None:
        """Запуск сервиса через Waitress."""
        self.logger.info(f"Запуск сервиса на 0.0.0.0:{self.port}")
        waitress.serve(self.app, host='0.0.0.0', port=self.port)

    def create_app(self) -> Flask:
        """
        Создание и настройка Flask приложения (для использования с WSGI серверами).
        
        Returns:
            Настроенное Flask приложение.
        """
        return self.app