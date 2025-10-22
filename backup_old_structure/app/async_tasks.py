"""
Модуль async_tasks.py содержит функции для асинхронной обработки задач.
"""

import uuid
import time
from typing import Dict, Any, Callable, Optional
from threading import Thread
from .utils import logger


class AsyncTaskManager:
    """
    Менеджер асинхронных задач на основе потоков.
    
    Attributes:
        tasks (Dict): Словарь для хранения информации о задачах.
    """
    
    def __init__(self):
        """
        Инициализация менеджера асинхронных задач.
        """
        self.tasks: Dict[str, Dict[str, Any]] = {}
    
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
        
        # Создание информации о задаче
        self.tasks[task_id] = {
            "status": "pending",
            "result": None,
            "error": None,
            "created_at": time.time(),
            "started_at": None,
            "completed_at": None
        }
        
        # Создание и запуск потока
        thread = Thread(target=self._run_task_thread, args=(task_id, func, args, kwargs))
        thread.daemon = True
        thread.start()
        
        return task_id
    
    def _run_task_thread(self, task_id: str, func: Callable, args: tuple, kwargs: dict) -> None:
        """
        Функция для выполнения задачи в потоке.
        
        Args:
            task_id: ID задачи.
            func: Функция для выполнения.
            args: Позиционные аргументы для функции.
            kwargs: Именованные аргументы для функции.
        """
        try:
            # Обновление статуса задачи
            self.tasks[task_id]["status"] = "running"
            self.tasks[task_id]["started_at"] = time.time()
            
            # Выполнение функции
            result = func(*args, **kwargs)
            
            # Сохранение результата
            self.tasks[task_id]["status"] = "completed"
            self.tasks[task_id]["result"] = result
            self.tasks[task_id]["completed_at"] = time.time()
            
            logger.info(f"Задача {task_id} завершена успешно")
        except Exception as e:
            # Обработка ошибки
            self.tasks[task_id]["status"] = "failed"
            self.tasks[task_id]["error"] = str(e)
            self.tasks[task_id]["completed_at"] = time.time()
            
            logger.error(f"Задача {task_id} завершилась с ошибкой: {e}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение статуса задачи.
        
        Args:
            task_id: ID задачи.
            
        Returns:
            Информация о задаче или None, если задача не найдена.
        """
        return self.tasks.get(task_id)
    
    def cleanup_completed_tasks(self, max_age_seconds: int = 3600) -> None:
        """
        Очистка завершенных задач старше указанного возраста.
        
        Args:
            max_age_seconds: Максимальный возраст задачи в секундах.
        """
        current_time = time.time()
        tasks_to_remove = []
        
        for task_id, task_info in self.tasks.items():
            if (task_info["status"] in ["completed", "failed"] and 
                "completed_at" in task_info and 
                current_time - task_info["completed_at"] > max_age_seconds):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
            logger.debug(f"Задача {task_id} удалена из-за устаревания")


# Глобальный экземпляр менеджера асинхронных задач
task_manager = AsyncTaskManager()


def transcribe_audio_async(file_path: str, transcriber) -> str:
    """
    Асинхронная транскрибация аудиофайла.
    
    Args:
        file_path: Путь к аудиофайлу.
        transcriber: Экземпляр транскрайбера.
        
    Returns:
        ID задачи.
    """
    return task_manager.run_task(transcriber.process_file, file_path)