<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Scheduled sync and a one-shot sync command

- **Status:** approved
- **Date:** 2026-10-12
- **Issue:** #74 (and the CronJob half of #48)

## Goal

Data stays fresh without anyone clicking Sync: the server syncs every vault every `polling_interval`, and
`python -m chronowarden sync` runs one sync of every vault and exits, for a Kubernetes `CronJob`. Both use the same
sync code as the API (ADR-013). This is what time-based webhooks (#99) and metrics (#71) build on.

## Non-goals

- Webhooks (#99) and metrics (#71): separate specs.
- A lock across processes: a server and a CronJob on the same database rely on SQLite's own locking; the docs tell
  operators to turn the server's schedule off when a CronJob does the syncing.
- Per-vault polling intervals.

## Scope

`chronowarden/config.py`, `config.example.yaml`, a new `chronowarden/scheduler.py`, a new
`chronowarden/__main__.py`, `chronowarden/app.py`, `pyproject.toml` (console script), docs, CHANGELOG.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [core](../../chronowarden/AGENTS.md), [integrations](../../chronowarden/integrations/AGENTS.md)
- [ADR-013](../adr/ADR-013-in-process-and-headless-sync.md), [ADR-009](../adr/ADR-009-offline-tolerant-reconnect.md)

## ADRs affected

Implements ADR-013. None changed.

## Design

- **`polling_interval`** gets its own parser (ADR-013 consequence): `<n>s|m|h|d` with `m` = minutes, at least 60 s,
  or `off` to turn the schedule off. Invalid values fail config validation. The default stays `6h`.
- **Scheduler** (`scheduler.py`): an asyncio task started in `lifespan` after the reconnect loop. It syncs every
  connected vault once shortly after startup, then every interval. Each vault goes through `sync_vault_now` (the
  per-vault lock the API uses), one vault's failure is logged and doesn't stop the others, and a disconnected vault
  is left to the reconnect loop. Shutdown cancels the task.
- **One-shot** (`python -m chronowarden sync`, also the `chronowarden` console script): loads the config, connects
  every vault, opens the database (migrating it), records config changes, syncs every connected vault, prints one
  line per vault and exits **0** if all synced, **1** if any failed or was unreachable, **2** on a config error.
  It doesn't start the server, the scheduler or the reconnect loop.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `polling_interval` parser and validation (`off`, minimum 60 s) | core | Config tests: units, `off`, too short, invalid | todo | |
| 2 | `SyncScheduler` started and stopped in `lifespan` | core, integrations | Tests with a fake clock/short interval: syncs connected vaults, skips disconnected, survives one vault failing, stops on shutdown; `off` starts nothing | todo | |
| 3 | `python -m chronowarden sync` and console script | core | Tests: exit codes 0/1/2 with fake vaults; runs against the integration containers | todo | |
| 4 | Docs: `config.example.yaml`, README (scheduled sync, one-shot, CronJob note), core AGENTS.md (remove the "nothing reads polling_interval" gotcha), CHANGELOG | core, deploy | Docs match | todo | |

## Validation

`uv run pytest`, `uv run pytest -m integration`, black, ruff, `check_agents_docs.py`; a dev server logs a
scheduled sync with `polling_interval: 1m`.

## Open questions

- None.
