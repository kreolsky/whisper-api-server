# Whisper API Server -- Project Bible

Local, OpenAI-compatible speech recognition API service using the Whisper model. Supports multiple audio input methods (file upload, URL, base64, local path), hardware acceleration (CUDA/MPS/CPU), audio preprocessing pipeline, and async transcription.

**Development rules and coding standards: see `RULES.md`**

## Tech Stack

* **Backend**: Python 3.12+, Flask, Waitress (WSGI). Entry: `server.py`.
* **ML**: PyTorch, Hugging Face Transformers (Whisper), Flash Attention 2.
* **Audio**: FFmpeg, SoX (external), scipy (resampling).
* **Validation**: python-magic (MIME detection).
* **Environment**: Conda. Setup: `server.sh`.
* **Language**: Code comments and docstrings in Russian (project convention).

## Architecture

* Entry: `server.py` -> `app/__init__.py` (WhisperServiceAPI)
* Modules: `app/core/` (transcriber, config), `app/audio/` (processor, sources, utils), `app/infrastructure/` (logging, validation, storage, async tasks)
* Request flow: source function -> validate -> transcribe (AudioProcessor -> Whisper inference) -> save history -> JSON response
* OpenAI-compatible API: `/v1/audio/transcriptions` matches OpenAI contract for drop-in replacement
* All settings in `config.json`. Device fallback: CUDA -> MPS -> CPU
