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

## [Unreleased]

### Upgrade notes

- **Back up `chronowarden.db` before upgrading, and keep it from now on.** The database is upgraded automatically at
  startup (schema migrations, #76); from 0.7 it holds data that can't be rebuilt by syncing. A database from a newer
  release is refused, so downgrading needs the backup.

### Changed

- **Breaking:** Prometheus metrics are off by default. `GET /api/v1/metrics` returns `404` until you set
  `metrics.enabled: true` in `config.yaml`; turn it on if Prometheus scrapes Chronowarden (#96, ADR-022).

### Removed

- **Breaking:** email notification routes. Existing email routes are deleted by the upgrade, and the API refuses
  `"type": "email"` with `422`. Webhook routes stay; built-in webhook alerting follows in 0.8 (ADR-022).

### Added

- **Audit log (#24, ADR-014).** Every change Chronowarden makes is recorded in an append-only, hash-chained log:
  system and owner assignments, systems, owners, secrets removed, reappearing or purged, and config changes that
  affect secrets (recorded at startup). Sync also records changes made in the backend: custom metadata keys
  added, changed or removed (with values), version-cleanup settings, and new versions (rotations; values are never
  read). `GET /api/v1/audit/events`, `/audit/events.jsonl` (export) and
  `/audit/verify` (recompute the chain); `GET /api/v1/secrets/{id}/history` per secret; assignment changes can be
  reverted with `POST /api/v1/audit/events/{id}/revert`. The log is kept forever.
- **Systems and owners for secrets (#61).** Create systems (name, description, CMDB link, asset number, owners) under
  `/api/v1/systems`, assign a secret to one system and to owners with `PUT /api/v1/secrets/{id}/system` and
  `/owners`, and filter secrets by `system_id`, `owner_id` (effective owner) or `unassigned`. A secret's effective
  owners are its own owners, or else its system's owners. In the UI: Settings → Systems, the assignment section of
  a secret's details, a System column and filter in the secrets table, and a "By system" card on the dashboard.
  Assignments live only in Chronowarden's database, so back it up. Editing is open to anyone who can reach the API until authentication (0.9).
- **Secrets deleted in the backend are noticed (#86).** Sync marks them with `removed_at` instead of showing them
  forever as aging secrets, and unmarks them if they come back. They are hidden from the table and the dashboard
  unless you turn on "Show removed", and can be purged one by one or all at once (`DELETE /api/v1/secrets/{id}`,
  `DELETE /api/v1/secrets/removed`). Nothing is marked when a listing fails or is incomplete.
- Releases are signed: the production image carries a cosign signature, SLSA Build L3 provenance and CycloneDX/SPDX
  SBOMs, and the GitHub Release has the wheel, sdist, source SBOMs and provenance. See "Verifying releases" in the
  README.
- `SECURITY.md` (private vulnerability reporting, acknowledgement within 7 days) and `CONTRIBUTING.md`.
- Fuzzing of date parsing, TTL calculation and config loading (ClusterFuzzLite).

### Fixed

- Timestamps with fractional seconds and a UTC offset (`last_synced`) lost the offset, so the UI could show them in
  the wrong time zone.
- A config file that isn't valid UTF-8 stopped startup with a raw `UnicodeDecodeError`; it is now a configuration
  error naming the file.
- TTL calculation crashed for update times near the year 9999, and years before 1000 were written in a form
  Chronowarden couldn't read back.

## [0.6.3] - 2026-10-11

**Upgrade promptly if other teams or tools put custom metadata on secrets Chronowarden manages.**

### Fixed

- **Sync deleted other custom metadata and reset version cleanup.** Every time sync wrote `chronowarden_severity`
  or `chronowarden_ttl` (on a secret's first sync, and whenever its severity or TTL changed, e.g. after a rotation),
  Vault replaced the secret's whole `custom_metadata` map. That deleted every other key on the secret, and reset its
  `delete_version_after` to `0s`, so old versions were no longer cleaned up. All earlier releases are affected.
  Chronowarden now merges its keys into the existing metadata and keeps `delete_version_after`; it still needs only
  the `read` and `update` capabilities of the documented policy.
- The Docker build no longer runs `npm ci` under arm64 emulation, which could hang the multi-arch build. The
  frontend is built once on the native build platform; its output is the same for every architecture.

### Check your secrets after upgrading

Vault keeps no history of custom metadata, so lost values can only come from your own records (IaC, scripts,
documentation):

- Look for secrets that should carry other teams' keys but only have `chronowarden_*` keys:
  `vault kv metadata get <mount>/<path>`.
- Check `delete_version_after` on secrets where you set a version cleanup period; it may now be `0s`.
- The Vault audit log shows which secrets were affected: `update` operations on `<mount>/metadata/<path>` by
  Chronowarden's token.

### Changed

- The frontend runs on SvelteKit 3 and TypeScript 6 (#79). No visible changes; the build, pages and API calls are
  the same.
- The Kubernetes example deploys `v0.6.3`.

## [0.6.2] - 2026-10-10

Security release following a review of the rest of the API. **Upgrade** if the API is reachable by anyone you don't
fully trust.

### Security

- **Vault path injection in the passthrough endpoints (High, [GHSA-7p2g-v7c6-vpww](https://github.com/fajfer/chronowarden/security/advisories/GHSA-7p2g-v7c6-vpww)).** `GET /api/v1/vault/{name}/secrets/list` and
  `POST /api/v1/vault/{name}/secrets/metadata` passed the request `path`/`mount_point` to Vault without keeping
  them inside the configured KV mount, so an unauthenticated request could reach other Vault API paths and have
  their response returned. Both endpoints were unused by the UI and are **removed**. (**Breaking** for direct API
  users.)
- urllib3 raised to `>= 2.8.0`, fixing PYSEC-2026-4175, -4176 and -4177.

### Changed

- Sentry no longer sends PII (request headers, client IPs) by default, and transaction tracing and profiling are
  off unless `sentry_traces_sample_rate` / `sentry_profiles_sample_rate` are set. Previously they were hard-coded on
  whenever a DSN was configured.
- The frontend is built on Node 22 LTS (was Node 20, end of life).
- The Kubernetes example deploys the pinned production image instead of the `main-dev` tag.

### Documentation

- The README warns that the API and UI are unauthenticated and should run only on a trusted network or behind an
  authenticating proxy.

## [0.6.1] - 2026-10-09

Security release. **Upgrade as soon as possible** if the UI is reachable by anyone you don't fully trust.

### Security

- **Path traversal in the UI route (High, [GHSA-63g5-x4f2-2rg5](https://github.com/fajfer/chronowarden/security/advisories/GHSA-63g5-x4f2-2rg5)).** Every release up to and including 0.6.0 served any file readable by
  the Chronowarden process for requests such as `GET /..%2f..%2fdata%2fconfig.yaml`, without authentication. This
  includes `config.yaml`, which can hold Vault tokens or AppRole `secret_id`s, and mounted secret files. The route
  now serves only files inside the frontend build directory. After upgrading, **rotate the Vault credentials
  Chronowarden uses** if the UI was reachable from untrusted networks.
- Frontend build dependencies updated to patched releases (`@sveltejs/kit` 2.70.3, `devalue` 5.9.4, `postcss`
  8.5.29, `source-map-js` 1.2.2, `cookie` 0.7.2), closing all open Dependabot alerts.

### Fixed

- Unknown `/api/...` paths return `404` instead of the UI page with `200`.

### Added

- CI starts the built production image and fails unless `/api/v1/health` answers and a path traversal request is
  refused, before any image is pushed.

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

[Unreleased]: https://github.com/fajfer/chronowarden/compare/v0.6.3...HEAD
[0.6.3]: https://github.com/fajfer/chronowarden/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/fajfer/chronowarden/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/fajfer/chronowarden/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/fajfer/chronowarden/compare/v0.5.0...v0.6.0
