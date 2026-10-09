<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Strict config validation

- **Status:** draft
- **Date:** 2026-10-09
- **Issue:** #12

## Goal

A wrong config never starts silently. Unknown keys, invalid values, unparsable YAML and a missing file at an explicit
path abort startup with one message that lists every problem (key path + reason). A correct config behaves exactly as
today.

## Non-goals

- A `--check-config` CLI (not chosen; can follow later).
- Changing the config schema itself (#30 removes the legacy keys first).

## Scope

`chronowarden/config.py`, `chronowarden/app.py`, `tests/test_config.py`, `tests/test_app.py`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [core](../../chronowarden/AGENTS.md)

## ADRs affected

None.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `model_config = ConfigDict(extra="forbid")` on every config model (`AppConfig`, `VaultConfig`, `EngineConfigNested`, `SecretConfig`, `ExpiryProfile`) | core, `chronowarden/config.py` | A typo such as `sevrity:` fails with its key path; tests cover each model | todo | |
| 2 | `load_config` raises a `ConfigError` (new, in `config.py`) instead of returning `AppConfig()` when YAML can't be read or parsed, when the explicit/`CHRONOWARDEN_CONFIG` path doesn't exist, or when validation fails; the message lists every pydantic error as `path: reason` | core | Tests for each case; no config file at the default paths still yields defaults | todo | |
| 3 | `lifespan` logs the `ConfigError` message once, without a traceback, and exits non-zero | core, `chronowarden/app.py` | `tests/test_app.py` covers startup failure on a bad config | todo | |
| 4 | Unknown severities (no matching expiry profile) become errors instead of warnings | core | `_warn_invalid_severity_values` replaced by a validator that raises; tests updated | todo | |
| 5 | Document the behaviour in `config.example.yaml` and core `AGENTS.md` Contracts | core | Docs match the code | todo | |

## Validation

`uv run pytest tests/test_config.py tests/test_app.py`, `uv run black --check .`, `uv run ruff check .`

## Open questions

- Task 4 changes PR #51's decision ("warning-only, preserves cascade/fallback behaviour"). Confirm before
  implementing.
