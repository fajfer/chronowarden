<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Instance UI settings: vault URLs and default theme

- **Status:** draft
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
| 1 | `VaultInstanceHealth` gains `address`; `/vault/health` and `/vault/{name}/health` return it | api | `tests/test_vault_api.py` asserts it | todo | |
| 2 | Vaults page shows the address as a link | frontend | `npm run check` clean | todo | |
| 3 | Config `ui.default_theme` (validated against the known theme IDs), fallback env `CHRONOWARDEN_THEME`, else `default`; exposed in `GET /api/v1/info` as `default_theme` | api, [core](../../chronowarden/AGENTS.md) | Tests for config, env, neither | todo | |
| 4 | `theme.ts` uses `default_theme` from `/info` when no theme is stored; drop `PUBLIC_CHRONOWARDEN_THEME` | frontend | Manual check: changing the config changes the default without rebuilding | todo | |
| 5 | Document `ui.default_theme` and `CHRONOWARDEN_THEME` in `config.example.yaml` and the deploy examples | core, [deploy](../../deploy/AGENTS.md) | Docs match | todo | |

## Validation

`uv run pytest tests/test_vault_api.py tests/test_config.py`, `cd frontend && npm run check`

## Open questions

- Theme IDs live in the frontend (`THEME_DEFINITIONS`). Should the backend validate against a copied list, or accept
  any string and let the frontend fall back to `default`?
