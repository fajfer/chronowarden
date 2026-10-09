<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Instance UI settings: vault URLs and default theme

- **Status:** implemented
- **Date:** 2026-10-09
- **Issue:** #19, #57

## Goal

The `/vaults` page shows each vault's address (#19). An instance sets its default theme at runtime: config key first,
then an environment variable, then `default`. A user's own theme choice (stored in `localStorage`) still wins (#57).

## Non-goals

- New themes.
- Removing the navbar theme switcher (a PR #60 TODO, separate).

## Scope

`chronowarden/config.py`, `chronowarden/api/vault.py`, `chronowarden/api/health.py`, `frontend/src/lib/stores/theme.ts`,
`frontend/src/routes/vaults/+page.svelte`, `config.example.yaml`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [api](../../chronowarden/api/AGENTS.md)
- [frontend](../../frontend/AGENTS.md)

## ADRs affected

None.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `VaultInstanceHealth` gains `address`; `/vault/health` and `/vault/{name}/health` return it | api | `tests/test_vault_api.py` asserts it | done | |
| 2 | Vaults page shows the address as a link | frontend | `npm run check` clean | done | |
| 3 | Config `ui.default_theme` (validated against the known theme IDs), fallback env `CHRONOWARDEN_THEME`, else `default`; exposed in `GET /api/v1/info` as `default_theme` | api, [core](../../chronowarden/AGENTS.md) | Tests for config, env, neither | done | |
| 4 | `theme.ts` uses `default_theme` from `/info` when no theme is stored; drop `PUBLIC_CHRONOWARDEN_THEME` | frontend | Manual check: changing the config changes the default without rebuilding | done | |
| 5 | Document `ui.default_theme` and `CHRONOWARDEN_THEME` in `config.example.yaml` and the deploy examples | core, [deploy](../../deploy/AGENTS.md) | Docs match | done | |

## Validation

`uv run pytest tests/test_vault_api.py tests/test_config.py`, `cd frontend && npm run check`

## Open questions

- Decided 2026-10-09: the backend validates against `THEME_IDS` (config and env); keep it in sync with
  `THEME_DEFINITIONS`.
- Also fixed: `initTheme` used to store the theme on every load, so an instance default could never apply after
  a user's first visit. Now only an explicit choice in Settings is stored.
