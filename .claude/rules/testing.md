---
alwaysApply: true
---

# Testing

`tests/test_all.py` — 23 tests across `TestConfig`, `TestRegistry`, `TestFileValidator`,
`TestHistory`, `TestAsyncTaskManager`, `TestTranscriptionService`. All mock-based.

## Where tests run

**On orange, over ssh — not locally.** `TestRegistry` calls `discover_transcribers()`, which
imports `whisper_transcriber` → torch + transformers + numpy. The macOS dev machine has no
such environment, and `requirements.txt` pins CUDA/Linux wheels that exclude macOS.

```bash
ssh orange "cd /home/text-generation/servers/whisper-api && \
  /home/serge/.miniconda/envs/whisper-api/bin/python -m pytest tests/ -q"
```

Baseline: `23 passed in 6.28s`.

**Trap: this runs the code checked out ON THE SERVER, not your working tree.** Push and
`git pull` on the server first, or you are testing the previous commit and will draw the
wrong conclusion. Verify with `git log --oneline -1` on the server when a result surprises you.

Local checks that do work without the ML stack:

```bash
python -m py_compile <file>          # syntax
ruff check app/                      # lint
ruff format --check app/             # formatting (the hook normally handles this)
```

## A green test is not evidence

A test written from the implementation, by its author, asserts what the code already does.
Our suite is entirely mock-based, so passing means "the mocks agree with themselves" — it
does not mean transcription works. Hence the reality-facing acceptance rule in `workflow.md`.

* **Assert over the DERIVED source, not a literal.** Walk the real thing —
  `get_registered_model_types()`, `app.url_map`, the actual list of supported extensions —
  so the assertion binds two components and covers the next member. A literal in the test
  mirroring a literal in the code drifts WITH it and never fails.
* **A test with no failing branch is not a test.** `if x: assert A else: assert B` passes on
  every outcome. If unsure which branch runs, print it once, then assert that one
  unconditionally.
* **Test the input that must be REFUSED.** A validator exercised only with valid audio is
  untested — the whole point of `FileValidator` is the file it rejects.
* **Verify with a different tool than you built with.** curl-ing your own endpoint the way
  you wrote it proves your path, not the one the OpenAI SDK client actually sends.
* **Never modify an existing test to make failing code pass.**

## Manual verification

For anything touching audio or inference, tests are not sufficient. Run a real transcription
against the running service and quote the output:

```bash
curl -s -X POST http://stt.ai.gray/v1/audio/transcriptions \
  -F "file=@test.wav" -F "model=gigaam"
```

Cover the formats the change could plausibly affect (wav / mp3 / opus / 3gp) — the audio
pipeline has a history of per-format breakage.
