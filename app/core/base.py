"""
Базовый интерфейс транскрайбера — typing.Protocol.
"""

from typing import Dict, Tuple, Union, Protocol, runtime_checkable


@runtime_checkable
class Transcriber(Protocol):
    """
    Протокол транскрайбера. Определяет контракт, которому должны
    соответствовать WhisperTranscriber и GigaAMTranscriber.
    """

    @property
    def is_ready(self) -> bool: ...

    def transcribe(self, audio_path: str, return_timestamps: bool = None,
                   language: str = None, temperature: float = None,
                   prompt: str = None, **kwargs) -> Union[str, Dict]: ...

    def process_file(self, input_path: str, return_timestamps: bool = None,
                     language: str = None, temperature: float = None,
                     prompt: str = None) -> Tuple[Union[str, Dict], float]: ...
