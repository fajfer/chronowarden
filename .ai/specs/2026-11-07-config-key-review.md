<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Config key review before 1.0

- **Status:** draft
- **Date:** 2026-11-07
- **Issue:** none

## Goal

Every config key that 1.0 ships is one the project wants to keep for all of 1.x. ADR-016 freezes config keys at
1.0: in 1.x they are only added, and a removal or rename waits for 2.0, with no deprecation warnings or aliases. So
every rename or removal happens before 1.0, in one breaking release with an upgrade note that maps each old key to
the new one. A test then makes a removed or renamed key fail CI.

## Non-goals

- Metric names, `/api/v1` fields and webhook payload fields: ADR-016 freezes them too, but they get their own
  review.
- New config options or new behaviour. A key changes only its name, place or form, never what it does.
- Deprecation warnings or aliases for old keys (root `AGENTS.md`, ADR-016).

## Scope

`chronowarden/config.py`, `config.example.yaml`, everything that writes or documents config (`devenv/config.py`,
`deploy/`, `docs/reference/`, `README.md`), `tests/test_config.py`, the open provider specs' config examples.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [core](../../chronowarden/AGENTS.md), [deploy](../../deploy/AGENTS.md)
- [ADR-016](../adr/ADR-016-stability-policy-for-1-0.md), [ADR-006](../adr/ADR-006-config-source-of-truth.md),
  [ADR-011](../adr/ADR-011-provider-registry.md)
- `chronowarden/config.py`, `config.example.yaml`

## ADRs affected

None superseded. It carries out ADR-016's "config keys are reviewed before 1.0". A rename that touches a decision
recorded in an ADR (e.g. `vaults:` under ADR-011) updates that ADR's wording by superseding it, if the maintainer
asks for it.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | The maintainer decides each candidate under **Open questions** (keep / rename to X / remove / move) | this spec | Every candidate has a decision written next to it | todo | |
| 2 | Apply the decisions in `config.py` and `config.example.yaml`; adjust `tests/test_config.py` (an old key is an error, through `extra="forbid"`) | spec Load, `tests/test_config.py` | `uv run pytest tests/test_config.py` passes; `config.example.yaml` loads | todo | |
| 3 | Update everything that writes or documents config: `devenv/config.py`, `deploy/` (Compose, Kubernetes), `docs/reference/`, `README.md`, the config examples in the open Azure Key Vault and GCP Secret Manager specs | spec Load, the files named | `git grep` finds no old key name outside `CHANGELOG.md` and `implemented/` specs | todo | |
| 4 | Key freeze test: `tests/test_config_keys.py` derives every key path from `AppConfig` and compares it with a checked-in list; a missing path fails with a message citing ADR-016, a new path asks to add it to the list | `chronowarden/config.py`, ADR-016 | Removing or renaming any key makes the test fail; adding one makes it fail until the list is updated | todo | |
| 5 | CHANGELOG upgrade notes: **Breaking**, one line per change, old key → new key | `CHANGELOG.md` | Every decision from task 1 that isn't "keep" is listed | todo | |

## Validation

`uv run black --check . && uv run ruff check . && uv run pytest`, then `./dev-setup.py --run keys` starts and the
app loads its config.

## Open questions

Current key paths (`AppConfig`, 2026-11-07): `ca_certs_dir`, `sentry_dsn`, `sentry_traces_sample_rate`,
`sentry_profiles_sample_rate`, `vaults[]` (`type`, `name`, `address`, `auth_method`, `token`/`_env`/`_file`,
`role_id`/`_env`/`_file`, `secret_id`/`_env`/`_file`, `approle_mount_point`, `namespace`, `mount_path`, `verify_ssl`,
`date_format`, `severity`, `confirmation_required`, `engines[]` → `secrets[]`), `date_format`,
`confirmation_grace`, `polling_interval`, `vault_reconnect_interval`, `vault_reconnect_max_attempts`,
`manual_sync_cooldown`, `snapshot_min_interval`, `expiry_profiles`, `ui`, `metrics`, `alerting`, `compliance`,
`auth`, `allowed_hosts`.

Candidates, for the maintainer to decide (the agent proposes, it doesn't choose):

- **`vaults:` → `providers:`?** Backends are generic since ADR-011, and the next ones (Azure Key Vault, GCP Secret
  Manager) are listed under `vaults:` with a `type:`. With it: `vault_reconnect_interval` →
  `reconnect_interval`, `vault_reconnect_max_attempts` → `reconnect_max_attempts`. Should this land before the
  Azure and GCP providers, so they never ship under `vaults:`?
- **`vaults[].engines[]`:** "engine" is Vault's word; the cloud providers have no engines. Keep, or a neutral name?
- **`vaults[].mount_path`:** only the default mount for `list_secrets` calls that don't pass one; sync discovers
  engines. Still needed?
- **Inline credentials** (`token`, `role_id`, `secret_id`, `auth.oidc.client_secret`) next to their `_env` and
  `_file` forms: keep all three, or only `_env` and `_file` from 1.0?
- **`sentry_dsn`, `sentry_traces_sample_rate`, `sentry_profiles_sample_rate`:** flat at the top level, while
  `metrics`, `ui`, `alerting` and `auth` are sections. Move to `sentry:`?
- **`date_format`** (top level and per vault) and **`confirmation_grace`** (top level and per expiry profile): keep
  both levels?
- **`ca_certs_dir`:** global, used only for vault connections. Keep it global, or move it per vault?
- **`vaults[].auth_method`:** plain string, while `auth.mode` is a fixed choice. Keep the name and make it a
  `Literal`, or rename?
