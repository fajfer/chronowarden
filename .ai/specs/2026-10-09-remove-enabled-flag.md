<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Remove the `enabled` leftover and API severity overrides

- **Status:** draft
- **Date:** 2026-10-09
- **Issue:** #73 (decision: PR #11 Q4 + Q6, reconfirmed 2026-10-09)

## Goal

Config is the only place to set severity, as decided in PR #11 (Q4: secret overrides in config only; Q6:
`severity: none` replaces `chronowarden_enabled`). The `enabled` field, the `chronowarden_enabled` key and
severity editing through `PATCH /secrets/{id}` disappear from the API, DB, sync, UI and README.

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
| 4 | Remove severity from `PATCH /secrets/{id}`; remove the endpoint and the unused client functions (`updateSecretMetadata`, `editSecretMetadata`; no component calls them), unless the [systems spec](2026-10-09-systems-and-owners.md) reuses a narrow `PATCH` for assignments | [api](../../chronowarden/api/AGENTS.md), [frontend](../../frontend/AGENTS.md) | `PATCH` returns 405; tests updated; `npm run check` clean | todo | |
| 5 | README: drop `chronowarden_enabled`, the `enabled` query param and `PATCH`; document `severity: none` and config-only overrides | core | README matches the API | todo | |

## Validation

`uv run pytest`, `uv run black --check .`, `cd frontend && npm run check`

## Open questions

- Existing `chronowarden.db` files keep the `enabled` column (no migrations). Is leaving the column unused
  acceptable, or should the DB be recreated?
