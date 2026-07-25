# Whisper API Server -- Project Bible

Local, OpenAI-compatible speech recognition API service. Supports multiple ASR backends (Whisper, GigaAM) behind one registry, multiple audio input methods (file upload, URL, base64, local path), hardware acceleration (CUDA/MPS/CPU), audio preprocessing pipeline, and async transcription.

**Development rules and coding standards: see `RULES.md`**

**Agent language: always think and respond in English, regardless of the user's language.**

## Tech Stack

* **Backend**: Python 3.12+, Flask, Waitress (WSGI). Entry: `server.py`.
* **ML**: PyTorch, Hugging Face Transformers (Whisper), GigaAM (+ pyannote segmentation), Flash Attention 2.
* **Audio**: FFmpeg, SoX (external), scipy (resampling).
* **Validation**: python-magic (MIME detection).
* **Environment**: Conda. Setup: `server.sh`.
* **Tooling**: ruff (format + lint, config in `pyproject.toml`), pytest.
* **Language**: Code comments and docstrings in Russian (project convention).

## Architecture

* Entry: `server.py` -> `app/__init__.py` (WhisperServiceAPI)
* Modules: `app/core/` (registry, transcribers, config, transcription service), `app/audio/` (processor, sources, utils), `app/infrastructure/` (logging, validation, storage, async tasks)
* Request flow: source function -> validate -> `TranscriptionService.transcribe()` (ModelManager.resolve -> transcriber inference) -> save history -> JSON response
* OpenAI-compatible API: `/v1/audio/transcriptions` matches OpenAI contract for drop-in replacement
* All settings in `config.json`. Device fallback: CUDA -> MPS -> CPU
* **Multi-model:** `ModelManager` (`app/core/model_manager.py`) holds N transcribers loaded at startup from `config.loaded_models`, each pinned to its own `device_id`; requests route by the `model` parameter, default = `config.model_type`. Unknown `model` falls back to default + warning. Builds on `docs/gigaam-multilingual-plan.md`.

### Transcriber registry

Backends are pluggable, not hardcoded. `app/core/registry.py` holds a name -> class map:

* `base.py` defines `Transcriber` -- a `runtime_checkable` Protocol (`is_ready`, `transcribe(...)`), not a base class. A backend conforms structurally; it does not inherit.
* A backend lives in `app/core/<name>_transcriber.py` and registers itself with `@register_model("<name>")`. Currently: `whisper_transcriber.py`, `gigaam_transcriber.py`.
* `discover_transcribers()` auto-imports every `*_transcriber.py` in `app/core/` (lazily, on first use -- so importing `app.core` does **not** pull in torch). Registering a duplicate name raises.
* `create_transcriber(config)` resolves `config.model_type` through the registry and raises `ValueError` listing available types if unknown.
* **Adding a backend = one new `*_transcriber.py` file.** No edits to registry, factory, or config loader.
* `gigaam_patches.py` holds isolated monkey-patches for the `gigaam` library, called explicitly from `GigaAMTranscriber._load_model()`; a failed patch crashes loudly (signals a library version mismatch).

## Deployment

Prod runs on host `orange` as the systemd unit `whisper.service` (**not** Docker -- `Dockerfile`/`docker-compose.yml` exist but the migration has not happened yet). Restart requires root. Full procedures: `/deploy` skill.

## Tests

`tests/test_all.py` -- 23 tests, mock-based (config, registry, validator, history, async tasks, transcription service). They run on orange, not locally. Commands and the "green tests are not evidence" caveat: `.claude/rules/testing.md`.
