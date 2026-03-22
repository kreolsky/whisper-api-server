# Development Rules

Living document. Updated after each session.

## Hard Rules

Non-negotiable. Violation = stop and fix before continuing.

* Branch freshness: Run `git fetch origin && git log HEAD..origin/dev --oneline` before work. Rebase if non-empty.
* Post-refactor verification: Verify all imports compile (`python -m py_compile <file>`) after dependency changes.
* Impact assessment: Ask how changes affect the rest of the project before implementation.
* 3+ Iteration Pivot: If a problem requires 3+ iterative fixes, propose a radical architectural simplification.
* Dependency removal audit: `grep -r 'import.*package'` all consumers, verify replacement covers every use case before removing.

## Git Strategy

* **Branch First**: Create feature branch from `dev` for multi-file or non-trivial changes. Minor features (single-concern, <=3 files) may be committed directly to `dev`. Never work directly on `main`.
* **Base Branch**: `dev` contains latest stable changes. Always branch from `dev`.
* **Release**: `dev` merged into `main` for production. Never push directly to `main`.
* **Clean Up**: Delete feature branches after merge into `dev`.

## Coding Constraints

* Use standard library and framework built-ins. No custom algorithms when a one-liner exists.
* No over-engineering, no redundant abstractions. Simplest tool for the job.
* No nested conditional chains. Use lookup dictionaries and early returns.
* Crash on missing configs/dependencies. No default values for critical data (model_path, language).
* Semantic naming and strict type hints mandatory.
* Extract shared utilities only for genuinely reusable operations.
* All code comments and docstrings in Russian (project convention).

## Testing

* No formal test suite yet. Verify changes with:
  - `python -m py_compile <file>` for syntax/import checks on each modified file.
  - `python -c "from app import WhisperServiceAPI"` for full import chain validation.
  - Manual API testing via web UI or curl against running server.

## Self-Review (after 3+ file changes)

1. `git diff --stat` -- verify only expected files changed.
2. Full diff review -- incomplete guards, duplicated literals, formatting.
3. Grep for old names after renames.
4. `python -m py_compile` on every modified `.py` file.

## Audio Processing Rules

* FFmpeg and SoX are external dependencies. Always check subprocess return codes.
* Temp files must be created via `create_temp_file()` from `app/infrastructure/storage.py` -- never raw `tempfile.mktemp`.
* Audio pipeline order matters: convert to WAV 16kHz -> normalize -> compress/expand -> add silence.

## Flask / API Rules

* New endpoints go in `app/routes.py` inside `_register_routes()`.
* All transcription endpoints delegate to `TranscriptionService.transcribe()`.
* New audio input methods: add a `get_*_file()` function in `sources.py` returning `(temp_path, filename, error)`.
* File validation runs through `FileValidator` -- never validate inline in routes.
* Configuration values accessed via `self.config.get()` with sensible defaults, except critical params which must crash if missing.

## Deploy

* Server: `ssh orange`, path `/home/text-generation/servers/whisper-api`
* Обновление: `git push` → `ssh orange "cd /home/text-generation/servers/whisper-api && git pull"` → перезапуск сервиса через systemd (`whisper.service`)
* Проверка: `ssh orange "curl -s http://localhost:5042/health"`
