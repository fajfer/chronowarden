<!--
SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Development Guidelines

Rules for every task, plus a router to the one or two scoped files a task needs. Read this file, then only what
the **Task Router** points to. Module detail lives next to the code; decisions live in [.ai/adr](.ai/adr/README.md).

## Always

- Put an SPDX header on every new file (`SPDX-FileCopyrightText: <years> Damian Fajfer <damian@fajfer.org>` +
  `SPDX-License-Identifier: EUPL-1.2`), in the comment style of that file type. Files that cannot hold a comment
  get a `<file>.license` sidecar.
- Update the SPDX year range when it is stale, e.g. `2025-2026` becomes `2025-2027` in 2027.
- Type hints on all Python code; docstrings on public APIs.
- Keep functions focused and small; follow existing patterns exactly.
- New features require tests; bug fixes require regression tests; cover edge cases and errors.
- Keep changes minimal: only modify code related to the task at hand. DRY.
- Start with minimal functionality and verify it works before adding complexity.
- Run formatters before type checks.
- If a change affects components or their relations, update the model as described in
  [architecture](architecture/AGENTS.md).

## Ask First

- Anything that contradicts an Accepted ADR: propose a superseding ADR before changing code.
- Changing the Vault policy users must grant (README "Vault Permissions").
- Wiring up or deleting the reserved roadmap models (see [models](chronowarden/models/AGENTS.md)).

## Never

- Read, return or log secret values: Chronowarden works on metadata only
  ([ADR-004](.ai/adr/ADR-004-metadata-only-access.md)).
- Add a `Co-authored-by:` trailer for an AI assistant (AI assistants are not GitHub users; the convention is
  reserved for human collaborators). Use `Assisted-by:` instead.
- Use `logger.error()` inside an `except` block, or put the exception into a `logger.exception()` message.
- Add deprecation warnings or backward-compatibility shims before 1.0: change the code and its config directly
  (#16, #30).
- Catch bare `Exception`, except in top-level handlers that must not crash and in cleanup blocks (log at debug).

## Validation Commands

| What | Command |
|---|---|
| Format (Python) | `uv run black --check .` |
| Lint (Python) | `uv run ruff check .` |
| Tests (all) | `uv run pytest` |
| Tests (one module) | see the **Validate** section of the scoped file |
| Frontend types | `cd frontend && npm run check` |
| Agent docs budget + links | `python3 scripts/check_agents_docs.py` |

## Task Router

Shorthand: `<area>` means `<area>/AGENTS.md`. Read root + the listed files, nothing else.

| Task | Read |
|---|---|
| Add a new secret provider (GitLab, Azure KV, …) | [integrations](chronowarden/integrations/AGENTS.md), [architecture](architecture/AGENTS.md), [ADR-003](.ai/adr/ADR-003-pluggable-integrations-vault-first.md), [generic registry spec](.ai/specs/2026-10-09-generic-provider-registry.md) |
| Vault connection, auth, TLS or reconnect issue | [integrations](chronowarden/integrations/AGENTS.md), [ADR-009](.ai/adr/ADR-009-offline-tolerant-reconnect.md) |
| Add or change a REST endpoint | [api](chronowarden/api/AGENTS.md), [models](chronowarden/models/AGENTS.md) |
| Secret status, TTL, severity cascade, sync | [core](chronowarden/AGENTS.md), [ADR-006](.ai/adr/ADR-006-config-source-of-truth.md) |
| Add or change a config option | [core](chronowarden/AGENTS.md), [deploy](deploy/AGENTS.md) |
| DB schema or query change | [models](chronowarden/models/AGENTS.md), [ADR-005](.ai/adr/ADR-005-sqlite-metadata-cache.md) |
| Add or wire a Prometheus metric | [metrics](chronowarden/metrics/AGENTS.md) |
| UI page, component, store, theme | [frontend](frontend/AGENTS.md) |
| Filter bug in the secrets table | [frontend](frontend/AGENTS.md) (+ [api](chronowarden/api/AGENTS.md) if the bug is in a query param) |
| App startup, Sentry, SPA serving | [core](chronowarden/AGENTS.md), [ADR-007](.ai/adr/ADR-007-sveltekit-spa-served-by-fastapi.md) |
| Docker image, Compose, Kubernetes, CI | [deploy](deploy/AGENTS.md), [ADR-008](.ai/adr/ADR-008-container-and-deployment-targets.md) |
| Architecture model (LikeC4) | [architecture](architecture/AGENTS.md) |
| Record a decision | [.ai/adr](.ai/adr/README.md) |
| Plan a 3+ step task | [.ai/specs](.ai/specs/README.md) |

User docs in `docs/` (mkdocs) are written by a human; agents don't edit them unless asked.

## Conventions

- Commits: [conventional commits](https://www.conventionalcommits.org/).
- Every commit made in an AI-assisted session carries an `Assisted-by: <agent-name>/<model-id>` trailer, with both
  values substituted by the agent's own.
- Python style: black, line length 120 (ruff uses the same); PEP 8 naming (snake_case functions/variables,
  PascalCase classes, UPPER_SNAKE_CASE constants); f-strings for formatting.
- Divide code into files: keep class/model definitions separate from their implementation (e.g. `models/` vs
  `api/`, `integrations/`), and don't put everything in one file (#2).
- Line too long: break strings with parentheses, use multi-line calls, split imports.
- Types: explicit `None` checks for `Optional`, narrow string types; type-checker version warnings can be ignored
  if checks pass.
- Exceptions: use `logger.exception("Failed")` when catching. Catch specific exceptions where possible:
  - file ops: `except (OSError, PermissionError):`
  - JSON: `except json.JSONDecodeError:`
  - network: `except (ConnectionError, TimeoutError):`

## Workflow

1. Small task (1–2 steps): follow the router, change, run the scoped **Validate** command.
2. Task with 3+ steps: write a spec in [.ai/specs](.ai/specs/README.md) first. Each task in it lists its own
   **Load** files; read exactly those.
3. A decision that future work must respect: write an ADR in [.ai/adr](.ai/adr/README.md).
4. When the user corrects you, add an entry to [.ai/lessons.md](.ai/lessons.md) so it doesn't repeat.
