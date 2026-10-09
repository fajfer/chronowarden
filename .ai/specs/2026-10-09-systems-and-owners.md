<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Systems and owners assigned to secrets

- **Status:** draft
- **Date:** 2026-10-09
- **Issue:** #61

## Goal

An operator can create systems (name, description, CMDB URI, asset number, owners) and assign each secret to at most
one system and to owners. Dashboard, filters and reports can group rotation risk by system and owner, and unassigned
secrets are clearly shown as unassigned.

## Non-goals

- Authentication and enforcing "only owners may edit" (ADR-015; editing is open until then, per ADR-010).
- Writing system or owner assignments to the secret backend.
- Automatic or bulk assignment by naming rules, and syncing systems from a CMDB.
- Alert labels for owner and system (alerting milestone, ADR-012).

## Scope

`chronowarden/database.py`, `chronowarden/models/`, `chronowarden/api/`, `chronowarden/app.py`, `frontend/`,
`architecture/main.c4`, `README.md`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [models](../../chronowarden/models/AGENTS.md)
- [api](../../chronowarden/api/AGENTS.md)
- [ADR-010](../adr/ADR-010-owners-systems-and-permissions.md)

## ADRs affected

Implements ADR-010. Relies on ADR-005 (SQLite; first schema change on an existing table).

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | DB: `systems` (id UUID, unique name, description, cmdb_uri, asset_number, created_at), `system_owners`, `secret_owners`, nullable `secret_metadata_cache.system_id`; add the column with a guarded `ALTER TABLE` (`PRAGMA table_info`) | models | `tests/test_database.py` covers a fresh DB and an existing DB without the column | todo | |
| 2 | Models: `chronowarden/models/system.py` (`SystemBase/System/SystemCreate/SystemUpdate`, like `owner.py`); `SecretMetadataResponse` gains `system` and `owners` (own + effective) | models | Model tests; mirrored in `frontend/src/lib/types/` | todo | |
| 3 | API: `/api/v1/systems/` CRUD plus system owners; register the router | [api](../../chronowarden/api/AGENTS.md) | `tests/test_systems.py` (404/422 cases included) | todo | |
| 4 | API: assign or unassign a secret's system and owners via dedicated endpoints (shape: see open questions); `GET /secrets/` filters `system_id`, `owner_id`, `unassigned` | api | Tests for assign, change, unassign and unknown IDs | todo | |
| 5 | Frontend: systems API, store and modal (like owners); system and owner fields in `SecretModal` with an explicit "Unassigned" option; system filter; system column in the secrets table | [frontend](../../frontend/AGENTS.md) | `npm run check` clean; "Unassigned" shown, not blank | todo | |
| 6 | Dashboard: group stats and ExpiryHorizon by system | frontend | Manual check with a dev vault (`dev-setup.py`) | todo | |
| 7 | Architecture and README: systems and owners in `main.c4`; README feature list and API endpoints | [architecture](../../architecture/AGENTS.md) | Model and README match the code | todo | |

## Validation

`uv run pytest`, `uv run black --check .`, `uv run ruff check .`, `cd frontend && npm run check`

## Open questions

- Endpoint shape: dedicated endpoints (decided 2026-10-09, `PATCH /secrets/{id}` was removed in #73); exact paths
  such as `PUT /secrets/{id}/system` and `PUT /secrets/{id}/owners` to be settled.
- Deleting a system or owner that is still assigned: unassign automatically (`ON DELETE SET NULL` needs
  `PRAGMA foreign_keys`, which is off today) or refuse with 409?
- Should assignment changes already go to the audit log (ADR-014), or does the audit log come after this spec in the
  milestone?
