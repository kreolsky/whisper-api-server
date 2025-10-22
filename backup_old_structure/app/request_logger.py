"""
Модуль request_logger.py содержит middleware для логирования входящих запросов и ответов.
"""

import time
import json
import logging
from flask import request, g
from typing import Dict, Any, Optional


class RequestLogger:
    """
    Middleware для логирования входящих запросов и ответов.
    """
    
    def __init__(self, app=None, config: Optional[Dict] = None):
        self.app = app
        self.config = config or {}
        self.logger = logging.getLogger('app.request')
        
        # Чувствительные заголовки для фильтрации
        self.sensitive_headers = set(self.config.get(
            'sensitive_headers',
            ['authorization', 'cookie', 'set-cookie', 'proxy-authorization', 'x-api-key']
        ))
        
        # Эндпоинты для исключения из логирования
        self.exclude_endpoints = set(self.config.get('exclude_endpoints', ['/health', '/static']))
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Инициализация middleware с Flask приложением."""
        app.before_request(self._before_request)
        app.after_request(self._after_request)
    
    def _should_log_request(self) -> bool:
        """Проверка, нужно ли логировать текущий запрос."""
        # Проверяем, исключен ли эндпоинт
        path = request.path
        for excluded in self.exclude_endpoints:
            if path.startswith(excluded):
                return False
        
        return True
    
    def _before_request(self):
        """Логирование входящего запроса."""
        if not self._should_log_request():
            return
        
        g.start_time = time.time()
        
        # Определяем режим логирования
        debug_mode = self.config.get('log_debug', False)
        
        # Сбор информации о запросе
        request_info = self._extract_request_info(debug=debug_mode)
        
        # Логирование в зависимости от режима
        if debug_mode:
            self._log_debug_request(request_info)
        else:
            message = self._format_request_message(request_info)
            self.logger.info(
                message,
                extra={"type": "request"}
            )
    
    def _after_request(self, response):
        """Логирование ответа."""
        if not self._should_log_request():
            return response
        
        # Расчет времени обработки
        processing_time = time.time() - getattr(g, 'start_time', time.time())
        
        # Определяем режим логирования
        debug_mode = self.config.get('log_debug', False)
        
        # Логирование в зависимости от режима
        if debug_mode:
            self._log_debug_response(response, processing_time)
        else:
            message = self._format_response_message(response, processing_time)
            self.logger.info(
                message,
                extra={"type": "response"}
            )
        
        return response
    
    def _extract_request_info(self, debug: bool = False) -> Dict[str, Any]:
        """Извлечение информации о запросе."""
        # Базовая информация
        info = {
            "endpoint": request.endpoint or str(request.url_rule),
            "method": request.method,
            "path": request.path,
            "client_ip": self._get_client_ip(),
            "user_agent": request.headers.get('User-Agent', 'Unknown')
        }
        
        # Параметры запроса
        if request.args:
            info["query_params"] = dict(request.args)
        
        # Данные формы (исключая файлы)
        if request.form:
            info["form_data"] = dict(request.form)
        
        # JSON данные
        if request.is_json:
            try:
                info["json_data"] = request.get_json()
            except Exception:
                info["json_data"] = "Invalid JSON"
        
        # Информация о файлах
        if request.files:
            file_info = {}
            for key, file in request.files.items():
                file_info[key] = {
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "content_length": len(file.read()) if file else 0
                }
                file.seek(0)  # Возвращаем указатель файла
            info["files"] = file_info
        
        # Заголовки
        if debug:
            # В отладочном режиме логируем все заголовки
            headers = dict(request.headers)
        else:
            # В обычном режиме фильтруем чувствительные заголовки
            headers = {}
            for key, value in request.headers:
                if key.lower() not in self.sensitive_headers:
                    headers[key] = value
        info["headers"] = headers
        
        return info
    
    def _log_debug_request(self, request_info: Dict[str, Any]):
        """Логирование полных данных запроса в отладочном режиме."""
        debug_data = {
            "timestamp": time.time(),
            "type": "request",
            "data": request_info
        }
        self.logger.info(
            "DEBUG REQUEST: %s",
            json.dumps(debug_data, ensure_ascii=False, default=str)
        )
    
    def _log_debug_response(self, response, processing_time: float):
        """Логирование полных данных ответа в отладочном режиме."""
        response_info = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content_length": response.content_length,
            "processing_time": round(processing_time, 3)
        }
        debug_data = {
            "timestamp": time.time(),
            "type": "response",
            "data": response_info
        }
        self.logger.info(
            "DEBUG RESPONSE: %s",
            json.dumps(debug_data, ensure_ascii=False, default=str)
        )
    
    def _format_request_message(self, request_info: Dict[str, Any]) -> str:
        """Форматирование сообщения с деталями запроса."""
        # Базовая информация
        method = request_info.get("method", "UNKNOWN")
        path = request_info.get("path", "/")
        client_ip = request_info.get("client_ip", "unknown")
        user_agent = request_info.get("user_agent", "Unknown")
        
        # Информация о файлах
        file_info = ""
        if "files" in request_info and request_info["files"]:
            file_details = []
            for file_key, file_data in request_info["files"].items():
                filename = file_data.get("filename", "unknown")
                size = file_data.get("content_length", 0)
                file_details.append(f"{filename} ({size} байт)")
            file_info = f" файлы: {', '.join(file_details)}"
        
        # Информация о параметрах (только имена для безопасности)
        param_info = ""
        if "query_params" in request_info and request_info["query_params"]:
            param_names = list(request_info["query_params"].keys())
            param_info = f" параметры: {', '.join(param_names)}"
        elif "form_data" in request_info and request_info["form_data"]:
            param_names = list(request_info["form_data"].keys())
            param_info = f" параметры: {', '.join(param_names)}"
        elif "json_data" in request_info and isinstance(request_info["json_data"], dict):
            param_names = list(request_info["json_data"].keys())
            param_info = f" параметры: {', '.join(param_names)}"
        
        # Формирование полного сообщения
        message = f"{method} {path} от {client_ip} ({user_agent}){file_info}{param_info}"
        
        return message.strip()
    
    def _format_response_message(self, response, processing_time: float) -> str:
        """Форматирование сообщения с деталями ответа."""
        status_code = response.status_code
        content_length = response.content_length or 0
        processing_time_rounded = round(processing_time, 3)
        
        return f"{status_code} за {processing_time_rounded} сек, {content_length} байт"
    
    def _get_client_ip(self) -> str:
        """Получение реального IP адреса клиента."""
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0]
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr or 'unknown'