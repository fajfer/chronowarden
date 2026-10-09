<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Changelog

All notable changes to Chronowarden are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).
Before 1.0, minor versions may contain breaking changes; they are marked **Breaking** below.

Releases before 0.6.0 are described in the [GitHub releases](https://github.com/fajfer/chronowarden/releases) and the
git history.

## [0.6.0] - 2026-10-09

Milestone [0.6 Foundations](https://github.com/fajfer/chronowarden/milestone/2): a strict, predictable core before
the compliance work in 0.7.

### Upgrade notes

- **Delete `chronowarden.db` before starting 0.6.0.** It is only a cache and is rebuilt by the next sync. Old files
  keep working, but still contain the removed `enabled` column and `engine_config` table.
- Check your `config.yaml` against [`config.example.yaml`](config.example.yaml): 0.6.0 refuses to start on unknown
  keys, unknown severities or invalid values, and names every problem in the startup error.
- `default_severity` and the top-level `engines:` list are gone. Use `vaults[].severity` and `vaults[].engines[]`.
- Severity is set in `config.yaml` only. To stop rotating a secret, use `severity: none`.

### Added

- Per-profile `alert_threshold` in `expiry_profiles` (default `30d`). A secret is `warning` when it expires within
  its own profile's threshold. The API returns it as `alert_threshold_days` (#70).
- Sync reconnects a disconnected vault first (re-authenticating, so AppRole tokens are renewed). If that fails, the
  `503` response says why (`reason`) and whether a retry is scheduled. After a background reconnect the vault is
  synced automatically. Syncs of one vault no longer run in parallel (#59).
- Every log line has a timestamp, and successful health, readiness and metrics requests no longer fill the access
  log (#58).
- Vault addresses are shown on the vaults page and returned by `/api/v1/vault/health` (#19).
- Instance default theme: `ui.default_theme` in `config.yaml`, or the `CHRONOWARDEN_THEME` environment variable.
  A theme the user picks in Settings still wins (#57).
- `dev-setup.py --cleanup` stops and removes the development containers (#31).
- CI runs black, ruff, pytest and `svelte-check` on every push and pull request.

### Changed

- **Breaking:** configuration is validated strictly. Unknown keys, severities without an expiry profile, a missing
  file at `CHRONOWARDEN_CONFIG` and unparsable YAML stop startup instead of being ignored or replaced by an empty
  config (#12).
- `GET /api/v1/info` also returns `default_theme`.
- The development environment runs OpenBao 2.7.1 and HashiCorp Vault 2.1.2 (one container each).

### Removed

- **Breaking:** `PATCH /api/v1/secrets/{id}`. Secrets are read-only through the API; severity comes from config (#73).
- **Breaking:** the `enabled` field in secret responses and sync results, the `enabled` filter on
  `GET /api/v1/secrets` (now ignored), and the `chronowarden_enabled` metadata key. `severity: none` replaces it (#73).
- **Breaking:** the deprecated `default_severity` vault key and the top-level `engines` list (#30).
- The build-time `PUBLIC_CHRONOWARDEN_THEME` frontend variable; use `CHRONOWARDEN_THEME` or `ui.default_theme`.

### Fixed

- An unreachable vault made `POST /api/v1/sync/vault/{name}` fail with `500` and could stop the background reconnect
  loop. It is now reported as `offline`.
- The UI stored the current theme on every page load, so a changed instance default never reached users who had
  visited before.

[0.6.0]: https://github.com/fajfer/chronowarden/compare/v0.5.0...v0.6.0
