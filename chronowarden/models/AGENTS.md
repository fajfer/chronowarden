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
- `owner.py`: `Owner*`, `NotificationRoute*` (route `type` is `webhook` only since 0.7, ADR-022).
- `system.py`: `System*`, `OwnerRef`/`SystemRef` (used in `SecretMetadataResponse.system`, `owners`,
  `effective_owners`), `OwnerIds`, `SystemAssignment`.
- `engine.py`, `entity.py`, `router.py`: **reserved for the roadmap, not wired.** Engine kinds (Azure Key Vault,
  X.509, manual), users/groups with permission levels (RBAC), notification routers (email/webhook/Slack). Nothing
  imports them. Wiring or deleting them is in root **Ask First**.
- `../database.py`: `Database`, `SecretMetadataCache`, `DEFAULT_DB_PATH`.
- `../migrations.py`: ordered schema steps (`MIGRATIONS`), run by `Database.connect()`
  ([ADR-023](../../.ai/adr/ADR-023-schema-migrations-with-user-version.md)).

## Contracts

- Tables: `secret_metadata_cache` (unique `vault_name, engine_id, secret_path`), `owners`,
  `notification_routes` (`type = 'webhook'`), `systems` (unique `name`), `system_owners`, and the assignments
  `secret_systems` / `secret_owners` keyed by `vault_name, engine_id, secret_path`, never the cache `id` (ADR-017).
  `audit_events` (append-only, [audit](../audit/AGENTS.md)), `audit_state`, `observed_state`,
  `rotation_confirmations` (revoked, never deleted, except by purge). `PRAGMA user_version` is the
  number of the last migration applied.
- `SecretMetadataResponse` fields are mirrored in `frontend/src/lib/types/Secret.ts`, `Owner` in `Owner.ts`:
  changing a field means changing both.
- `full_path` is computed as `vault_name/engine_id/secret_path`.
- `Database` uses one shared connection (`check_same_thread=False`) in WAL mode. Every method takes
  `self._conn_lock` (an `RLock`) and calls `_require_connection()`, which logs and returns `None` when the DB is
  not connected. Callers get `None`/empty results instead of an exception.
- `upsert_secret_metadata` overwrites `updated_time, ttl, severity, last_synced` on conflict, never `removed_at`
  (only `reconcile_engine` sets or clears it). `list_all_secrets` hides removed rows unless `include_removed`;
  `purge_removed` deletes only removed rows, with their assignments. Pre-0.6 DB files
  still have an unused `enabled` column (default 1); the 0.6 release notes ask users to delete `chronowarden.db`.

## How to

- **Change the schema**: append a `Migration` to `MIGRATIONS` (never edit a shipped one; constraint changes rebuild
  the table), with a test that upgrades a database from the previous release (`tests/test_migrations.py`). For a
  column also update the `SecretMetadataCache` model, every `SELECT` column list and row
  mapping in `database.py`, then the response model and the frontend type. Add tests in `tests/test_database.py`.
- **Dynamic `UPDATE`**: build the `SET` clause only from fixed column names chosen in code (see `update_owner`,
  `update_secret_metadata_fields`) and pass values as `?` params. Never interpolate caller-supplied names
  (`d773fc6`).
- **Test**: the `db` fixture in `tests/test_database.py` (`Database(db_path=tmp_path / "test.db")`) or
  `Database(Path(":memory:"))`. Concurrency is covered with a `ThreadPoolExecutor` test.

## Gotchas

- A database newer than the code is refused at startup (`MigrationError`); downgrading needs a backup.
- `PRAGMA foreign_keys` is not enabled, so `ON DELETE CASCADE` does nothing. `delete_owner` deletes routes and
  assignments explicitly; `delete_system` expects no secrets assigned (the API checks).
- Owner and route IDs are `TEXT` (generated in the API); secret IDs are `INTEGER AUTOINCREMENT`.
- `chronowarden.db` files created before 0.6 still contain an unused `engine_config` table (removed from code in
  #30). It is harmless; nothing reads it.

## Related ADRs

[ADR-017](../../.ai/adr/ADR-017-sqlite-holds-assignments.md),
[ADR-023](../../.ai/adr/ADR-023-schema-migrations-with-user-version.md),
[ADR-010](../../.ai/adr/ADR-010-owners-systems-and-permissions.md) (owners, systems, #61)

## Validate

`uv run pytest tests/test_database.py tests/test_migrations.py tests/test_secrets.py tests/test_owners.py tests/test_systems.py`
