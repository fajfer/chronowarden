<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# models: API schemas and the SQLite cache

## Purpose

Pydantic request/response schemas (`chronowarden/models/`) and the SQLite metadata cache
(`chronowarden/database.py`), which stores synced secret metadata, engine overrides and owner profiles.

## Files

- `secret.py`: `SecretStatus` (`expired`/`warning`/`ok`/`no_ttl`), `SecretMetadataResponse`,
  `SecretMetadataUpdate` (trims severity, rejects blank).
- `owner.py`: `Owner*`, `NotificationRoute*` (route `type` is `email` or `webhook`).
- `engine.py`, `entity.py`, `router.py`: **reserved for the roadmap, not wired.** Engine kinds (Azure Key Vault,
  X.509, manual), users/groups with permission levels (RBAC), notification routers (email/webhook/Slack). Nothing
  imports them. Wiring or deleting them is in root **Ask First**.
- `../database.py`: `Database`, `SecretMetadataCache`, `EngineConfigRow`, `DEFAULT_DB_PATH`.

## Contracts

- Tables: `secret_metadata_cache` (unique `vault_name, engine_id, secret_path`), `engine_config` (unique
  `vault_name, engine_id`), `owners`, `notification_routes` (`type IN ('email','webhook')`).
- `SecretMetadataResponse` fields are mirrored in `frontend/src/lib/types/Secret.ts`, `Owner` in `Owner.ts`:
  changing a field means changing both.
- `full_path` is computed as `vault_name/engine_id/secret_path`.
- `Database` uses one shared connection (`check_same_thread=False`) in WAL mode. Every method takes
  `self._conn_lock` (an `RLock`) and calls `_require_connection()`, which logs and returns `None` when the DB is
  not connected. Callers get `None`/empty results instead of an exception.
- `upsert_secret_metadata` overwrites `updated_time, ttl, severity, enabled, last_synced` on conflict.

## How to

- **Add a column**: update `_create_tables`, the `SecretMetadataCache` model, every `SELECT` column list and row
  mapping in `database.py`, then the response model and the frontend type. Add tests in `tests/test_database.py`.
- **Dynamic `UPDATE`**: build the `SET` clause only from fixed column names chosen in code (see `update_owner`,
  `update_secret_metadata_fields`) and pass values as `?` params. Never interpolate caller-supplied names
  (`d773fc6`).
- **Test**: the `db` fixture in `tests/test_database.py` (`Database(db_path=tmp_path / "test.db")`) or
  `Database(Path(":memory:"))`. Concurrency is covered with a `ThreadPoolExecutor` test.

## Gotchas

- No migrations: tables are created with `CREATE TABLE IF NOT EXISTS`, so a schema change won't alter an existing
  `chronowarden.db`. Plan a migration in the spec for any column change.
- `PRAGMA foreign_keys` is not enabled, so `ON DELETE CASCADE` does nothing. `delete_owner` deletes routes
  explicitly.
- Owner and route IDs are `TEXT` (generated in the API); secret IDs are `INTEGER AUTOINCREMENT`.
- The `engine_config` table and its methods are only used by tests. The live severity cascade reads YAML config
  ([core](../AGENTS.md)).

## Related ADRs

[ADR-005](../../.ai/adr/ADR-005-sqlite-metadata-cache.md),
[ADR-010](../../.ai/adr/ADR-010-owners-systems-and-permissions.md) (owners, systems, #61)

## Validate

`uv run pytest tests/test_database.py tests/test_secrets.py tests/test_owners.py`
