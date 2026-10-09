<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Sync reconnects first

- **Status:** implemented
- **Date:** 2026-10-09
- **Issue:** #59

## Goal

`POST /api/v1/sync/vault/{name}` on a disconnected vault first tries one reconnect (including AppRole token
regeneration). If that works, it syncs and returns the results as usual. If not, it returns 503 with the reason
(`offline`, `auth`, …) and says that a background retry is scheduled. When the background loop reconnects a vault, it
syncs that vault right away.

## Non-goals

- Periodic sync (#74, milestone 0.8).
- Changing auth-failure policy (auth errors are still not retried in the background, ADR-009).

## Scope

`chronowarden/api/sync.py`, `chronowarden/integrations/manager.py`, `frontend/src/lib/stores/sync.ts`, tests.

## Load

- [root AGENTS.md](../../../AGENTS.md)
- [integrations](../../../chronowarden/integrations/AGENTS.md)
- [api](../../../chronowarden/api/AGENTS.md)
- [ADR-009](../../adr/ADR-009-offline-tolerant-reconnect.md)

## ADRs affected

ADR-009 is extended (sync after reconnect); no change of decision.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `VaultManager.reconnect(name) -> bool`: one reconnect attempt for a single vault, sharing the code of `_retry_pending_vaults`/`_reconnect_disconnected_vaults` | integrations, `chronowarden/integrations/manager.py` | `tests/test_manager.py` covers success, offline, auth | done | |
| 2 | Sync endpoint: when disconnected, run `reconnect` and then `detect_changes` in a worker thread (`run_in_threadpool`) so the blocking hvac calls don't block the event loop; on failure return 503 with `reason` and `retry_scheduled` | api, integrations | `tests/test_sync_api.py` covers reconnect-then-sync and both failure kinds | done | |
| 3 | Reconnect loop: after a successful reconnect, sync that vault (callback set by `app.py`, so `integrations` doesn't import `metadata`) | integrations, [core](../../../chronowarden/AGENTS.md) | Test: a reconnect triggers exactly one sync | done | |
| 4 | Frontend: show the 503 `reason` and "will retry automatically" as an info toast, not an error | [frontend](../../../frontend/AGENTS.md) | `npm run check` clean; manual check with a stopped dev vault | done | |

## Validation

`uv run pytest tests/test_manager.py tests/test_sync_api.py`; manual check with `dev-setup.py` while stopping and
starting a vault container.

## Open questions

- Decided 2026-10-09: per-vault `asyncio.Lock` added now (`VaultManager.sync_lock`); a second sync waits.
- Found while testing: `is_connected()` raised on network errors (500 from the endpoint, and it could stop the
  reconnect loop). Fixed separately with regression tests.
