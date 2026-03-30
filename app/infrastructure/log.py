"""
Настройка логирования и middleware для логирования HTTP-запросов.
"""

import os
import time
import logging
from logging.handlers import RotatingFileHandler
from flask import request, g
from typing import Dict, Optional


def setup_logging(log_level=logging.INFO, log_file=None):
    """
    Настройка логирования для всего приложения.

    Args:
        log_level: Уровень логирования (по умолчанию INFO).
        log_file: Путь к файлу для записи логов (опционально).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Очищаем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    class CustomFormatter(logging.Formatter):
        def format(self, record):
            if not hasattr(record, 'type'):
                record.type = 'general'
            return super().format(record)

    formatter = CustomFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(type)s] %(message)s'
    )

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Файловый обработчик
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    logging.getLogger('app').setLevel(log_level)
    logging.getLogger('app.request').setLevel(log_level)

    return root_logger


class RequestLogger:
    """Middleware для логирования HTTP-запросов и ответов."""

    def __init__(self, app=None, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger('app.request')
        self.exclude_endpoints = set(self.config.get('exclude_endpoints', ['/health', '/static']))

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Регистрация middleware в Flask-приложении."""
        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def _should_log(self) -> bool:
        for excluded in self.exclude_endpoints:
            if request.path.startswith(excluded):
                return False
        return True

    def _get_client_ip(self) -> str:
        return (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
                or request.headers.get('X-Real-IP')
                or request.remote_addr
                or 'unknown')

    def _before_request(self):
        if not self._should_log():
            return
        g.start_time = time.time()
        self.logger.info(
            "%s %s от %s",
            request.method, request.path, self._get_client_ip(),
            extra={"type": "request"}
        )

    def _after_request(self, response):
        if not self._should_log():
            return response
        processing_time = time.time() - getattr(g, 'start_time', time.time())
        self.logger.info(
            "%s за %.3f сек",
            response.status_code, processing_time,
            extra={"type": "response"}
        )
        return response
