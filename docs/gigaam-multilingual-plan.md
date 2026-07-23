# План работ: поддержка модели GigaAM-Multilingual

**Дата:** 2026-07-23
**Статус:** план (изменения не вносились)
**Источник:** https://huggingface.co/ai-sage/GigaAM-Multilingual,
https://github.com/salute-developers/GigaAM

## Главный вывод (пересматривает docs/gigaam-multilingual-research.md)

Предыдущий отчёт от 2026-07-16 исходил из того, что мультиязычную модель можно
загрузить только через `transformers.AutoModel(..., trust_remote_code=True)`, и на
этом строил все риски (апгрейд torch/transformers, поломка monkey-patch, ручной
longform/VAD). **Это неверно.**

Библиотека `gigaam` (мы ставим её из git `main`) уже поддерживает мультиязычные
модели как штатные варианты `gigaam.load_model()`:

```python
gigaam.load_model("multilingual_ctc")        # 220M
gigaam.load_model("multilingual_large_ctc")  # 600M
```

Оба имени присутствуют в `_MODEL_HASHES` в исходниках библиотеки. Значит:

- **Тот же путь загрузки**, что и у текущего `v3_e2e_rnnt`.
- **Полностью переиспользуется** `GigaAMTranscriber`: `transcribe()`,
  `transcribe_longform()`, `word_timestamps=True`, VAD-сегментация на pyannote,
  оба monkey-patch (`load_audio`, `segment_audio_file`).
- **Никакого апгрейда зависимостей** (torch 2.10 / transformers 5.x) не требуется —
  это был путь `AutoModel`, а не путь библиотеки.

Итог: добавление модели — это по сути **конфигурация + регистрация второго
`model_type`**, а не переписывание транскрайбера.

## Отличия модели, которые нужно учесть

1. **Только CTC, без RNNT и без e2e.** У текущей `v3_e2e_rnnt` end-to-end декодер
   даёт **регистр и пунктуацию/нормализацию**. `multilingual_ctc` — charwise CTC:
   вывод, скорее всего, **в нижнем регистре, без пунктуации**. Это заметная
   регрессия для русского трафика. Постобработку (пунктор/нормализация) — вне
   рамок этого плана, отметить как известное ограничение.
2. **Языки.** Сильно: русский, казахский, киргизский, узбекский; умеренно —
   английский. Модель language-agnostic (charwise CTC), параметр `language`
   по-прежнему игнорируется — текущее поведение `GigaAMTranscriber` подходит.
3. **Точность на русском.** CTC обычно уступает RNNT на русском. Если основной
   трафик русский — оставить `v3_e2e_rnnt` дефолтом, мультиязычную включать
   осознанно. Только один `model_type` грузится за раз, поэтому переключение — это
   правка `config.json` + рестарт.
4. **Веса.** `multilingual_ctc` ~220M, `multilingual_large_ctc` ~600M. Скачиваются
   `gigaam.load_model()` в кэш (или в `download_root`). На orange нужно
   предзагрузить (см. деплой).

## Дизайн-решение

Отдельный `model_type` (не правка существующего) — оставляет v3 для A/B и отката,
паттерн registry это уже поддерживает. Класс транскрайбера тот же.

- Новый `model_type`: **`gigaam-multilingual`**.
- Тот же класс `GigaAMTranscriber` регистрируется под вторым именем.
- Новая секция в `config.json` → `models["gigaam-multilingual"]`.

## Шаги

### 1. Регистрация класса под вторым именем
`app/core/gigaam_transcriber.py`: добавить второй декоратор/регистрацию, чтобы
`GigaAMTranscriber` был доступен и как `gigaam`, и как `gigaam-multilingual`.

```python
@register_model("gigaam")
@register_model("gigaam-multilingual")
class GigaAMTranscriber:
    ...
```

(Декоратор `register_model` возвращает класс — стекать два декоратора корректно;
проверить, что `discover_transcribers()` не падает на двойной регистрации.)

### 2. Конфигурация
`config.json` → в `models` добавить:

```json
"gigaam-multilingual": {
    "variant": "multilingual_ctc",
    "segmentation_model": "/home/text-generation/models/whisper/gigaAM-v3/segmentation"
}
```

- `variant`: `multilingual_ctc` (лёгкая, дефолт) либо `multilingual_large_ctc`
  (точнее, 600M).
- `segmentation_model`: тот же pyannote-путь, что и у v3 (нужен для longform VAD).
- `model_path` в секции gigaam фактически **не используется** транскрайбером
  (грузит `gigaam.load_model(variant)`); можно не добавлять. При желании
  зафиксировать каталог загрузки — отдельно передавать `download_root` (см. п.5).
- Переключение на мультиязычную: `"model_type": "gigaam-multilingual"`.

### 3. Проверка вывода timestamps
Убедиться, что для `multilingual_ctc` `transcribe(word_timestamps=True)` и
`transcribe_longform(word_timestamps=True)` возвращают структуры с `.words` /
`.segments` в том же виде, что ожидают `_format_timestamps_result` и
`_format_longform_result`. По README — поддерживается для CTC и RNNT; проверить
фактически на установленной версии.

### 4. Локальный прогон
- Короткий файл (<25 с): текст + `return_timestamps=true`.
- Длинный файл (>25 с): путь `transcribe_longform` + VAD + сегментные метки.
- Русский + один из казахский/киргизский/узбекский — sanity-check мультиязычности.
- Сверить регистр/пунктуацию вывода (ожидается lower-case без пунктуации).

### 5. (Опционально) Явный каталог весов
Если нужен контролируемый путь загрузки (offline/зеркало) — пробросить
`download_root=config.model.get("model_path")` в `gigaam.load_model()` в
`_load_model()`. Иначе используется дефолтный кэш gigaam.

### 6. Деплой (orange)
- Предзагрузить веса `multilingual_ctc` (или `_large_ctc`) в кэш/`download_root`
  на сервере (нет доступа в интернет во время запроса).
- Переиспользуется существующая модель сегментации pyannote — доп. скачивания нет.
- Обновить `config.json` на сервере (`model_type` + новая секция), рестарт
  `whisper.service`.
- `requirements.txt` **менять не нужно** (gigaam уже из git main).

### 7. Документация
- Обновить `docs/gigaam-multilingual-research.md` пометкой, что вывод пересмотрен
  (модель доступна через библиотеку, тяжёлый апгрейд не нужен).
- Кратко описать новый `model_type` и его ограничения (CTC, без пунктуации) в
  README/CLAUDE.md при необходимости.

## Оценка

- **Сложность: низкая.** Код: ~несколько строк (второй `@register_model`) плюс
  секция конфига. Основное — прогоны и проверка формата timestamps/longform.
- **Риск: низкий** для интеграции; **средний** для качества на русском (CTC vs
  RNNT, отсутствие пунктуации) — решается выбором дефолта `model_type`.

## Открытые вопросы

1. `multilingual_ctc` (220M) или `multilingual_large_ctc` (600M) как рабочий вариант?
2. Нужна ли постобработка (регистр/пунктуация) для русского вывода, или lower-case
   без пунктуации приемлемо?
3. Оставляем `v3_e2e_rnnt` дефолтом, мультиязычную — по требованию?
</content>
