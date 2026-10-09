<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-013: Scheduled sync in-process, plus a headless one-shot mode

- **Status:** Accepted
- **Date:** 2026-10-09
- **Evidence:** Maintainer decision 2026-10-09; issue #48; `polling_interval` exists in config but nothing reads it.

## Context

Sync runs only when `POST /api/v1/sync/vault/{name}` is called. Metrics-based alerting (ADR-012) needs fresh data without anyone clicking Sync. #48 asks for a headless run, e.g. as a Kubernetes CronJob without the frontend.

## Decision

- The server runs a background task that syncs every configured, connected vault every `polling_interval`. It starts next to the reconnect loop in `lifespan`.
- A headless one-shot mode runs the same sync for all vaults and exits, for CronJob use. It updates the SQLite DB; metrics are served by the long-running server.
- Both call the same sync function as the API.

## Consequences

- `polling_interval` needs its own parser: the expiry parser (`parse_duration_to_days`) reads `m` as months, but `config.example.yaml` documents `30m` as minutes.
- In-process loop, CronJob and manual sync can overlap, so they share one per-vault lock.
- The headless image (#48) can drop the frontend build stage.
- Handling sync while a vault is reconnecting (#59) becomes part of the same code path.

## Related files

- [`chronowarden/app.py`](../../chronowarden/app.py)
- [`chronowarden/metadata.py`](../../chronowarden/metadata.py)
- [`chronowarden/config.py`](../../chronowarden/config.py)
- [`Dockerfile`](../../Dockerfile)
