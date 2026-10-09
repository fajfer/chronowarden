<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# architecture: LikeC4 model

## Purpose

The system architecture is kept as code in this directory, in the [LikeC4](https://likec4.dev) DSL
([ADR-002](../.ai/adr/ADR-002-architecture-as-code-likec4.md)).

## Files

- `specification.c4`: element kinds `actor`, `system`, `component`; relationship kind `api`.
- `main.c4`: model (`user`, `chronowarden` with `frontend`, `backend`, `metadata`, `database`) and the `index`
  view.
- `integrations.c4`: comment-only notes on integration behaviour (custom metadata keys, auth methods, severity
  cascade, owners, `severity: none`).

## Contracts

- Always consult the architecture MCP server at <http://localhost:33335/sse> to get knowledge of the architecture
  model. If it is unreachable, read the `.c4` files and say so in your report.
- If a change affects the architecture, fix the architecture accordingly in the same change.
- Notes in `integrations.c4` describe behaviour that code and docs rely on. Keep them true when that behaviour
  changes.

## How to

- **New component or relation**: add it under `chronowarden` in `main.c4` with `technology` and `description`;
  use `-[api]->` for calls, like the existing relations. Cross-file references need full FQNs
  (e.g. `chronowarden.backend`).
- **New integration**: add it to the model and add a note to `integrations.c4`
  ([integrations](../chronowarden/integrations/AGENTS.md)).
- **New element or relationship kind**: declare it in `specification.c4` first.

## Gotchas

- There is no `likec4.config.*` / `.likec4rc` in the repo; the directory is used as the project root.
- `npx likec4 validate` crashes in the maintainer's environment (2026-10-09), so there is no working automated check.
  Review `.c4` diffs by reading them.
- The model has no element for the external secret backends (Vault/OpenBao) yet; integrations are described only
  in the `integrations.c4` comments.
- `integrations.c4` lists `chronowarden_owner` as a custom metadata key, but no code reads or writes it.
- SPDX headers in `.c4` files use `//SPDX-...` line comments.

## Related ADRs

[ADR-002](../.ai/adr/ADR-002-architecture-as-code-likec4.md),
[ADR-003](../.ai/adr/ADR-003-pluggable-integrations-vault-first.md)

## Validate

No working validator (see Gotchas). Check that every FQN you reference exists in `main.c4`.
