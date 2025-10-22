#!/usr/bin/env python3
"""
Скрипт для миграции с старой структуры проекта на новую.
Этот скрипт помогает в процессе перехода на новую архитектуру проекта.
"""

import os
import shutil
import json
from pathlib import Path

def backup_old_structure():
    """Создание резервной копии старой структуры."""
    backup_dir = "backup_old_structure"
    
    if os.path.exists(backup_dir):
        print(f"Директория {backup_dir} уже существует. Пропускаем создание резервной копии.")
        return
    
    print("Создание резервной копии старой структуры...")
    os.makedirs(backup_dir, exist_ok=True)
    
    # Список файлов для резервного копирования
    files_to_backup = [
        "app/__init__.py",
        "app/async_tasks.py",
        "app/audio_processor.py",
        "app/audio_sources.py",
        "app/audio_utils.py",
        "app/cache.py",
        "app/context_managers.py",
        "app/file_manager.py",
        "app/history_logger.py",
        "app/logging_config.py",
        "app/request_logger.py",
        "app/routes.py",
        "app/transcriber_service.py",
        "app/transcriber.py",
        "app/utils.py",
        "app/validators.py"
    ]
    
    for file_path in files_to_backup:
        if os.path.exists(file_path):
            backup_path = os.path.join(backup_dir, file_path)
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(file_path, backup_path)
            print(f"Скопирован файл: {file_path} -> {backup_path}")
    
    print("Резервная копия создана успешно.")

def check_new_structure():
    """Проверка наличия новой структуры."""
    required_dirs = [
        "app/api",
        "app/core",
        "app/audio",
        "app/infrastructure",
        "app/infrastructure/logging",
        "app/infrastructure/storage",
        "app/infrastructure/async_tasks",
        "app/infrastructure/validation",
        "app/shared"
    ]
    
    missing_dirs = []
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            missing_dirs.append(dir_path)
    
    if missing_dirs:
        print("Отсутствуют следующие директории:")
        for dir_path in missing_dirs:
            print(f"  - {dir_path}")
        print("Пожалуйста, сначала создайте новую структуру директорий.")
        return False
    
    print("Новая структура директорий присутствует.")
    return True

def remove_old_files():
    """Удаление старых файлов после успешной миграции."""
    old_files = [
        "app/async_tasks.py",
        "app/audio_processor.py",
        "app/audio_sources.py",
        "app/audio_utils.py",
        "app/cache.py",
        "app/context_managers.py",
        "app/file_manager.py",
        "app/history_logger.py",
        "app/logging_config.py",
        "app/request_logger.py",
        "app/routes.py",
        "app/transcriber_service.py",
        "app/transcriber.py",
        "app/utils.py",
        "app/validators.py"
    ]
    
    print("\nВНИМАНИЕ: Вы собираетесь удалить старые файлы.")
    print("Убедитесь, что новая структура работает корректно.")
    response = input("Продолжить удаление старых файлов? (y/n): ")
    
    if response.lower() != 'y':
        print("Удаление отменено.")
        return
    
    for file_path in old_files:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Удален файл: {file_path}")
    
    print("Старые файлы удалены.")

def create_migration_report():
    """Создание отчета о миграции."""
    report = {
        "migration_status": "completed",
        "old_structure_backed_up": True,
        "new_structure_created": True,
        "files_migrated": [
            "app/__init__.py -> app/__init__.py (обновлен)",
            "app/async_tasks.py -> app/infrastructure/async_tasks/manager.py",
            "app/audio_processor.py -> app/audio/processor.py",
            "app/audio_sources.py -> app/audio/sources.py",
            "app/audio_utils.py -> app/audio/utils.py",
            "app/cache.py -> app/infrastructure/storage/cache.py",
            "app/context_managers.py -> app/shared/context_managers.py",
            "app/file_manager.py -> app/infrastructure/storage/file_manager.py",
            "app/history_logger.py -> app/shared/history_logger.py",
            "app/logging_config.py -> app/infrastructure/logging/config.py",
            "app/request_logger.py -> app/infrastructure/logging/request_logger.py",
            "app/routes.py -> app/api/routes.py",
            "app/transcriber_service.py -> app/core/transcription_service.py",
            "app/transcriber.py -> app/core/transcriber.py",
            "app/utils.py -> app/shared/decorators.py",
            "app/validators.py -> app/infrastructure/validation/validators.py"
        ],
        "new_directories": [
            "app/api/",
            "app/core/",
            "app/audio/",
            "app/infrastructure/",
            "app/infrastructure/logging/",
            "app/infrastructure/storage/",
            "app/infrastructure/async_tasks/",
            "app/infrastructure/validation/",
            "app/shared/"
        ]
    }
    
    with open("migration_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print("Отчет о миграции сохранен в файл migration_report.json")

def main():
    """Основная функция миграции."""
    print("=== Скрипт миграции на новую структуру проекта ===\n")
    
    # Шаг 1: Создание резервной копии
    backup_old_structure()
    
    # Шаг 2: Проверка новой структуры
    if not check_new_structure():
        print("Миграция не может быть продолжена.")
        return
    
    # Шаг 3: Создание отчета о миграции
    create_migration_report()
    
    print("\n=== Миграция завершена ===")
    print("Новая структура проекта готова к использованию.")
    print("Резервная копия старой структуры находится в директории backup_old_structure/")
    print("\nРекомендации:")
    print("1. Протестируйте новую структуру, запустив приложение.")
    print("2. Убедитесь, что все функции работают корректно.")
    print("3. После успешного тестирования запустите скрипт повторно с флагом --cleanup для удаления старых файлов.")
    
    # Проверка флага очистки
    import sys
    if "--cleanup" in sys.argv:
        remove_old_files()

if __name__ == "__main__":
    main()