---
name: retro
description: >
  Session retrospective — extract a lesson from what went wrong and fold the rule into
  the rules files. Use when: user says "ретро", "ретроспектива", "итоги сессии", "уроки",
  "retro", or after a session where an Auto-lessons trigger from workflow.md fired.
  Do NOT use for: routine session wrap-up where nothing was learned.
---

# Session Retrospective

Auto-lessons triggers live in `.claude/rules/workflow.md` — don't restate them.

## 1. Summary

What was accomplished; what broke; root cause of each fix.

## 2. Decide whether there is a lesson

Write one **only** if a `workflow.md` trigger fired:

- 3+ fix iterations on the same issue category;
- a new architectural pattern established (a new backend, a new audio source);
- a non-obvious workflow optimization discovered.

Otherwise say "no lesson — no trigger fired" and stop. A lessons folder padded with
non-lessons stops being read, which costs more than the lesson was worth.

## 3. Write the lesson

- Check existing `lessons/*.md` for the same topic first — **update, don't duplicate**.
- `lessons/YYYY-MM-DD-short-slug.md`, structure:
  - **What happened** — the observable symptom, not the diagnosis.
  - **Root cause** — what was actually true.
  - **Actionable rule** — imperative, checkable, one or two sentences.
  - **Code example** — wrong vs right, real code from this repo.
- Written in English. Keep it short: if it exceeds a screen, the rule is not sharp enough.

## 4. Fold the rule into the rules files

**This is the step that matters** — `lessons/` is the evidence, `.claude/rules/` is what gets
loaded next session. A lesson whose rule never reaches a rules file will not change behavior.

- Process/debugging rule → `.claude/rules/workflow.md`.
- Code-style rule → `.claude/rules/coding-constraints.md`.
- Path-specific rule → the matching `.claude/rules-scoped/` file.
- Reference the lesson from the rule; never copy its full text (single home for contracts,
  `documentation.md`).

If the rule duplicates something already there, the real finding is that the existing rule
was not followed — consider whether it needs to be sharper or enforced by a hook instead.
