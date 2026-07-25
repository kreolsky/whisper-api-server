"""
Модуль device.py — централизованный выбор устройства (CPU/CUDA/MPS).
Логика вынесена из WhisperTranscriber._get_device, чтобы её могли
переиспользовать и другие транскрайберы (в т.ч. GigaAM).
"""

import logging
from typing import Any, Dict

import torch

logger = logging.getLogger('app.device')


def resolve_device(model_config: Dict[str, Any]) -> torch.device:
    """Разрешает устройство для модели по её секции конфигурации.

    CUDA: берёт device_id (по умолчанию 0), валидирует что это int (bool
    отвергается) и что индекс попадает в диапазон доступных GPU; иначе откат на
    cuda:0 с предупреждением (покрывает и отрицательные значения).
    Без CUDA: MPS при наличии, иначе CPU.

    Args:
        model_config: Секция models.<name> (может содержать device_id).

    Returns:
        Объект torch.device для вычислений.
    """
    if torch.cuda.is_available():
        device_id = model_config.get("device_id", 0)

        # bool — подкласс int; запрещаем явно (True/False — не валидный индекс GPU).
        if isinstance(device_id, bool) or not isinstance(device_id, int):
            logger.warning(
                "device_id должен быть целым числом, получено: %s. Используем 0",
                device_id,
            )
            device_id = 0

        device_count = torch.cuda.device_count()
        if not (0 <= device_id < device_count):
            logger.warning(
                "Запрошенный GPU с индексом %s недоступен. Доступно GPU: %s. "
                "Используем GPU с индексом 0", device_id, device_count,
            )
            device_id = 0

        logger.info("Используется CUDA GPU с индексом %s для вычислений", device_id)
        return torch.device(f"cuda:{device_id}")

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        logger.info("Используется MPS (Apple Silicon) для вычислений")
        # Обходное решение для MPS: PyTorch проверяет is_initialized()
        # при создании тензоров на MPS-устройстве, что вызывает ошибку
        # в однопроцессном режиме.
        # TODO: Удалить после обновления до PyTorch >= 2.5
        setattr(torch.distributed, "is_initialized", lambda: False)
        return torch.device("mps")

    logger.info("Используется CPU для вычислений")
    return torch.device("cpu")
