# Development Rules — Index

**Two tiers.** `.claude/rules/` is injected into every session — only process-wide rules live
there, keep it lean. `.claude/rules-scoped/` is NOT auto-loaded: each file is read on demand
when its path trigger fires (a PreToolUse hook reminds once per session on the first matching
edit). One concept = one file; pointers, not restatement.

## Always loaded (`.claude/rules/`)

- **`workflow.md`** — sizing (S/M/L) + model-choice axis, review gate, reality-facing
  acceptance, self-review, error-recovery ladder, **debugging intake**, hard rules,
  auto-lessons. *Single source of truth for the process.*
- **`coding-constraints.md`** — stdlib preference, no over-engineering, crash-on-missing-config,
  surgical changes, read-the-entry-file, anti-mirage validation.
- **`testing.md`** — where tests run (orange, over ssh) and why a green run is not evidence.
- **`documentation.md`** — `INVARIANT:`+`Why:` and `WHY:` markers, doc tiers, decision pinning.
- **`git-strategy.md`** — S/M straight to `dev`, branch only for L, pre-merge audit,
  `dev→main` only on explicit request.

## On demand (`.claude/rules-scoped/`) — READ BEFORE editing matching paths

| Trigger (files you are about to touch) | Read first |
|---|---|
| `app/audio/**` | `audio.md` — pipeline order, ffmpeg/sox return codes, temp files, format trap |
| `app/routes.py`, `app/infrastructure/validation.py` | `api.md` — route rules, OpenAI contract, validation |
| `app/core/**` | `transcribers.md` — registry/Protocol, adding a backend, concurrency, device fallback |

## Skills (invoke via `/command`)

- `/deploy` — deploy, restart, status, logs, rollback on orange (systemd `whisper.service`).
- `/review` — post-implementation self-review. Presents findings; never auto-fixes.
- `/retro` — session retrospective; writes a lesson only when a trigger fired.

## Artifacts

- `lessons/` — actionable rules extracted from real iterations (triggers in `workflow.md`).
  Flat folder, no index script. Each lesson's rule gets folded into the matching rules file.
- `.kilo/plans/` — implementation plans.

## Tooling

- **Format/lint**: `ruff` (config in `pyproject.toml`, line-length 120). Formatting runs
  automatically on every edit via a PostToolUse hook; lint manually with `ruff check app/`.
- **Tests**: on orange over ssh — see `testing.md`.

## Environment facts

- Prod: host `orange`, systemd unit `whisper.service`, port 5042, `http://stt.ai.gray`.
  Restart requires `root@orange`. Docker exists in the repo but is **not** the active runtime.
- Never edit `config.json` on the server — it legitimately differs from the local copy.

## Owed

- `/reality-audit` — a lore-style skill that verifies this file and `CLAUDE.md` against actual
  code (~monthly). Not written yet; the 2026-07-25 config overhaul served as the first audit
  and found four drifted claims.
