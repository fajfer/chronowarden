<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Per-profile alert threshold

- **Status:** draft
- **Date:** 2026-10-09
- **Issue:** #70

## Goal

A secret is `warning` when `0 < days_remaining <= alert_threshold` of **its** expiry profile, as the README
promises, instead of the fixed 30 days hard-coded in `chronowarden/api/secrets.py:_compute_status`.

## Non-goals

- Notifications and alert routing (README roadmap).
- Changing rotation periods.

## Scope

`chronowarden/config.py`, `chronowarden/api/secrets.py`, `config.example.yaml`, `README.md`,
`frontend/src/lib/components/ExpiryHorizon.svelte`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [core](../../chronowarden/AGENTS.md)
- [api](../../chronowarden/api/AGENTS.md)
- [ADR-006](../adr/ADR-006-config-source-of-truth.md)

## ADRs affected

None (extends the expiry-profile schema; the cascade is unchanged).

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Add `alert_threshold` (duration, same `<int>[d\|m\|y]` format) to `ExpiryProfile` with defaults for the built-in profiles; profiles without it keep 30d | core, `chronowarden/config.py` | `tests/test_config.py` covers default, custom, invalid value | todo | |
| 2 | `_compute_status` takes the threshold of the entry's severity (`none` → never warning) | api, `chronowarden/api/secrets.py` | `tests/test_secrets.py` covers boundary days (threshold, threshold+1, 0) per profile | todo | |
| 3 | Document in `config.example.yaml` and fix the README "Secret Status" table | core | Example and README match the code | todo | |
| 4 | `ExpiryHorizon.svelte` no longer assumes a fixed 30d marker, or the marker is documented as fixed | [frontend](../../frontend/AGENTS.md) | `npm run check` has no new warnings | todo | |

## Validation

`uv run pytest tests/test_config.py tests/test_secrets.py`, `uv run black --check .`, `cd frontend && npm run check`

## Open questions

- Default thresholds: the earlier README example used `critical` 7d, `pci-dss-4.0` 14d, `default` 30d. Adopt
  these?
