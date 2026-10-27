<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-014: Rotation confirmation, audit log and change history

- **Status:** Accepted
- **Date:** 2026-10-11
- **Evidence:** issues #24, #18; maintainer decisions of 2026-10-11
- **Supersedes:** none

## Context

Compliance work needs to show what happened to each secret and when. A fresh secret in a vault isn't proof that it
was applied where it is used (#18), and changes made in Vault by other teams were invisible to Chronowarden.

## Decision

- One **append-only SQLite table with hash-chained rows**, exported as JSONL, kept forever.
- Every change Chronowarden sees on a secret is recorded with before/after values: Chronowarden-managed fields, all
  custom metadata (keys and values), rotations (versions, never values), Vault settings, and config changes affecting
  secrets. Changes made in Vault are recorded as observed by sync.
- Revert creates a new event and is allowed only for Chronowarden data and `chronowarden_*` keys (ADR-004).
- Rotation confirmation is part of the same log (ADR-021).
- Actor: the source only ("sync", "config", "ui", "api"; the API may pass `confirmed_by`) until authentication
  (ADR-015) provides real identities.
- Every snapshot records the log's head hash and row count, anchoring the chain.

## Consequences

- The database holds history that can't be rebuilt (ADR-017: back it up).
- The log grows with every observed change; metadata is small, so no retention limit is set.
- Other teams' custom metadata values are stored in Chronowarden and visible to anyone who reaches it until 0.9.
- *Update 2026-10-27:* since 0.9 ([ADR-026](ADR-026-sessions-tokens-and-permissions.md)) API changes record the
  actor (`user:<email or name>`, `token:<name>`), and `confirmed_by` is the actor instead of a request field.

## Related files

- `chronowarden/audit/` (new), `chronowarden/metadata.py`, `chronowarden/database.py`
