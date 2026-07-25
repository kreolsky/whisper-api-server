---
alwaysApply: true
---

# Coding Constraints

* Use standard library and framework built-ins. No custom algorithms when a one-liner exists.
* No over-engineering, no redundant abstractions. Simplest tool for the job.
* No nested conditional chains. Use lookup dictionaries and early returns.
* Crash on missing configs/dependencies. No default values for critical data
  (`model_path`, `language`). A wrong-but-plausible default is worse than a startup crash.
* Semantic naming and strict type hints mandatory.
* Extract shared utilities only for genuinely reusable operations.
* Code comments and docstrings in **Russian** (project convention). Rules, plans, and commit
  messages in **English**.
* Formatting is `ruff format`'s job (config in `pyproject.toml`, applied automatically on
  edit) — never hand-tune whitespace or line breaks.

## Surgical changes

Don't "improve" adjacent code, comments, or formatting. Match existing style. Remove
imports/variables/functions that YOUR changes made unused — don't touch pre-existing dead
code unless asked.

**When consolidating duplicated code into a shared helper**: if the two sites diverge in
behavior (different constants, thresholds, ffmpeg flags), STOP and ask which behavior to
keep. Never assume the divergence is accidental — in audio processing it usually is not.

## Read the entry file — don't infer a contract from one symbol

Before building ON or NEXT TO an existing mechanism (the transcriber registry, the audio
pipeline, async tasks, the validator), READ its module docstring and the protocol it
implements. Do NOT reconstruct its contract from a single signal — one regex, one type, one
call site. A particular signal describes an edge case or a legacy tolerance, not the canon.

Concretely: `app/core/base.py` is a `runtime_checkable` **Protocol**, not a base class.
Reading one transcriber and copying its `__init__` teaches you that file's habits, not the
contract. The contract is the Protocol.

This is the design analog of "observe before patch": there, reproduce before patching; here,
read the entry file before designing on top of it. The trigger is the moment you are about to
write "new format / new module / new target" over something that already exists.

## Anti-mirage validation

After generating or modifying >20 lines, verify:

* every `import` references a real module/export;
* every call matches a real signature;
* every config key you read is actually produced by `load_config()` in `app/core/config.py`;
* new dependencies are in `requirements.txt`;
* any endpoint you reference from a client actually exists in `app/routes.py`.

If unsure whether an API exists, grep before using it. Then verify with `ruff check app/`
and the test commands in `testing.md`.
