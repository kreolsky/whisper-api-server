# Отчёт: возможность замены модели на GigaAM-Multilingual

**Дата:** 2026-07-16
**Статус:** исследование (изменения не вносились)
**Источник:** https://huggingface.co/ai-sage/GigaAM-Multilingual

## Краткий вывод

Замена **возможна, но не является drop-in swap**. Она меняет и библиотеку загрузки,
и runtime-API, а также отбирает функции, на которые опирается текущая реализация
(RNNT-декодер, `transcribe_longform`, пословные таймстемпы). Целесообразна только
если реально нужна мультиязычность (казахский/киргизский/узбекский). Для чисто
русского трафика GigaAM-v3 RNNT, скорее всего, точнее.

## Что используется сейчас

Файл: `app/core/gigaam_transcriber.py`, `app/core/gigaam_patches.py`

- Библиотека: отдельный пакет **`gigaam`** → `gigaam.load_model("v3_e2e_rnnt")`
- **RNNT** end-to-end декодер
- `model.transcribe(...)` **и** `model.transcribe_longform(...)`
- Поддержка **`word_timestamps=True`** (пословные таймстемпы)
- VAD-сегментация на базе pyannote для longform
- Два monkey-patch, завязанных на внутренности пакета `gigaam`:
  - `gigaam.preprocess.load_audio` — логирование stderr от ffmpeg
  - `gigaam.vad_utils.segment_audio_file` — обход torchcodec

## Что даёт GigaAM-Multilingual

- Загрузка через **`transformers`**:
  ```python
  from transformers import AutoModel
  model = AutoModel.from_pretrained(
      "ai-sage/GigaAM-Multilingual",
      revision="ctc",  # или ssl, large_ssl, large_ctc
      trust_remote_code=True,
  )
  transcription = model.transcribe("example.wav")
  ```
- Варианты: `ctc` (220M), `large_ctc` (600M), а также `ssl`/`large_ssl`
  (только энкодеры, для ASR напрямую не используются)
- Предобучение: HuBERT-style, 2M часов речи, 70+ языков; дообучение 50K часов
- Языки: сильно на **русском, казахском, киргизском, узбекском**; умеренно на английском
- Зависимости по карточке: `torch==2.10.*`, `torchaudio==2.10.*`,
  `transformers==5.*`, `hydra-core`, `omegaconf`

## Ключевые риски и пробелы

1. **Только CTC, нет RNNT.** Другой декодер. Точность на русском трафике нужно
   мерить бенчмарком, а не предполагать — RNNT у GigaAM обычно точнее CTC на русском.
2. **Нет `transcribe_longform` и (по карточке) нет пословных таймстемпов.**
   На HF показан только простой `model.transcribe(file)`. Наши longform-путь, VAD и
   функцию `return_timestamps` (`_format_timestamps_result`, `_format_longform_result`)
   пришлось бы строить вручную (внешний VAD-чанкинг + сшивка).
3. **Наши monkey-patch устаревают.** Оба патча нацелены на внутренности пакета
   `gigaam`. С `transformers` + `trust_remote_code` код загрузки аудио и сегментации
   другой; логирование ffmpeg stderr и обход torchcodec пришлось бы переделывать.
   Вероятно, remote-код использует `torchaudio`, что возвращает проблему torchcodec/кодеков,
   которую мы обходили патчем.
4. **Тяжёлый апгрейд зависимостей.** `torch 2.10.*`, `torchaudio 2.10.*`,
   `transformers 5.*` — крупный скачок, возможен конфликт с текущим стеком
   Whisper (transformers/pyannote) в одном conda-окружении.
5. **`trust_remote_code=True`** — выполняет код из HF-репозитория. Приемлемо для
   локального зеркала с закреплённой ревизией, но требует пиннинга.

## Оценка трудозатрат

- **Сложность:** средняя–высокая, не тривиально.
- **Подход:** отдельный класс транскрайбера (например `@register_model("gigaam_ml")`),
  а не правка существующего — оставляет v3 для A/B-сравнения и отката. Паттерн
  registry это уже поддерживает.
- **Стоит внедрять только если** реально нужна мультиязычность (казахский/киргизский/
  узбекский). Для чистого русского v3 RNNT, вероятно, лучше.

## Что проверить до принятия решения

1. Отдаёт ли мультиязычная модель пословные/сегментные таймстемпы в принципе?
2. RU WER относительно текущего v3 на нашем аудио.
3. Совместимость зависимостей (torch/transformers 5.x) с Whisper-путём в одном окружении.
</content>
</invoke>
