<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Generic provider registry

- **Status:** draft
- **Date:** 2026-10-09
- **Issue:** none

## Goal

A second secret provider (e.g. GitLab CI variables, Azure Key Vault) can be added by writing one integration
class plus its config model, without editing Vault-specific code in the manager, API or sync.

## Non-goals

- Implementing a second provider (separate spec).
- Changing the Vault behaviour or required policy.

## Scope

`chronowarden/integrations`, `chronowarden/config.py`, `chronowarden/metadata.py`, `chronowarden/api`,
`architecture/`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [integrations](../../chronowarden/integrations/AGENTS.md)
- [core](../../chronowarden/AGENTS.md)
- [ADR-003](../adr/ADR-003-pluggable-integrations-vault-first.md)
- [ADR-004](../adr/ADR-004-metadata-only-access.md)

## ADRs affected

ADR-003: write ADR-010 "Generic provider registry", superseding ADR-003's manager design.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Write ADR-010 with the chosen design; mark ADR-003 `Superseded by ADR-010` | integrations, [.ai/adr](../adr/README.md) | ADR approved by the user | todo | |
| 2 | Make `BaseIntegration` an enforced interface (ABC or `Protocol`) that includes `write_secret_metadata`, `discover_engines`, `check_health`, `last_error_kind` | integrations | `VaultIntegration` passes; missing methods fail at definition/instantiation | todo | |
| 3 | Generalise `VaultManager` into a manager keyed by provider type, with config `type:` defaulting to `vault` for existing configs | integrations, core | Existing `config.example.yaml` loads unchanged; `tests/test_manager.py` green | todo | |
| 4 | Make `metadata.py` and the `/vault`/`/sync` APIs depend on the interface, not `VaultIntegration` | core, [api](../../chronowarden/api/AGENTS.md) | No `VaultIntegration` imports outside `integrations/` | todo | |
| 5 | Model providers in `architecture/main.c4` | [architecture](../../architecture/AGENTS.md) | Element for the external backend(s) exists | todo | |

## Validation

`uv run pytest`, `uv run black --check .`, `uv run ruff check .`

## Open questions

- Should `/api/v1/vault/*` be renamed (e.g. `/providers`), which breaks the frontend and API users?
