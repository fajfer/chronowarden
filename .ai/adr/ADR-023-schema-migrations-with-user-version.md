<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-023: Schema migrations with PRAGMA user_version

- **Status:** Accepted
- **Date:** 2026-10-11
- **Evidence:** maintainer decision in the 0.7 scope review (2026-10-11); issue #76; ADR-017
- **Supersedes:** none

## Context

Tables were created with `CREATE TABLE IF NOT EXISTS`, so no schema change reached an existing `chronowarden.db`.
From 0.7 the database holds data that can't be rebuilt (ADR-017), so deleting it on upgrade is no longer an option,
and 0.7 changes existing tables (email routes, the privileged flag, `removed_at`). Alembic would bring SQLAlchemy into
a project that uses plain `sqlite3`.

## Decision

- `chronowarden/migrations.py` holds an ordered list of steps numbered from 1; `PRAGMA user_version` stores the last
  step applied (0 = a database from before migrations).
- `Database.connect()` runs the missing steps at startup, each in its own transaction with the version bump, so a
  failed step is rolled back and startup stops with a `MigrationError`.
- Step 1 is the 0.6 schema with `IF NOT EXISTS`, so a 0.6 database is only marked as version 1.
- A database newer than the code is refused, never downgraded.
- Shipped steps are never edited; every schema change is a new step with a test that upgrades a database from the
  previous release.

## Consequences

- Upgrades keep data; downgrading needs a backup of `chronowarden.db` taken before the upgrade.
- SQLite can't alter constraints, so such steps rebuild the table (create, copy, drop, rename).
- ADR-016's "shipped migrations" requirement for 1.0 is met by this mechanism.

## Related files

- [`chronowarden/migrations.py`](../../chronowarden/migrations.py)
- [`chronowarden/database.py`](../../chronowarden/database.py)
- [`tests/test_migrations.py`](../../tests/test_migrations.py)
