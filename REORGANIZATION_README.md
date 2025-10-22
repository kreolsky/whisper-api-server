# Реорганизация проекта Whisper API Server

## Обзор

Этот документ описывает реорганизацию проекта Whisper API Server с плоской структуры на архитектуру, основанную на доменах. Цель реорганизации - улучшить поддерживаемость, читаемость и масштабируемость кода.

## Старая структура

```
app/
├── __init__.py
├── async_tasks.py
├── audio_processor.py
├── audio_sources.py
├── audio_utils.py
├── cache.py
├── context_managers.py
├── file_manager.py
├── history_logger.py
├── logging_config.py
├── request_logger.py
├── routes.py
├── transcriber_service.py
├── transcriber.py
├── utils.py
├── validators.py
└── static/
    └── index.html
```

## Новая структура

```
app/
├── __init__.py                 # Главный модуль приложения
├── api/                        # Слой API
│   ├── __init__.py
│   ├── routes.py              # Определения маршрутов API
│   └── middleware.py          # Middleware для запросов/ответов
├── core/                       # Основная бизнес-логика
│   ├── __init__.py
│   ├── transcriber.py         # Основной сервис транскрибации
│   ├── transcription_service.py
│   └── config.py              # Управление конфигурацией
├── audio/                      # Домен обработки аудио
│   ├── __init__.py
│   ├── processor.py           # Предобработка аудио
│   ├── sources.py             # Обработчики источников аудио
│   └── utils.py               # Утилиты для работы с аудио
├── infrastructure/             # Инфраструктурные сервисы
│   ├── __init__.py
│   ├── logging/               # Конфигурация логирования
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── request_logger.py
│   ├── storage/               # Управление файлами и кэшем
│   │   ├── __init__.py
│   │   ├── file_manager.py
│   │   └── cache.py
│   ├── async_tasks/           # Управление фоновыми задачами
│   │   ├── __init__.py
│   │   └── manager.py
│   └── validation/            # Валидация входных данных
│       ├── __init__.py
│       └── validators.py
├── shared/                     # Общие утилиты
│   ├── __init__.py
│   ├── context_managers.py    # Переиспользуемые контекстные менеджеры
│   ├── decorators.py          # Общие декораторы
│   └── history_logger.py      # Функциональность журналирования истории
└── static/                     # Статические веб-ресурсы
    └── index.html
```

## Преимущества новой структуры

1. **Четкое разделение ответственности**: Каждый модуль имеет одну, хорошо определенную зону ответственности
2. **Лучшая поддерживаемость**: Поиск и изменение кода становится более интуитивным
3. **Улучшенная тестируемость**: Тесты могут быть организованы по доменам
4. **Масштабируемость**: Новые функции могут быть добавлены в соответствующие домены
5. **Снижение связанности**: Зависимости между модулями становятся более явными
6. **Улучшенная читаемость**: Организация кода отражает ментальную модель системы

## Карта миграции файлов

| Старый файл | Новое расположение |
|--------------|--------------|
| `routes.py` | `api/routes.py` |
| `request_logger.py` | `infrastructure/logging/request_logger.py` |
| `transcriber.py` | `core/transcriber.py` |
| `transcriber_service.py` | `core/transcription_service.py` |
| `audio_processor.py` | `audio/processor.py` |
| `audio_sources.py` | `audio/sources.py` |
| `audio_utils.py` | `audio/utils.py` |
| `file_manager.py` | `infrastructure/storage/file_manager.py` |
| `cache.py` | `infrastructure/storage/cache.py` |
| `async_tasks.py` | `infrastructure/async_tasks/manager.py` |
| `validators.py` | `infrastructure/validation/validators.py` |
| `logging_config.py` | `infrastructure/logging/config.py` |
| `context_managers.py` | `shared/context_managers.py` |
| `utils.py` | `shared/decorators.py` |
| `history_logger.py` | `shared/history_logger.py` |

## Процесс миграции

1. **Создание новой структуры**: Созданы все новые директории с файлами `__init__.py`
2. **Миграция кода**: Все файлы перемещены в новые расположения с обновленными импортами
3. **Документация**: Весь код задокументирован на русском языке
4. **Тестирование**: Убедитесь, что все функции работают корректно

## Использование скрипта миграции

Для помощи в процессе миграции предоставлен скрипт `migrate_to_new_structure.py`:

```bash
# Запуск миграции
python migrate_to_new_structure.py

# Запуск миграции с последующим удалением старых файлов
python migrate_to_new_structure.py --cleanup
```

## Обновление импортов

При переходе на новую структуру необходимо обновить импорты в вашем коде:

### Примеры обновления импортов

```python
# Старые импорты
from .transcriber import WhisperTranscriber
from .routes import Routes
from .validators import FileValidator

# Новые импорты
from .core.transcriber import WhisperTranscriber
from .api.routes import Routes
from .infrastructure.validation.validators import FileValidator
```

## Тестирование

После миграции убедитесь, что:

1. Приложение запускается без ошибок
2. Все эндпоинты API работают корректно
3. Функции транскрибации работают как ожидалось
4. Логирование работает правильно

## Возврат к старой структуре

Если возникнут проблемы с новой структурой, вы можете вернуться к старой:

1. Восстановите файлы из директории `backup_old_structure/`
2. Удалите новые директории
3. Проверьте, что все работает корректно

## Заключение

Новая структура проекта обеспечивает лучшую организацию кода и упрощает его поддержку. Все функции сохранены, а код стал более читаемым и масштабируемым.