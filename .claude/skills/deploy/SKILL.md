---
name: deploy
description: >
  Use when: user says "deploy", "деплой", "задеплой", "обнови сервер",
  "обнови на orange", "залей на сервер", "перезапусти whisper",
  "рестарт whisper", "статус whisper на orange", "логи whisper на orange".
  Do NOT use for: local development, testing, or unrelated server tasks.
---

# deploy: Деплой Whisper API на сервер Orange

## Инфраструктура (актуальное состояние)

**Хост:** `orange` (10.10.1.20) -- bare metal, NVIDIA RTX 3090
**Путь на сервере:** `/home/text-generation/servers/whisper-api`
**Рантайм:** systemd-юнит `whisper.service` (НЕ Docker -- см. раздел «Будущее» внизу)
**Python:** `/home/serge/.miniconda/envs/whisper-api/bin/python` (conda-окружение `whisper-api`)
**Порт:** 5042, внешний адрес `http://stt.ai.gray`

Юнит (`/etc/systemd/system/whisper.service`), проверено:

```
WorkingDirectory=/home/text-generation/servers/whisper-api
ExecStart=/home/serge/.miniconda/envs/whisper-api/bin/python .../server.py --config config.json
Environment="HOME=/home/serge"
Environment="LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
Restart=on-failure
```

`LD_PRELOAD` обязателен -- при ручном запуске без него импорт падает.

## SSH-доступ и права

```bash
ssh orange         # чтение: git pull, systemctl status, journalctl, тесты
ssh root@orange    # ОБЯЗАТЕЛЕН для restart/stop/start
```

Проверено: `systemctl restart` из-под обычного пользователя падает с
`Interactive authentication required`. Чтение статуса и логов -- работает без root.

## Поведенческие правила

- **Деплой = git pull на сервере** -- не копируем файлы через scp, сервер сам тянет из git.
- **Не трогать `config.json` на сервере** -- серверный конфиг отличается от локального
  (на сервере он в состоянии `M`). Изменения конфига обсуждаются отдельно, не в рамках деплоя.
- **Модель грузится ~15-30 сек** после рестарта -- подождать перед проверкой API.
- **`requirements.txt` изменился** -- обновить окружение (`server.sh --update`), потом рестарт.
- **После деплоя** -- проверить `systemctl status` И health-эндпоинт: юнит может быть
  `active (running)`, пока модель ещё грузится.

## Процедуры

### 1. Полный деплой (обновление кода + рестарт)

```bash
ssh orange "cd /home/text-generation/servers/whisper-api && git pull"
ssh root@orange "systemctl restart whisper.service"

sleep 25
ssh orange "systemctl status whisper.service --no-pager | head -8"
curl -s http://stt.ai.gray/health
```

### 2. Деплой с обновлением зависимостей

```bash
ssh orange "cd /home/text-generation/servers/whisper-api && git pull && ./server.sh --update"
ssh root@orange "systemctl restart whisper.service"
sleep 30
curl -s http://stt.ai.gray/health
```

### 3. Только рестарт

```bash
ssh root@orange "systemctl restart whisper.service"
sleep 25
curl -s http://stt.ai.gray/health
```

### 4. Проверка статуса

```bash
ssh orange "systemctl status whisper.service --no-pager | head -8"
```

### 5. Логи

```bash
# Последние 50 строк
ssh orange "journalctl -u whisper.service -n 50 --no-pager"

# Реалтайм
ssh orange "journalctl -u whisper.service -f"

# Только ошибки за сегодня
ssh orange "journalctl -u whisper.service --since today -p err --no-pager"
```

### 6. Проверка API

```bash
curl -s http://stt.ai.gray/health      # {"model":"gigaam","status":"ok","version":"1.0.0"}
curl -s http://stt.ai.gray/v1/models

curl -s -X POST http://stt.ai.gray/v1/audio/transcriptions \
  -F "file=@test.wav" -F "model=gigaam"
```

### 7. Откат

```bash
ssh orange "cd /home/text-generation/servers/whisper-api && git checkout <commit>"
ssh root@orange "systemctl restart whisper.service"
sleep 25
curl -s http://stt.ai.gray/health
```

### 8. Прогон тестов на сервере

Локальное окружение на Mac тесты не тянет (нужны torch/transformers), поэтому сюит гоняется
на orange -- см. `.claude/rules/testing.md`. Важно: тесты идут по коду, который лежит НА
СЕРВЕРЕ, то есть после `git pull`, а не по локальному рабочему дереву.

```bash
ssh orange "cd /home/text-generation/servers/whisper-api && \
  /home/serge/.miniconda/envs/whisper-api/bin/python -m pytest tests/ -q"
```

---

## Будущее: миграция на Docker (ЕЩЁ НЕ АКТИВНО)

В репозитории лежат `Dockerfile` и `docker-compose.yml`, но **прод на них не переведён**.
Ничего из этого раздела не запускать в рамках обычного деплоя -- на сервере нет запущенных
контейнеров, команды `docker compose` там работать не будут.

Целевая схема: Docker + NVIDIA Container Toolkit, код монтируется volume'ом (`.:/app`),
поэтому rebuild нужен только при изменении `requirements.txt`.

Первичная настройка (один раз, при переезде):

```bash
ssh orange "docker info | grep -i runtime"            # проверить NVIDIA runtime
ssh root@orange "systemctl disable --now whisper.service"
ssh orange "cd /home/text-generation/servers/whisper-api && docker compose up -d --build"
```

После переезда процедуры 1-7 заменяются на: `git pull && docker compose restart`
(или `up -d --build` при смене зависимостей), статус -- `docker compose ps`,
логи -- `docker compose logs --tail=50`. **Этот файл и `.claude/rules/testing.md`
обновить в том же коммите, что и переезд.**
