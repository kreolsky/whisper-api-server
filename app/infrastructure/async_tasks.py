"""
Модуль async_tasks.py содержит функции для асинхронной обработки задач.
"""

import copy
import uuid
import time
from typing import Dict, Any, Callable, Optional
from threading import Thread, Lock
import logging

logger = logging.getLogger('app.async_tasks')


class AsyncTaskManager:
    """
    Менеджер асинхронных задач на основе потоков.
    
    Attributes:
        tasks (Dict): Словарь для хранения информации о задачах.
    """
    
    TASK_TTL = 3600  # 1 час

    def __init__(self):
        """
        Инициализация менеджера асинхронных задач.
        """
        self._lock = Lock()
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._start_cleanup_thread()
    
    def run_task(self, func: Callable, *args, **kwargs) -> str:
        """
        Запуск задачи в отдельном потоке.
        
        Args:
            func: Функция для выполнения.
            *args: Позиционные аргументы для функции.
            **kwargs: Именованные аргументы для функции.
            
        Returns:
            ID задачи.
        """
        task_id = str(uuid.uuid4())

        with self._lock:
            self._cleanup_old_tasks()
            self.tasks[task_id] = {
                "status": "pending",
                "result": None,
                "error": None,
                "created_at": time.time(),
                "started_at": None,
                "completed_at": None
            }

        thread = Thread(target=self._run_task_thread, args=(task_id, func, args, kwargs))
        thread.daemon = True
        thread.start()

        return task_id

    def _cleanup_old_tasks(self) -> None:
        """Удаляет завершённые задачи старше TASK_TTL. Вызывать под self._lock."""
        now = time.time()
        expired = [
            tid for tid, info in self.tasks.items()
            if info["completed_at"] and now - info["completed_at"] > self.TASK_TTL
        ]
        for tid in expired:
            del self.tasks[tid]
    
    def _run_task_thread(self, task_id: str, func: Callable, args: tuple, kwargs: dict) -> None:
        """
        Функция для выполнения задачи в потоке.
        
        Args:
            task_id: ID задачи.
            func: Функция для выполнения.
            args: Позиционные аргументы для функции.
            kwargs: Именованные аргументы для функции.
        """
        with self._lock:
            self.tasks[task_id]["status"] = "running"
            self.tasks[task_id]["started_at"] = time.time()

        try:
            result = func(*args, **kwargs)

            with self._lock:
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["result"] = result
                self.tasks[task_id]["completed_at"] = time.time()

            logger.info("Задача %s завершена успешно", task_id)
        except Exception as e:
            with self._lock:
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["error"] = str(e)
                self.tasks[task_id]["completed_at"] = time.time()

            logger.error("Задача %s завершилась с ошибкой: %s", task_id, e)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение статуса задачи.
        
        Args:
            task_id: ID задачи.
            
        Returns:
            Информация о задаче или None, если задача не найдена.
        """
        with self._lock:
            task = self.tasks.get(task_id)
            return copy.deepcopy(task) if task else None

    def _start_cleanup_thread(self) -> None:
        """Запуск фонового потока для периодической очистки старых задач."""
        def _cleanup_loop():
            while True:
                time.sleep(600)  # Каждые 10 минут
                with self._lock:
                    self._cleanup_old_tasks()

        thread = Thread(target=_cleanup_loop, daemon=True)
        thread.start()


# Глобальный экземпляр менеджера асинхронных задач
task_manager = AsyncTaskManager()


def transcribe_audio_async(file_path: str, transcription_service, params: Dict = None) -> str:
    """
    Асинхронная транскрибация аудиофайла.
    
    Args:
        file_path: Путь к аудиофайлу.
        transcription_service: Экземпляр TranscriptionService.
        params: Параметры транскрибации.
        
    Returns:
        ID задачи.
    """
    params = params or {}
    def _transcribe():
        return transcription_service.transcribe(file_path, "async_task", params)
    return task_manager.run_task(_transcribe)