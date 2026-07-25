---
alwaysApply: true
---

# Git Strategy

* **Branch first (L only)**: S and M changes commit straight to `dev`. Create a feature branch
  from `dev` only for Large work (new subsystem, cross-cutting, 8+ files). Never work on `main`.
* **Base branch**: `dev` holds the latest stable changes. Always branch from `dev`.
* **Branch freshness**: the SessionStart hook reports whether `dev` is behind origin. Rebase
  before starting new work if it fired.
* **Pre-merge audit**: `git diff dev <branch> --stat`, review every changed file, get user
  confirmation before merging.
* **Release**: `dev` → `main` only when the user explicitly asks. Never push to `main`
  automatically after a commit.
* **Clean up**: delete feature branches after merge into `dev`.
* **Commit messages in English** (`feat:`/`fix:`/`chore:` prefix). Commit only when asked.
* **Deploy is not a commit**: pushing to origin does not update the server. The server pulls
  and the systemd unit restarts — see the `/deploy` skill.
