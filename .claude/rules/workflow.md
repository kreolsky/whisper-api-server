---
alwaysApply: true
---

# Workflow (mandatory)

Single source of truth for: sizing, review gate, self-review, error recovery, debugging
intake, auto-lessons. Other rule files point here — they do not restate.

## Sizing

| Size | Criteria | Sequence |
|------|----------|----------|
| **S** Quick fix | single-concern, ≤2 files, no new endpoint | implement → verify |
| **M** Feature | multi-file, new endpoint / new audio source / new transcriber | scope → implement → `/review` → commit |
| **L** Epic | new subsystem, cross-cutting, 8+ files | scope → plan → implement → `/review` → commit |

Output the size explicitly at the start of M/L work: `━━━ SCOPE: [S/M/L] ━━━` + one-line task.

**Model choice is a separate axis from size.** Volume (how many files) is decomposable —
any model handles a big flat change step by step. What is not decomposable is how much
must be held simultaneously: an `INVARIANT:` on the path, the concurrency semaphore, the
audio pipeline ordering, or a device-placement decision. Any of those → Opus regardless of
file count. Pure volume without invariants → Sonnet. Mechanical/cosmetic → Haiku.

## Review gate

Self-initiate `/review` — never wait to be asked, never auto-fix. Trigger when ANY holds:

- 3+ files changed (`git diff --stat`).
- New module / endpoint / transcriber backend.
- User says "готово", "done", "push", or asks for a commit.

Flow: finish work → `/review` → present findings + fix plan → wait for approval → then fix.

**Acceptance is reality-facing.** Our entire test suite is mock-based, so a green run proves
the mocks agree with themselves — it says nothing about transcription. For any change with a
runtime surface, "done" additionally requires driving the affected flow for real (a request
against the running service) and quoting the observed output verbatim. Exempt: diffs touching
only docs/config/tests with no runtime surface — state the exemption explicitly.

## Self-review (after 3+ file changes)

1. `git diff --stat` — only expected files changed.
2. Full diff — incomplete guards, duplicated literals, leftover debug logging.
3. Grep old names after renames.
4. `ruff check app/` and the test suite (`.claude/rules/testing.md`).

## Error recovery — escalate per failed attempt

1. **Retry** — re-read the error; check types/imports/signatures. Max 3.
2. **Instrument** — add logging, reproduce, read actual output before coding another fix. Max 2.
3. **Pivot** — step back, propose a simpler approach to the user. Do NOT implement without approval.
4. **Stop** — write up tried/observed/hypotheses to `lessons/`, ask for guidance.

## Debugging intake (meta-rule)

On any bug report, in this order:

1. **`git status` first, unconditionally.** In-flight changes *are* the running code.
2. **Vague report** ("не работает", "пусто", "сломалось") → ask ONE batched question for the
   missing specifics (exact request, audio format, model, response body, first-vs-Nth,
   regression-vs-never-worked) BEFORE reproducing. A stack trace or exact error text in the
   report already counts as specific. "Minimize questions" applies to implementation
   hand-holding, NOT debugging — one targeted question saves 10+ blind tool calls.
3. **Name hypothesis #1 AND its falsifier**: "H: X is broken. Falsifier: code at Y already
   does Z / my repro succeeds." An observation you ALREADY hold that falsifies it ⇒ drop the
   hypothesis. No patching it anyway, no caveats, no more digging in that same code.
4. **If your repro WORKS while the user reports broken**, the contradiction means your
   assumption about *what* is broken is wrong. The next message is a question to the user,
   not another investigation step.
5. **"Missing/disabled in case X"** = a gating condition (`if not config.X`, an early return,
   a format check). Locate it with one grep; reserve live reproduction for real runtime bugs.
6. **Server-side bug** → check the service is actually running the code you think it is:
   `journalctl -u whisper.service` start time vs the commit time on the server. A stale
   process after a `git pull` without restart looks exactly like a logic bug.

## Hard rules (non-negotiable)

- **Branch freshness**: the SessionStart hook prints whether `dev` is behind origin — rebase
  if it fired. Mid-session, re-check with `git fetch origin && git log HEAD..origin/dev --oneline`.
- **Impact assessment**: ask how a change affects the rest of the project before implementing.
- **Observe before patch**: for timing/concurrency bugs (async tasks, the transcription
  semaphore, model loading), instrument and reproduce BEFORE writing a fix. Code analysis
  alone yields plausible-but-wrong hypotheses.
- **Name the class on the 2nd fix**: before writing fix #2 for a symptom that rhymes with fix
  #1 in the same area, write one sentence — "the general class of inputs that breaks here is
  ___". If the class has >2 members, the fix is a normalization over the class, NOT another
  `if member_k` branch. This is the audio-format trap specifically: 3gp, opus, and the next
  format each got their own patch.
- **Size limits**: file > 500 lines → propose a split. Function > 50 lines → split.
- **Dependency removal audit**: `grep -r 'import.*<package>'` across all consumers; verify the
  replacement covers every use case before removing.
- **Post-refactor verification**: `ruff check app/` + the test suite after dependency changes.
- **Never edit `config.json` on the server** — it legitimately differs from the local copy.

## Auto-lessons

Write `lessons/YYYY-MM-DD-short-slug.md` when ANY holds:

- 3+ fix iterations on the same issue category.
- A new architectural pattern established (a new backend, a new audio source type).
- A non-obvious workflow optimization discovered.

Structure: What happened · Root cause · Actionable rule · Code example (wrong vs right).
Then fold the rule into the matching `.claude/rules/` file — the lesson is the evidence,
the rule is what gets loaded next session.
