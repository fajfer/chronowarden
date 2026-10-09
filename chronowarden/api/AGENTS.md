<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# api: FastAPI routers

## Purpose

REST API used by the frontend and by operators. Every router is mounted under `/api/v1` in `chronowarden/app.py`.

## Files

| File | Prefix | Endpoints |
|---|---|---|
| `health.py` | none | `GET /health`, `/info`, `/ready`, `/metrics` (Prometheus) |
| `secrets.py` | `/secrets` | `GET /` (filters `vault_name`, `engine_id`, `severity`, `enabled`), `GET /{id}`, `PATCH /{id}` |
| `sync.py` | `/sync` | `POST /vault/{vault_name}` |
| `vault.py` | `/vault` | `GET /instances`, `/health`, `/{name}/health`, `/{name}/secrets/list`, `POST /{name}/secrets/metadata` |
| `owners.py` | `/owners` | CRUD for owners, `POST/DELETE` notification routes, `POST /{id}/test-route/{route_id}` |
| `__init__.py` | n/a | exports `*_router`; add new routers here and include them in `app.py` |

## Contracts

- Full paths are `/api/v1/<prefix>/...`. Kubernetes probes use `/api/v1/health`.
- Response shapes come from `chronowarden/models` (`SecretMetadataResponse`, `Owner`, …); the frontend mirror
  rule is in [models](../models/AGENTS.md).
- Status mapping used across routers: unknown vault/secret/owner → 404; vault not connected or backend write failed
  → 503; invalid severity → 422, with `detail` listing the allowed values.
- `severity` input (query or body) must be a configured expiry profile or `"none"` (`_validate_severity_input`).
- `PATCH /secrets/{id}` writes to the backend first, then the cache. If the backend write fails, the cache is not
  touched.
- `POST /sync/vault/{name}` also (re)starts the manager's reconnect loop.

## How to

- **Add an endpoint**: add a function to the matching router with `summary=`, `response_model=` and a docstring
  with `Raises:`. Get dependencies through the module's lazy `_get_app_dependencies()` / `_get_db()` /
  `_get_vault_manager()` helper; never import `chronowarden.app` at module top level.
- **Add a router**: new file with `router = APIRouter(prefix=..., tags=[...])`, export it in `__init__.py`, call
  `app.include_router(..., prefix="/api/v1")` in `app.py`, and add the tag to `openapi_tags`.
- **Test it**: build a bare `FastAPI()` app, `include_router(router, prefix="/api/v1")`, use a `Database` on
  `tmp_path`/`:memory:`, and `patch("chronowarden.api.<module>._get_app_dependencies", return_value=(...))`.
  See `tests/test_secrets.py`.

## Gotchas

- `_compute_status` uses a fixed 30-day WARNING window, not a per-profile threshold. See
  [the spec](../../.ai/specs/2026-10-09-per-profile-alert-threshold.md).
- `_get_app_dependencies()` returns a different tuple order per module: `secrets` → `(db, config, manager)`,
  `sync` → `(manager, config, db)`.
- `POST /owners/{id}/test-route/{route_id}` only logs; no notification is sent yet.
- `vault.py` increments `VAULT_OPERATIONS_TOTAL{operation,status}`. Reuse the existing label values (see
  [metrics](../metrics/AGENTS.md)).

## Related ADRs

[ADR-004](../../.ai/adr/ADR-004-metadata-only-access.md), [ADR-006](../../.ai/adr/ADR-006-config-source-of-truth.md),
[ADR-007](../../.ai/adr/ADR-007-sveltekit-spa-served-by-fastapi.md)

## Validate

`uv run pytest tests/test_secrets.py tests/test_sync_api.py tests/test_vault_api.py tests/test_owners.py tests/test_app.py`
