"""
Главный модуль приложения, содержащий класс WhisperServiceAPI для инициализации
и запуска сервиса распознавания речи.
"""

import os
import logging
from flask import Flask
from typing import Dict

from .core.transcriber import WhisperTranscriber
from .core.config import load_config
from .api.routes import Routes
from .infrastructure.validation.validators import FileValidator
from .infrastructure.storage.file_manager import temp_file_manager
from .infrastructure.logging.config import setup_logging
from .infrastructure.logging.request_logger import RequestLogger


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
        self.port = self.config.get('port', 5000)
        
        # Инициализация компонентов
        self.transcriber = WhisperTranscriber(self.config)
        self.file_validator = FileValidator(self.config)
        
        # Настройка логирования запросов
        request_logger_config = self.config.get('request_logger', {})
        request_logger = RequestLogger(self.app, request_logger_config)
        
        # Регистрация маршрутов
        routes = Routes(self.app, self.transcriber, self.config, self.file_validator)
        
        # Регистрация обработчиков очистки
        self._register_cleanup_handlers()
        
        self.logger.info("WhisperServiceAPI успешно инициализирован")

    def _register_cleanup_handlers(self) -> None:
        """
        Регистрация обработчиков для очистки ресурсов при завершении приложения.
        """
        @self.app.teardown_appcontext
        def cleanup(error):
            """
            Очистка временных файлов при завершении контекста запроса.
            
            Args:
                error: Ошибка, если она произошла.
            """
            # Выполнение очистки временных файлов, если необходимо
            pass

    def run(self, host: str = '0.0.0.0', debug: bool = False) -> None:
        """
        Запуск Flask приложения.
        
        Args:
            host: Хост для запуска приложения.
            debug: Флаг отладочного режима.
        """
        self.logger.info(f"Запуск сервиса на {host}:{self.port}")
        self.app.run(host=host, port=self.port, debug=debug)

    def create_app(self) -> Flask:
        """
        Создание и настройка Flask приложения (для использования с WSGI серверами).
        
        Returns:
            Настроенное Flask приложение.
        """
        return self.app