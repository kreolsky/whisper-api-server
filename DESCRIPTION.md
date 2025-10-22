# Whisper API server project structure

The project is a local API service for speech recognition based on the Whisper model. The service is designed as an OpenAI-compatible API, allowing it to be used as a local alternative to cloud-based speech recognition services.

## Main files

### Root files
- **server.py** - Application entry point, initializes and starts the service.
- **server.sh** - Bash script to start the server with optional conda environment update.
- **config.json** - Configuration file with service settings.
- **requirements.txt** - Project dependencies for conda/pip.

### `app` module

#### app/\_\_init\_\_.py
Contains the main class `WhisperServiceAPI`, which initializes the application, loads the configuration, and starts the server on the specified port using the production-ready Waitress server.

#### app/logger.py
Configures logging for all application components.

#### app/transcriber.py
Contains the `WhisperTranscriber` class, which loads the Whisper model and performs speech recognition. The class determines the optimal device for computations (CPU, CUDA, MPS) and supports acceleration with Flash Attention 2.

#### app/audio_processor.py
Contains the `AudioProcessor` class for preprocessing audio files before transcription. Includes methods for:
- Converting to WAV with a 16 kHz sample rate.
- Normalizing volume level (with configurable `norm_level` parameters).
- Applying compression/expansion (with configurable `compand_params` parameters).
- Speeding up audio playback for faster recognition (with configurable `audio_speed_factor` parameter).
- Adding silence at the beginning of the recording.
- Cleaning up temporary files.

#### app/audio_sources.py
Contains the abstract class `AudioSource` and its concrete implementations for various audio sources:
- `UploadedFileSource` - for files uploaded via HTTP request.
- `URLSource` - for files available via URL.
- `Base64Source` - for audio encoded in base64.
- `LocalFileSource` - for local files on the server.
- `FakeFile` - a helper class for unifying processing from different sources.

#### app/history_logger.py
Contains the `HistoryLogger` class for saving transcription history.

#### app/routes.py
Contains the classes:
- `TranscriptionService` - a service for processing and transcribing audio files, including methods for getting audio duration and transcribing from various sources.
- `Routes` - registers all API endpoints, including OpenAI-compatible routes and an endpoint for retrieving service configuration.

## Main classes

### WhisperServiceAPI
The main application class, initializes the service, loads the configuration, and starts the server using Waitress.

### WhisperTranscriber
A class for speech recognition using the Whisper model. Determines the optimal device for computations, loads the model considering available hardware, and performs transcription of audio files.

### AudioProcessor
A class for preprocessing audio files. Performs conversion, normalization, and adds silence at the beginning of the recording to improve recognition quality, using configurable parameters.

### AudioSource (and subclasses)
An abstract class and its implementations for working with various audio file sources. Provides a unified interface for obtaining audio files from different sources.

### HistoryLogger
A class for saving transcription history.

### TranscriptionService
A service that combines the logic for processing requests and transcribing audio. Accepts an audio source, processes it, and returns the transcription result.

### Routes
A class that registers all API routes of the service, including OpenAI-compatible endpoints for integration with existing systems, as well as an endpoint for retrieving the current configuration.

## API endpoints

The service provides several endpoints, including:
- `/health` - Service status check.
- `/config` - Get current configuration.
- `/local/transcriptions` - Transcribe a local file on the server.
- `/v1/models` - Get a list of available models (OpenAI-compatible).
- `/v1/audio/transcriptions` - Transcribe an uploaded file (OpenAI-compatible).
- `/v1/audio/transcriptions/url` - Transcribe from a URL.
- `/v1/audio/transcriptions/base64` - Transcribe from base64.
- `/v1/audio/transcriptions/multipart` - Transcribe a file from a multipart form.

The service is designed to provide maximum flexibility in use and integration with existing systems that support the OpenAI Whisper API.