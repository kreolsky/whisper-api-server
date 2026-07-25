# Lessons

Actionable rules extracted from real iterations. Written by `/retro`, and **only** when an
Auto-lessons trigger from `.claude/rules/workflow.md` fired:

- 3+ fix iterations on the same issue category;
- a new architectural pattern established;
- a non-obvious workflow optimization discovered.

## Format

`YYYY-MM-DD-short-slug.md`, in English:

- **What happened** — the observable symptom, not the diagnosis.
- **Root cause** — what was actually true.
- **Actionable rule** — imperative, checkable, one or two sentences.
- **Code example** — wrong vs right, real code from this repo.

## The point

A lesson is evidence; the rule it yields belongs in `.claude/rules/` (or
`.claude/rules-scoped/`), because that is what gets loaded into the next session. A lesson
whose rule never reaches a rules file changes nothing.

Flat folder, no index script — at this repo's size `grep` is enough. Don't pad it: a folder
full of non-lessons stops being read.
