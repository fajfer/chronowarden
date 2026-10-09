<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Remove pre-1.0 deprecation shims

- **Status:** draft
- **Date:** 2026-10-09
- **Issue:** #30 (also #16)

## Goal

No deprecation warnings or legacy config paths before 1.0. Each config key has exactly one supported form.

## Non-goals

- Introducing a config versioning scheme.

## Scope

`chronowarden/config.py`, `chronowarden/database.py`, `config.example.yaml`, tests.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [core](../../chronowarden/AGENTS.md)
- [models](../../chronowarden/models/AGENTS.md)

## ADRs affected

ADR-006: the cascade loses the "legacy top-level `engines[]`" level; update its text.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Remove `VaultConfig.default_severity` and `migrate_default_severity` | core, `chronowarden/config.py` | A config with `default_severity` fails validation (or is rejected with a clear error); tests updated | todo | |
| 2 | Remove top-level `AppConfig.engines`, `EngineConfig`, `AppConfig.get_engine_config` and the `legacy_engine_config` cascade level | core | `resolve_severity_source` has 4 levels; `tests/test_config.py` green | todo | |
| 3 | Remove the unused `engine_config` table, `EngineConfigRow` and its DB methods | [models](../../chronowarden/models/AGENTS.md) | `tests/test_database.py` green | todo | |
| 4 | Update core `AGENTS.md` (cascade contract) and ADR-006 | core | No mention of the legacy level remains | todo | |

## Validation

`uv run pytest tests/test_config.py tests/test_metadata.py tests/test_database.py`, `uv run black --check .`

## Open questions

- Unknown config keys are ignored by pydantic today. Should removed keys raise instead (relates to #12)?
