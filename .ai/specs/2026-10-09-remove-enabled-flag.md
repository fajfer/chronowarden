<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Remove the `enabled` leftover

- **Status:** draft
- **Date:** 2026-10-09
- **Issue:** none (decision: PR #11 Q6, reconfirmed 2026-10-09)

## Goal

`severity: none` is the only way to stop alerting on a secret, as decided in PR #11. The `enabled` field and the
`chronowarden_enabled` metadata key disappear from the API, DB, sync, UI and README.

## Non-goals

- Changing what `severity: none` means.
- Migrating existing `chronowarden_enabled` values in backends: per the pre-1.0 rule there is no compat shim.

## Scope

`chronowarden/api/secrets.py`, `chronowarden/models/secret.py`, `chronowarden/database.py`,
`chronowarden/metadata.py`, `chronowarden/api/sync.py`, `frontend/src/lib/{types,api,stores}`, `README.md`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [core](../../chronowarden/AGENTS.md)
- [ADR-006](../adr/ADR-006-config-source-of-truth.md)

## ADRs affected

None (implements ADR-006).

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Remove `enabled` from `SecretMetadataResponse`, `SecretMetadataUpdate`, the `GET /secrets` query and the `PATCH` write of `chronowarden_enabled`; remove it from the sync response | [api](../../chronowarden/api/AGENTS.md), [models](../../chronowarden/models/AGENTS.md) | `tests/test_secrets.py` and `tests/test_sync_api.py` updated and green; `enabled` param gives 422 or is ignored (decide) | todo | |
| 2 | Drop the `enabled` column and `SecretMetadataCache.enabled`; delete `is_secret_enabled` | [models](../../chronowarden/models/AGENTS.md), core | `tests/test_database.py`, `tests/test_metadata.py` green; plan for existing DB files written down (see models Gotchas: no migrations) | todo | |
| 3 | Frontend: remove `enabled` from types, `fetchSecrets`, `FilterState`/`setEnabled`, and any enable/disable UI | [frontend](../../frontend/AGENTS.md) | `npm run check` has no new warnings | todo | |
| 4 | README: drop `chronowarden_enabled`, the `enabled` query param and `enabled` in PATCH; document `severity: none` | core | README matches the API | todo | |

## Validation

`uv run pytest`, `uv run black --check .`, `cd frontend && npm run check`

## Open questions

- Existing `chronowarden.db` files keep the `enabled` column (no migrations). Is leaving the column unused
  acceptable, or should the DB be recreated?
