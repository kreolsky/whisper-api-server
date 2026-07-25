# Transcriber backends — read before editing `app/core/**`

## The registry contract

`app/core/base.py` defines `Transcriber` as a `runtime_checkable` **Protocol**, not a base
class. Backends conform structurally — they do not inherit. Reading one existing transcriber
and copying its `__init__` teaches you that file's habits; the Protocol is the contract.

Required surface: the `is_ready` property and `transcribe(audio_path, return_timestamps=None,
language=None, temperature=None, prompt=None, **kwargs) -> Union[str, Dict]`.

## Adding a backend

One new file, `app/core/<name>_transcriber.py`, with `@register_model("<name>")`. That is all:

* `discover_transcribers()` auto-imports every `*_transcriber.py` in `app/core/` — no
  registration list to update, no factory to edit, no config-loader change.
* Registering a name twice **raises**. If a module gets imported by two paths, you get a
  startup crash, not a silent overwrite.
* Discovery is **lazy** — called from `create_transcriber()`, not at package import. That is
  why importing `app.core` does not pull in torch, and why the test suite can touch the
  registry cheaply. Do not move it to module scope: it would drag torch into every import
  and slow startup for no gain.

Add the model's config section under `models.<name>` in `config.json`; `load_config()` warns
(does not crash) when the section for the active `model_type` is missing.

## Concurrency — two mechanisms, know which is which

* Each transcriber holds `threading.Semaphore(max_concurrent)` around inference. **This is
  the only limit on parallel GPU work.**
* `TranscriptionService.transcribe()` adds a **timeout only** — `threading.Thread` +
  `Event.wait(timeout)`, returning 504 on expiry. It deliberately does NOT use a
  `ThreadPoolExecutor`: a pool of 1 would have made the semaphore meaningless (this was a
  real bug, removed on purpose).

Consequence to respect: on timeout the worker thread is a **daemon and keeps running** — the
GPU stays busy and the semaphore slot stays held after the client got its 504. Raising the
timeout, adding retries, or "just" cancelling the request all interact with this. Do not
change one side without the other.

## Device placement

`_get_device()` falls back CUDA → MPS → CPU, honoring `models.<name>.device_id` for CUDA,
with warnings when `device_id` is not an int or exceeds `torch.cuda.device_count()`. It
degrades rather than crashes — deliberately, so a config typo does not take the service down.

When touching this: MPS is the dev machine's path and CUDA is prod's, so a change verified
locally has, by construction, not been verified on the path that matters. Verify on orange.

## Library patches

`gigaam_patches.py` holds monkey-patches for the `gigaam` library as individual functions,
called explicitly from `GigaAMTranscriber._load_model()`. A failing patch **crashes with a
clear message** — that is intentional: it means the installed library version no longer
matches what the patch assumes, and silently continuing would produce wrong transcriptions
rather than an error. Never wrap these in a bare `except`.

Keep patches isolated in that module. A monkey-patch inlined into the transcriber becomes
invisible to the next person debugging a library version bump.
