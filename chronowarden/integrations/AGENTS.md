<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# integrations: secret-backend providers

## Purpose

Connect to secret backends and read and write **metadata only**. Today the only provider is HashiCorp Vault /
OpenBao (KV v2) via `hvac`.

## Files

- `base.py`: `BaseIntegration`, the intended provider interface.
- `vault.py`: `VaultIntegration` (token and AppRole auth, KV v2 metadata, engine discovery, health).
- `manager.py`: `VaultManager`, which holds one `VaultIntegration` per configured vault, builds the CA bundle from
  `ca_certs_dir`, and runs the background reconnect loop.

## Contracts

- `BaseIntegration` methods: `connect() -> bool`, `disconnect()`, `is_connected() -> bool`,
  `list_secrets(path)`, `get_secret_metadata(path)`, `get_secret(path, key)`.
- Used by sync and the API on top of the base: `VaultIntegration.write_secret_metadata`, `discover_engines`
  (KV v2 only), `check_health`, `last_error`, `last_error_kind`. `mount_point=` overrides the engine per call.
- `last_error_kind` is one of `auth` (not retried), `offline` / `vault` / `unexpected` (retried by the loop).
- `VaultManager` API used elsewhere: `get(name)`, `vault_names`, `connect_all(config)`, `disconnect_all()`,
  `health()`, `start_reconnect_loop()`, `reconnect(name)` (one blocking attempt), `sync_lock(name)` (one
  `asyncio.Lock` per vault; every sync holds it) and `set_reconnect_callback(cb)` (`app.py` registers a sync that
  runs after the background loop reconnects a vault, #59).
- Metadata keys written to the backend: `chronowarden_severity`, `chronowarden_ttl`, only by sync.
  `chronowarden_enabled` is no longer used (#73).
- Tokens (static or AppRole-issued) are kept in memory only; never persist them (#10).
- Required Vault policy: README "Vault Permissions" (`+/metadata/*` list/read/update, `+/metadata` list,
  `sys/mounts` read). A new call must fit this policy (root **Ask First**).

## How to

- **Add a new provider** (e.g. GitLab): today `VaultManager`, `VaultConfig` and the API are hard-wired to Vault,
  so a second provider first needs the
  [generic provider registry spec](../../.ai/specs/2026-10-09-generic-provider-registry.md). After that: subclass
  `BaseIntegration`, map backend failures to `last_error_kind`, add
  `tests/test_<provider>.py` with a mocked client (see `tests/test_vault.py`).
- **Every new integration must also update the architecture model** ([architecture](../../architecture/AGENTS.md)):
  add the element and relations, and a note in `architecture/integrations.c4`.
- **New Vault call**: wrap it in `if not self._client:` and catch `Forbidden` (log which policy capability is
  missing), then `VaultError`, and return a neutral value (`None`/`[]`/`False`). Look at `write_secret_metadata`.

## Gotchas

- `BaseIntegration` is a pydantic `BaseModel` whose methods just `pass`; it is not an ABC, so nothing enforces the
  interface.
- `VaultIntegration.get_secret` exists but no API exposes it (the value-reading endpoint was removed in `ac38af9`).
  Don't wire it up.
- `get_secret_metadata` returns `None` for `InvalidPath`; `list_secrets` keys ending in `/` are folders (sync
  recurses).
- Auth failures stop retries for that vault; offline vaults are retried every `vault_reconnect_interval` s for at
  most `vault_reconnect_max_attempts` cycles. `connect()` closes a previous client before re-authenticating.
- `connect()`, `is_connected()` and the reconnect loop's passes block on network I/O: call them through
  `asyncio.to_thread` from async code. `is_connected()` maps network errors to `offline`/`unexpected` instead of
  raising.
- `check_health` returns `initialized`/`sealed`, but the UI only shows healthy/offline (#44 follow-up).
- OpenBao compatibility is a goal (README); test against both if you touch auth or KV calls (`dev-setup.py`).

## Related ADRs

[ADR-003](../../.ai/adr/ADR-003-pluggable-integrations-vault-first.md),
[ADR-004](../../.ai/adr/ADR-004-metadata-only-access.md),
[ADR-009](../../.ai/adr/ADR-009-offline-tolerant-reconnect.md)

## Validate

`uv run pytest tests/test_vault.py tests/test_manager.py tests/test_metadata.py`
