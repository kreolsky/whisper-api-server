"""
Главный модуль приложения, содержащий класс WhisperServiceAPI для инициализации
и запуска сервиса распознавания речи.
"""

__all__ = ['WhisperServiceAPI']

import os
import signal
import threading
import logging
from flask import Flask
from flask_cors import CORS
import waitress

from .core import create_transcriber
from .core.config import load_config
from .routes import Routes
from .infrastructure.validation import FileValidator
from .infrastructure.log import setup_logging, RequestLogger
from .infrastructure.async_tasks import AsyncTaskManager


class WhisperServiceAPI:
    """
    Класс для API сервиса распознавания речи.

    Attributes:
        config: Типизированная конфигурация (AppConfig).
        port: Порт для сервиса.
        transcriber: Экземпляр транскрайбера.
        app: Flask-приложение.
        file_validator: Валидатор файлов.
    """

    def __init__(self, config_path: str):
        """
        Инициализация API сервиса.

        Args:
            config_path: Путь к конфигурационному файлу.
        """
        self.config = load_config(config_path)

        log_level = getattr(logging, self.config.log_level.upper())
        setup_logging(log_level=log_level, log_file=self.config.log_file)

        self.logger = logging.getLogger('app')
        self.logger.info("Инициализация WhisperServiceAPI")

        self.app = Flask(__name__)
        CORS(self.app)
        self.port = self.config.service_port

        self.transcriber = create_transcriber(self.config)
        self.file_validator = FileValidator(self.config)
        self.task_manager = AsyncTaskManager()
        self._shutting_down = False
        self._shutdown_timeout = self.config.shutdown_timeout_s
        self._shutdown_event = threading.Event()

        request_logger = RequestLogger(self.app, self.config.request_logging)

        routes = Routes(self.app, self.transcriber, self.config, self.file_validator, self.task_manager)

        self.logger.info("WhisperServiceAPI успешно инициализирован")

    def _handle_shutdown(self, signum, frame):
        """Обработчик SIGTERM/SIGINT для graceful shutdown."""
        if self._shutting_down:
            self.logger.warning("Повторный сигнал завершения — принудительный выход")
            os._exit(1)
        self._shutting_down = True
        self.logger.info("Получен сигнал завершения (%s), ожидание завершения активных запросов (таймаут %ds)...",
                         signal.Signals(signum).name, self._shutdown_timeout)
        self._shutdown_event.set()

    def run(self) -> None:
        """Запуск сервиса через Waitress."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        self.logger.info("Запуск сервиса на 0.0.0.0:%s", self.port)

        channel_timeout = self.config.channel_timeout_s

        serve_thread = threading.Thread(
            target=waitress.serve,
            kwargs=dict(
                app=self.app,
                host='0.0.0.0',
                port=self.port,
                channel_timeout=channel_timeout,
            ),
            daemon=True,
        )
        serve_thread.start()

        self._shutdown_event.wait()
        self.logger.info("Ожидание завершения активных запросов (таймаут %ds)...", self._shutdown_timeout)
        serve_thread.join(timeout=self._shutdown_timeout)

        if serve_thread.is_alive():
            self.logger.warning("Таймаут graceful shutdown — принудительный выход")
        else:
            self.logger.info("Все запросы завершены — остановка сервиса")

        os._exit(0)

    def create_app(self) -> Flask:
        """
        Создание и настройка Flask приложения (для использования с WSGI серверами).

        Returns:
            Настроенное Flask приложение.
        """
        return self.app
