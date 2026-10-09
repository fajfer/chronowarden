<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# core: app, config, sync

## Purpose

Application wiring (`app.py`), YAML configuration and the severity cascade (`config.py`), and the sync engine that
turns backend metadata into cached TTLs (`metadata.py`). The SQLite layer (`database.py`) is covered in
[models](models/AGENTS.md).

## Files

- `app.py`: module-level singletons `vault_manager`, `db`, `app_config`; `lifespan` (load config → Sentry →
  `connect_all` → open DB → `start_reconnect_loop`); routers mounted under `/api/v1`; SPA serving.
- `config.py`: `AppConfig`, `VaultConfig`, `EngineConfigNested`, `SecretConfig`, `ExpiryProfile`, `load_config`.
- `metadata.py`: `parse_date`, `calculate_ttl`, `sync_secret_metadata`, `detect_changes`.
- `../config.example.yaml`: the reference for every config key. Keep it in sync with `config.py`.

## Contracts

- Config lookup order: explicit path → `CHRONOWARDEN_CONFIG` → `/etc/chronowarden/config.yaml` → `./config.yaml`.
  A missing or unreadable file yields a default `AppConfig()`; startup does not fail.
- Severity cascade (`AppConfig.resolve_severity`): secret → engine (nested) → legacy top-level `engines[]` →
  vault → `"default"`. `resolve_severity_source` names the level that matched.
- `"none"` is reserved (`RESERVED_SEVERITY_VALUES`): monitored, never rotated; `calculate_ttl` returns `None`.
- `DEFAULT_EXPIRY_PROFILES` (`default` 365d, `critical` 6m, `pci-dss-4.0` 90d) are always merged with
  user-defined ones (`merge_default_expiry_profiles`). Durations are `<int>[d|m|y]`.
- Unknown severities in config only log a warning; they don't raise. The value is kept, and `get_rotation_days`
  falls back to the `default` profile for it.
- Credential resolution order: `*_file` > `*_env` > literal (tokens and AppRole IDs).
- Config is the source of truth: sync writes the resolved `chronowarden_severity`/`chronowarden_ttl` back to the
  backend when they differ ([ADR-006](../.ai/adr/ADR-006-config-source-of-truth.md)).
- `detect_changes(vault, vault_name, config, db)` is what `POST /api/v1/sync/vault/{name}` calls.
- API routers read `app_config`, `db`, `vault_manager` from `chronowarden.app` lazily (inside a function); keep
  that pattern and don't rename these globals.

## How to

- **Add a config option**: add a `Field(..., description=...)` to the right model in `config.py`, document it in
  `config.example.yaml`, and add tests in `tests/test_config.py`. If deployments need it, follow [deploy](../deploy/AGENTS.md).
- **Change the cascade**: edit `_resolve_severity_with_source` and its docstring, the comment block in
  `config.example.yaml`, and the note in `architecture/integrations.c4`. If precedence changes, supersede
  ADR-006.

## Gotchas

- `polling_interval` is parsed but nothing reads it: there is no background sync scheduler. Sync only runs via the
  API.
- `sync_secret_metadata` always writes `enabled=True` to the cache and never reads `chronowarden_enabled`
  (`is_secret_enabled` is unused). See [the spec](../.ai/specs/2026-10-09-honor-enabled-flag-in-sync.md).
- Sync recomputes severity from config, so a severity set through `PATCH /secrets/{id}` is overwritten on the next
  sync unless config agrees.
- Dates: ISO 8601 or `YYYY-MM-DD`/`YYYY-DD-MM`. `date_format` is a hint; with `YYYY-MM-DD`, an invalid month falls
  back to swapped parts.
- The DB path is `chronowarden.db` relative to the working directory (set in `lifespan`).
- `app.py` registers the SPA catch-all `/{full_path:path}` last. New API routes must be included before it.

## Related ADRs

[ADR-005](../.ai/adr/ADR-005-sqlite-metadata-cache.md), [ADR-006](../.ai/adr/ADR-006-config-source-of-truth.md),
[ADR-007](../.ai/adr/ADR-007-sveltekit-spa-served-by-fastapi.md)

## Validate

`uv run pytest tests/test_config.py tests/test_metadata.py tests/test_app.py`
