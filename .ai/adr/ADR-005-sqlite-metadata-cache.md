<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-005: SQLite as the local metadata cache

- **Status:** Accepted (retroactive)
- **Date:** 2026-02-07
- **Evidence:** `b9baae7` (database.py added), `4add654` (API moved to the DB cache), `2725865` (connection lock); PRs #8, #54.

## Context

Not recorded. `architecture/integrations.c4`: "Secrets API reads from the database cache populated by sync, not from an in-memory store".

## Decision

Store the cache in a single SQLite file (`chronowarden.db` in the working directory) via `sqlite3`. One shared connection, WAL mode, guarded by an `RLock`.

## Consequences

There is no migration tool (`CREATE TABLE IF NOT EXISTS`), it is single-replica (RWO PVC), and the API reads from the cache, not from backends.

## Related files

- [`chronowarden/database.py`](../../chronowarden/database.py)
- [`chronowarden/app.py`](../../chronowarden/app.py)
- [`deploy/kubernetes/pvc.yaml`](../../deploy/kubernetes/pvc.yaml)
