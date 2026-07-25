"""
Изолированные monkey-patches для gigaam.
Каждый патч — функция, которая вызывается явно из GigaAMTranscriber._load_model().
При ошибке патчинга — crash с понятным сообщением (версия gigaam несовместима).
"""

import logging
import threading
from subprocess import CalledProcessError

logger = logging.getLogger('app.gigaam_patches')

_load_audio_patched = False
_segment_audio_patched = False

# Устройство, на котором инициализирован общий VAD-пайплайн. Фиксируется первой
# загружаемой моделью (см. _init_vad_pipeline и §4 плана multi-model).
_vad_device = None

# VAD (gigaam.vad_utils._PIPELINE) — единый модульный объект, общий для всех
# моделей. При параллельных longform-запросах с разных GPU он становится точкой
# состязания; лок сериализует только VAD-сегментацию, не трогая инференс (он
# остаётся за собственным семафором каждого транскрайбера).
_vad_lock = threading.Lock()


def set_vad_device(device) -> None:
    """Фиксирует устройство общего VAD-пайплайна (вызывается при инициализации)."""
    global _vad_device
    _vad_device = device


def patch_load_audio():
    """
    Патчит gigaam_preprocess.load_audio: оригинал теряет stderr от ffmpeg при ошибке,
    что делает невозможной диагностику проблем с аудиофайлами.
    """
    global _load_audio_patched
    if _load_audio_patched:
        logger.debug("load_audio уже пропатчен — пропуск")
        return

    import gigaam.preprocess as gigaam_preprocess

    _original_load_audio = gigaam_preprocess.load_audio

    def _load_audio_with_logging(audio_path, sample_rate=gigaam_preprocess.SAMPLE_RATE):
        try:
            return _original_load_audio(audio_path, sample_rate)
        except RuntimeError as e:
            cause = e.__cause__
            if isinstance(cause, CalledProcessError):
                stderr = cause.stderr.decode("utf-8", errors="replace") if cause.stderr else "(пусто)"
                logger.error(
                    "ffmpeg не смог декодировать '%s' (exit code %d). stderr:\n%s",
                    audio_path, cause.returncode, stderr
                )
            raise

    gigaam_preprocess.load_audio = _load_audio_with_logging
    _load_audio_patched = True
    logger.info("load_audio пропатчен для логирования ffmpeg stderr")


def patch_segment_audio_file():
    """
    Патчит vad_utils.segment_audio_file: pyannote 4.x требует torchcodec для чтения файлов,
    но torchcodec не работает с conda-окружением из-за старого GCC runtime.
    Вместо этого загружаем аудио через ffmpeg (GigaAM preprocess) и передаём
    в pipeline как waveform dict — pyannote принимает такой формат напрямую.
    """
    global _segment_audio_patched
    if _segment_audio_patched:
        logger.debug("segment_audio_file уже пропатчен — пропуск")
        return

    import gigaam.vad_utils as vad_utils
    import torch
    from gigaam.preprocess import SAMPLE_RATE
    from gigaam.preprocess import load_audio as gigaam_load_audio

    def _patched_segment_audio_file(wav_file, sr, device=torch.device("cpu"), **kwargs):
        # VAD — единый общий пайплайн; фиксируем его устройство из инициализации,
        # а не переданный device (оригинальный default 'cpu' перемещал бы
        # привязанный к GPU пайплайн).
        vad_device = _vad_device if _vad_device is not None else device
        # Декод аудио и сбор waveform — per-request работа над локальными данными,
        # не требуют блокировки (ffmpeg-декод долгий; держать его под локом —
        # сериализовать longform-запросы с разных GPU). Локом защищаем только
        # обращение к общему модулю VAD-пайплайна.
        audio = gigaam_load_audio(wav_file)
        waveform_dict = {"waveform": audio.unsqueeze(0), "sample_rate": SAMPLE_RATE}
        with _vad_lock:
            vad_pipeline = vad_utils.get_pipeline(vad_device)
            sad_segments = vad_pipeline(waveform_dict)

        max_duration = kwargs.get("max_duration", 22.0)
        min_duration = kwargs.get("min_duration", 15.0)
        strict_limit_duration = kwargs.get("strict_limit_duration", 30.0)
        new_chunk_threshold = kwargs.get("new_chunk_threshold", 0.2)

        segments = []
        boundaries = []
        curr_duration = 0.0
        curr_start = 0.0
        curr_end = 0.0

        def _update_segments(cs, ce, cd):
            if cd > strict_limit_duration:
                max_segs = int(cd / strict_limit_duration) + 1
                seg_dur = cd / max_segs
                ce_local = cs + seg_dur
                for _ in range(max_segs - 1):
                    segments.append(audio[int(cs * sr): int(ce_local * sr)])
                    boundaries.append((cs, ce_local))
                    cs = ce_local
                    ce_local += seg_dur
            segments.append(audio[int(cs * sr): int(ce * sr)])
            boundaries.append((cs, ce))

        for segment in sad_segments.get_timeline().support():
            start = max(0, segment.start)
            end = min(audio.shape[0] / sr, segment.end)
            if curr_duration == 0.0:
                curr_start = start
            elif curr_duration > new_chunk_threshold and (
                curr_duration + (end - curr_end) > max_duration
                or curr_duration > min_duration
            ):
                _update_segments(curr_start, curr_end, curr_duration)
                curr_start = start
            curr_end = end
            curr_duration = curr_end - curr_start

        if curr_duration > new_chunk_threshold:
            _update_segments(curr_start, curr_end, curr_duration)

        return segments, boundaries

    vad_utils.segment_audio_file = _patched_segment_audio_file
    _segment_audio_patched = True
    logger.info("segment_audio_file пропатчен для обхода torchcodec")
