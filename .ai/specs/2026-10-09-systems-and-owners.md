<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Systems and owners assigned to secrets

- **Status:** in progress
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

Implements ADR-010 and [ADR-017](../adr/ADR-017-sqlite-holds-assignments.md) (assignments in their own tables,
keyed by secret identity; the DB now needs backups).

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | DB: `systems` (id UUID, unique name, description, cmdb_uri, asset_number, created_at), `system_owners`, and assignment tables `secret_systems` / `secret_owners` keyed by `vault_name` + `engine_id` + `secret_path` (ADR-017), all new tables in migration step 3 (ADR-023); `secret_metadata_cache` is unchanged | models | `tests/test_database.py`: assignments survive deleting and re-syncing the cache row; works on a pre-0.7 DB | done | 9af6bfb |
| 2 | Models: `chronowarden/models/system.py` (`SystemBase/System/SystemCreate/SystemUpdate`, like `owner.py`); `SecretMetadataResponse` gains `system` and `owners` (own + effective) | models | Model tests; mirrored in `frontend/src/lib/types/` | done | 9af6bfb |
| 3 | API: `/api/v1/systems/` CRUD plus system owners; register the router | [api](../../chronowarden/api/AGENTS.md) | `tests/test_systems.py` (404/422 cases included) | done | 9af6bfb |
| 4 | API: `PUT /api/v1/secrets/{id}/system` with `{"system_id": "…" \| null}` and `PUT /api/v1/secrets/{id}/owners` with `{"owner_ids": [...]}` (replace the whole value, idempotent); `{id}` is resolved to the secret identity before storing. `GET /secrets/` filters `system_id`, `owner_id`, `unassigned`. Each change is logged with `logger.info` (secret identity, old value, new value) | api | Tests for assign, change, unassign, unknown IDs, and the log line | done | 9af6bfb |
| 4a | Deleting: `DELETE /systems/{id}` returns 409 listing the assigned secrets while any remain; `DELETE /owners/{id}` removes that owner from every secret and system, then deletes it | api | Tests for 409 with its list, for delete after unassigning, and for owner removal | done | 9af6bfb |
| 5 | Frontend: systems API, store and modal (like owners); system and owner fields in `SecretModal` with an explicit "Unassigned" option; system filter; system column in the secrets table | [frontend](../../frontend/AGENTS.md) | `npm run check` clean; "Unassigned" shown, not blank | todo | |
| 6 | Dashboard: group stats and ExpiryHorizon by system | frontend | Manual check with a dev vault (`dev-setup.py`) | todo | |
| 7 | Architecture and README: systems and owners in `main.c4`; README feature list, API endpoints, and "back up `chronowarden.db`" (ADR-017); models `AGENTS.md` | [architecture](../../architecture/AGENTS.md) | Model and docs match the code | todo | |

## Validation

`uv run pytest`, `uv run black --check .`, `uv run ruff check .`, `cd frontend && npm run check`

## Decisions (2026-10-11)

- **Storage:** assignments live in their own tables keyed by `vault_name` + `engine_id` + `secret_path`, not the
  cache row `id` (ADR-017).
- **Endpoints:** `PUT /secrets/{id}/system` and `PUT /secrets/{id}/owners`, replacing the whole value. Bulk assignment
  from the system side (`PUT /systems/{id}/secrets`) can come later without breaking these.
- **Deleting:** a system that still has secrets → 409 with the list; an owner → removed from its secrets and systems.
- **Audit:** structured `logger.info` lines now; they move into the audit log when #24 lands (ADR-014).
