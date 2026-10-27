<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Generic provider registry

- **Status:** implemented
- **Date:** 2026-10-09
- **Issue:** #72

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

- [root AGENTS.md](../../../AGENTS.md)
- [integrations](../../../chronowarden/integrations/AGENTS.md)
- [core](../../../chronowarden/AGENTS.md)
- [ADR-003](../../adr/ADR-003-pluggable-integrations-vault-first.md)
- [ADR-004](../../adr/ADR-004-metadata-only-access.md)

## ADRs affected

ADR-003 superseded by [ADR-011](../../adr/ADR-011-provider-registry.md) (accepted 2026-10-14).

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Settle the open options in ADR-011, set it Accepted, mark ADR-003 `Superseded by ADR-011` | integrations, [.ai/adr](../../adr/README.md) | ADR approved by the user | done | 9c51683 |
| 2 | Make `BaseIntegration` an `abc.ABC` (ADR-011) that includes `write_secret_metadata`, `discover_engines`, `check_health`, `last_error_kind` | integrations | `VaultIntegration` passes; missing methods fail at definition/instantiation | done | 668e939 |
| 3 | Generalise `VaultManager` into a manager keyed by provider type, with config `type:` defaulting to `vault` for existing configs | integrations, core | Existing `config.example.yaml` loads unchanged; `tests/test_manager.py` green | done | 668e939 |
| 4 | Make `metadata.py` and the APIs depend on the interface, not `VaultIntegration`; rename `/vault/*` to `/providers/*` and `/sync/vault/{name}` to `/sync/provider/{name}`, frontend included | core, [api](../../../chronowarden/api/AGENTS.md), [frontend](../../../frontend/AGENTS.md) | No `VaultIntegration` imports outside `integrations/`; UI works against the new paths; CHANGELOG notes the break | done | e2ce338 |
| 5 | Model providers in `architecture/main.c4` | [architecture](../../../architecture/AGENTS.md) | Element for the external backend(s) exists | done | 8f99432 |

## Validation

`uv run pytest`, `uv run black --check .`, `uv run ruff check .`

## Decisions (maintainer, 2026-10-14)

See ADR-011: `abc.ABC`; `type:` per backend entry (default `vault`); `/providers` paths now; only providers with
per-secret key/value metadata. Azure Key Vault and GCP Secret Manager follow as separate specs after this one.
