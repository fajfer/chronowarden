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

### 2026-11-07: security design

- **Mistake:** ADR-029 was drafted to block private and loopback webhook targets by default, against a threat that
  wasn't checked: the metadata risk was overstated (webhooks are POSTs whose response is never read), and the
  default would have broken every internal or air-gapped deployment.
- **Rule:** threat-model every security concern before proposing it or a fix for it: who the attacker is, what
  they can actually do with the code as it is, and who a default would break.

### 2026-10-10: specs, scope

- **Mistake:** asked to "prepare a document extending the 0.7 scope", the agent wrote specs straight into
  `.ai/specs/` and edited the specs index, without asking the open questions first.
- **Rule:** a scope change is a proposal until the maintainer approves it: put it in one dedicated file outside
  `.ai/`, ask the open questions while drafting, and touch `.ai/` only after approval.

### 2026-02-07: gitignore

- **Mistake:** a `lib/` pattern in the root `.gitignore` silently excluded `frontend/src/lib/`, so the files an agent
  wrote were never committed (PR #5).
- **Rule:** anchor root-only ignore patterns (`/lib/`), and after adding files check `git status` to confirm they
  are tracked.
