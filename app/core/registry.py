"""
Registry-паттерн для моделей транскрибации.
Новый тип модели — создать файл *_transcriber.py с декоратором @register_model.
"""

from typing import Dict, List, Optional, Type


_TRANSCRIBERS: Dict[str, type] = {}
_discovered = False


def register_model(name: str):
    """Декоратор для регистрации класса транскрайбера."""
    def decorator(cls):
        if name in _TRANSCRIBERS:
            raise ValueError(f"Модель '{name}' уже зарегистрирована: {_TRANSCRIBERS[name].__name__}")
        _TRANSCRIBERS[name] = cls
        return cls
    return decorator


def get_transcriber_class(model_type: str) -> Optional[type]:
    return _TRANSCRIBERS.get(model_type)


def get_registered_model_types() -> List[str]:
    return list(_TRANSCRIBERS.keys())


def discover_transcribers() -> None:
    """Автообнаружение модулей *_transcriber.py и их регистрация."""
    global _discovered
    if _discovered:
        return
    _discovered = True

    import importlib
    import pkgutil
    from app import core as pkg

    for module_info in pkgutil.iter_modules(pkg.__path__):
        if module_info.name.endswith("_transcriber"):
            importlib.import_module(f".{module_info.name}", package="app.core")
