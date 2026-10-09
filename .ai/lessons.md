<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Lessons

Corrections from the user that should not repeat. Add one entry per correction, newest first. Read this only
when the Task Router or a scoped file points here, or before starting a spec.

## Format

```markdown
### YYYY-MM-DD: <tag or module, e.g. api, frontend, commits>

- **Mistake:** what the agent did.
- **Rule:** what to do instead, stated so it can be checked.
```

If a lesson becomes a lasting rule, move it into the narrowest `AGENTS.md` it applies to and delete it here.

## Entries

### 2026-02-07: gitignore

- **Mistake:** a `lib/` pattern in the root `.gitignore` silently excluded `frontend/src/lib/`, so the files an agent
  wrote were never committed (PR #5).
- **Rule:** anchor root-only ignore patterns (`/lib/`), and after adding files check `git status` to confirm they
  are tracked.
