---
alwaysApply: true
---

# Documentation as Architecture

Code is the single source of truth. Document only what is **not inferable from the code**:
traps, not operations. Comments and docstrings in Russian.

## Markers (grep-able)

Two markers only — no `SYSTEM:`/`DEBT:`/`ARCH:` ledgers, no CI gates. At 20 source files
`grep` reaches everything; the markers exist to preserve *reasons*, not to build an index.

* **`INVARIANT: <rule>`** — a constraint that must hold, always followed by **`Why: <reason>`**
  on the same line or within the next two. Without the `Why:`, the marker gets deleted by the
  next refactor and the constraint silently dies. Goes on the **load-bearing line** — the
  branch, guard, early return, or ordering statement that enforces it, not at the top of the file.
* **`WHY: <reason>`** — a non-obvious implementation choice: a library workaround, a lazy
  import, an ffmpeg flag that looks redundant but is not.

Natural homes here: the concurrency semaphore in `transcription_service.py`, the audio
pipeline ordering in `processor.py`, the lazy `discover_transcribers()` import, the
device-fallback chain (CUDA → MPS → CPU), and the `gigaam_patches.py` crash-on-failure choice.

**Applied to new and touched code only.** No retro-conversion sweep — that would violate the
surgical-change rule in `coding-constraints.md`.

## Single home for contracts

A contract lives in ONE place — the marker on the load-bearing line. Rules files and lessons
REFERENCE it (`see INVARIANT in app/core/transcription_service.py`), never restate it: a
copied contract drifts from the code silently.

## Docstrings

* Every module: one-line docstring.
* **Tier 1** (non-obvious behavior, side effects, error conditions): full docstring.
* **Tier 2** (name + types tell the story): one line.
* **Tier 3** (trivial getters, dataclasses, <30-line helpers): none.
* Never document what type hints already say, or what the stdlib does.

## Decision pinning

User-stated business logic (which model is default, what happens on an unknown `model`,
size limits, history retention, timeout behavior) MUST be captured in the code that enforces
it — a rule living only in chat is a future regression.

```python
# INVARIANT: <правило словами пользователя>.
# Why: <причина, которую он назвал>.
```

* **User states a rule** → restate it in one line and ask *"Pin as INVARIANT?"* — no defaults.
  On yes, mark the load-bearing line; if no such line exists yet, note it in the plan.
* **Bugfix in a repeatedly-regressing area** → the recurrence means it was never pinned. The
  fix MUST add or tighten an `INVARIANT:` + `Why:` on the line that broke. `/review` flags
  its absence.
* **Don't** restate what the code already says, and don't mark trivial code.
* **Maintenance**: markers move with their code. A marker that contradicts actual behavior →
  stop and ask which side is wrong. Never silently "fix" either one.
