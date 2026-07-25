---
name: review
description: >
  Post-implementation self-review. Use when: user says "ревью", "проверь изменения",
  "review", "самопроверка", "посмотри что получилось", or when a review-gate trigger
  from workflow.md fired (3+ files changed, new module/endpoint/backend, user said
  "готово"/"done"/"push"/asked for a commit).
  Do NOT use for: reviewing someone else's PR, or before the work is finished.
---

# Post-Implementation Self-Review

Trigger conditions, the self-review checklist, and the decision-pinning rule live in
`.claude/rules/workflow.md` and `.claude/rules/documentation.md` — follow them, don't restate.

**Never auto-fix.** Present findings + a fix plan, then wait for approval.

## 1. Compliance block

Output exactly:

```
━━━ REVIEW ━━━
Scope:       [S/M/L — matches what was actually touched?]
Doc markers: [PASS / MISSING — list]   (INVARIANT+Why on new guards, module docstrings)
Tests:       [PASS / FAIL / NOT RUN — why]
Acceptance:  [PASS — live evidence quoted / VIOLATION — no live run / EXEMPT — no runtime surface]
```

`Acceptance` per `workflow.md`: our suite is entirely mock-based, so for any change with a
runtime surface "done" requires a real request against the running service with the output
quoted verbatim. Diffs touching only docs/config/tests are EXEMPT — say so explicitly.

## 2. Diff review

1. `git diff --stat` — only expected files changed? Flag anything unexpected.
2. Full `git diff` — look for:
   - incomplete guards (an error path that logs but continues);
   - `subprocess.run` without checked return code (`rules-scoped/audio.md`);
   - temp files created outside `create_temp_file()` or missing from cleanup;
   - duplicated literals (format lists, MIME types, size limits) that should be one constant;
   - leftover debug logging / commented-out code;
   - changed response shape on `/v1/*` — an OpenAI-contract break (`rules-scoped/api.md`).
3. Grep old names after any rename.
4. `ruff check app/` — lint clean.

## 3. Decision-pinning check

Per `documentation.md`:

- A bugfix in a repeatedly-regressing area MUST add or tighten an `INVARIANT:` + `Why:` on
  the line that broke. Flag its absence.
- Flag any new `INVARIANT:` lacking a `Why:`.
- Flag any marker that now contradicts actual behavior — stop and ask which side is wrong;
  never silently fix either one.

## 4. Findings card

Present as a card, most severe first. For each: file:line · what breaks · concrete failure
scenario (inputs → wrong output). Separate "must fix" from "worth considering". Then the fix
plan, and **halt for approval**.

If nothing survives scrutiny, say so plainly — a clean review is a real outcome, not a
failure to find something.
