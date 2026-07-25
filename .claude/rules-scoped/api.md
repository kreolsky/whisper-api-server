# API layer — read before editing `app/routes.py` or `app/infrastructure/validation.py`

## Route rules

* New endpoints go inside `Routes._register_routes()`. Nowhere else.
* **Every** transcription endpoint delegates to `TranscriptionService.transcribe()` — routes
  never call a transcriber directly. Routes parse the request, pick a source, and format the
  response; that is all.
* File validation runs through `FileValidator`. Never validate inline in a route.
* Config read via `self.config.<field>` (typed `AppConfig`). Critical params must crash if
  missing, not silently default (`coding-constraints.md`).

Current surface: `/`, `/health`, `/config`, `/v1/models`, `/v1/models/<id>`,
`/v1/audio/transcriptions` (+ `/url`, `/base64`, `/async`), `/v1/tasks/<task_id>`.

## OpenAI compatibility is a contract, not a nicety

`/v1/audio/transcriptions` exists so OpenAI SDK clients work unmodified. That constrains
changes:

* **Response shape is fixed.** Adding a field is safe; renaming or removing one breaks
  clients silently — they read `.text`.
* **Unknown `model` values must not 400.** SDK clients send `model="whisper-1"`
  unconditionally regardless of what we serve. Falling back to the default with a logged
  warning is deliberate; a strict 400 would break every stock client.
* Test with a real OpenAI SDK client, not only curl — the SDK's multipart encoding differs
  from a hand-written `-F` (see "verify with a different tool" in `testing.md`).

## Validation

`FileValidator` checks extension **and** MIME type via python-magic. Both — extension alone
is trivially spoofed, and MIME alone rejects legitimate files whose container detection is
ambiguous.

Supporting a new format means updating the allowed extensions AND the allowed MIME types.
Updating only one produces the confusing failure mode where the file is accepted and then
fails deep in ffmpeg, or is rejected with a message about a format that is listed as supported.

Test the file that must be **refused** — that is what the validator is for.

## Async transcription

`/v1/audio/transcriptions/async` returns a task id; state lives in `AsyncTaskManager`
(in-memory). Consequences to keep in mind: task state does not survive a restart, and a
deploy mid-transcription loses the result. Do not add long-lived client contracts on top of
it without saying so explicitly.
