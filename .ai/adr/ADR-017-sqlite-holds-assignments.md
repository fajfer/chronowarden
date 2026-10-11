<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-017: SQLite holds assignments that can't be rebuilt from the backends

- **Status:** Accepted
- **Date:** 2026-10-11
- **Evidence:** maintainer decision on #61 (2026-10-11); ADR-010; `chronowarden/database.py`
- **Supersedes:** ADR-005

## Context

ADR-005 made SQLite a local cache of backend metadata. Everything in it could be rebuilt by syncing, so the 0.6.0
upgrade notes told users to delete `chronowarden.db`. With #61, system and owner assignments are made in Chronowarden
and stored only in its database (ADR-010), so they can't be rebuilt from Vault.

Two properties of the existing cache made it unsuitable to hold them:

- A secret's `id` in `secret_metadata_cache` is an auto-increment row number. It changes when the cache is rebuilt or a
  secret is synced again after its row is gone, so anything stored against it would be orphaned.
- Sync never removes rows for secrets that were deleted in the backend (`delete_secret_metadata` has no callers).

## Decision

- SQLite stays the single local database, and `secret_metadata_cache` stays a rebuildable cache.
- Data entered in Chronowarden (systems, owners, and which secrets they're assigned to) lives in **separate tables**,
  keyed by the secret's real identity: `vault_name` + `engine_id` + `secret_path`, never by the cache row `id`.
- From 0.7 on, `chronowarden.db` must be **backed up**, not deleted. Release notes and the README say so; Kubernetes
  keeps it on the PVC, and Docker users mount it.

## Consequences

- Deleting or rebuilding the cache keeps every assignment.
- New tables are created with `CREATE TABLE IF NOT EXISTS`, so #61 needs no change to existing tables. Changing an
  existing table still needs migrations (#76).
- Assignments to secrets deleted in the backend stay in the database until stale-row handling exists.
- Backup and restore become an operator concern (`chronowarden.db` on the PVC or a mounted volume).

## Related files

- [`chronowarden/database.py`](../../chronowarden/database.py)
- [`.ai/specs/2026-10-09-systems-and-owners.md`](../specs/2026-10-09-systems-and-owners.md)
