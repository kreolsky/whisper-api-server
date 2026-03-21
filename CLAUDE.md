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

```
server.py                          # Entry point, argparse, launches WhisperServiceAPI
app/__init__.py                    # WhisperServiceAPI: Flask init, wires all components
app/core/
  config.py                        # load_config() from JSON
  transcriber.py                   # WhisperTranscriber: model load, device select, inference
  transcription_service.py         # TranscriptionService: orchestrates source -> validate -> transcribe -> log
app/audio/
  processor.py                     # AudioProcessor: WAV convert, normalize, compress, speedup, silence
  sources.py                       # AudioSource (abstract) + UploadedFile/URL/Base64/LocalFile sources
  utils.py                         # AudioUtils: load audio as numpy, get duration via ffprobe
app/api/
  routes.py                        # All Flask endpoints (OpenAI-compatible + local + async)
app/infrastructure/
  storage/cache.py                 # SimpleCache with TTL
  storage/file_manager.py          # TempFileManager: temp file lifecycle with context managers
  logging/config.py                # setup_logging(): console + rotating file handler
  logging/request_logger.py        # RequestLogger: HTTP request/response middleware
  validation/validators.py         # FileValidator: size, extension, MIME checks
  async_tasks/manager.py           # AsyncTaskManager: thread-based async with status tracking
app/shared/
  history_logger.py                # HistoryLogger: saves transcription results as JSON by date
  decorators.py                    # log_invalid_file_request decorator
  context_managers.py              # open_file context manager
app/static/
  index.html                       # Built-in web UI client
```

## Request Flow

```
Flask Request
  -> RequestLogger middleware (logs request)
  -> Routes (endpoint handler)
  -> TranscriptionService.transcribe_from_source()
     -> AudioSource.get_audio_file()        # fetch from upload/URL/base64/local
     -> FileValidator.validate_file()        # size/extension/MIME
     -> WhisperTranscriber.process_file()
        -> AudioProcessor.process_audio()    # WAV 16kHz, normalize, compress, speedup, silence
        -> WhisperTranscriber.transcribe()   # model inference
     -> HistoryLogger.save()                 # persist result JSON
  -> JSON Response (text, processing_time, duration, model)
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Web UI |
| GET | `/health` | Service status |
| GET | `/config` | Current configuration |
| GET | `/v1/models` | List models (OpenAI-compatible) |
| GET | `/v1/models/<id>` | Model details |
| POST | `/v1/audio/transcriptions` | Transcribe uploaded file (multipart) |
| POST | `/v1/audio/transcriptions/url` | Transcribe from URL |
| POST | `/v1/audio/transcriptions/base64` | Transcribe from base64 |
| POST | `/v1/audio/transcriptions/async` | Async transcription |
| GET | `/v1/tasks/<task_id>` | Async task status |
| POST | `/local/transcriptions` | Transcribe local server file |

## Configuration

All settings in `config.json`. Key parameters:

* `service_port`: server port (default 5042)
* `model_path`: path to Whisper model directory
* `language`: recognition language
* `device_id`: GPU index for CUDA
* Audio processing: `norm_level`, `compand_params`, `audio_speed_factor`, `audio_rate`
* Inference: `chunk_length_s`, `batch_size`, `max_new_tokens`, `temperature`
* `file_validation`: max size, allowed extensions/MIME types
* `request_logging`: excluded endpoints, sensitive headers

## Key Design Decisions

* **Config-driven**: All behavior controlled via `config.json`. No hardcoded model paths or thresholds.
* **Source abstraction**: `AudioSource` ABC unifies all input methods. New sources implement `get_audio_file()`.
* **Temp file lifecycle**: `TempFileManager` with context managers ensures cleanup even on errors.
* **OpenAI compatibility**: `/v1/audio/transcriptions` matches OpenAI API contract for drop-in replacement.
* **Device fallback**: CUDA -> MPS -> CPU, with Flash Attention 2 attempted first on CUDA.
