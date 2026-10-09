<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Strict config validation

- **Status:** implemented
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

- [root AGENTS.md](../../../AGENTS.md)
- [core](../../../chronowarden/AGENTS.md)

## ADRs affected

None.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `model_config = ConfigDict(extra="forbid")` on every config model (`AppConfig`, `VaultConfig`, `EngineConfigNested`, `SecretConfig`, `ExpiryProfile`) | core, `chronowarden/config.py` | A typo such as `sevrity:` fails with its key path; tests cover each model | done | |
| 2 | `load_config` raises a `ConfigError` (new, in `config.py`) instead of returning `AppConfig()` when YAML can't be read or parsed, when the explicit/`CHRONOWARDEN_CONFIG` path doesn't exist, or when validation fails; the message lists every pydantic error as `path: reason` | core | Tests for each case; no config file at the default paths still yields defaults | done | |
| 3 | Startup fails with exit code 3 on `ConfigError`. Deviation: logged by the existing `logger.exception` in `lifespan` (with traceback), because root AGENTS.md requires `logger.exception` when catching | core, `chronowarden/app.py` | `tests/test_app.py` covers startup failure on a bad config | done | |
| 4 | Unknown severities (no matching expiry profile) become errors instead of warnings | core | `_warn_invalid_severity_values` replaced by a validator that raises; tests updated | done | |
| 5 | Document the behaviour in `config.example.yaml` and core `AGENTS.md` Contracts | core | Docs match the code | done | |

## Validation

`uv run pytest tests/test_config.py tests/test_app.py`, `uv run black --check .`, `uv run ruff check .`

## Open questions

- Task 4 reverses PR #51 (warning-only); confirmed by the maintainer on 2026-10-09.
- Pydantic runs model validators only after field validation passes, so unknown severities show up after key
  errors are fixed.
