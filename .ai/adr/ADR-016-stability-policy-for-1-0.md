<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-016: What 1.0 guarantees

- **Status:** Proposed
- **Date:** 2026-10-09
- **Evidence:** Issues #16, #30 (no deprecations before 1.x); root `AGENTS.md` pre-1.0 rule.

## Context

Before 1.0, config, API and DB schema change freely with no compatibility shims. Users need to know what 1.0 will promise.

## Decision

**Not decided yet.** Candidate guarantees from 1.0:

- Config: removed or renamed keys go through one minor release with a deprecation warning.
- REST API: `/api/v1` stays backward compatible; breaking changes go to `/api/v2`.
- Metrics: names and labels are stable (alert rules depend on them, ADR-012).
- DB: schema migrations ship with the release (none exist today, ADR-005).

## Consequences

When accepted, it replaces the pre-1.0 rule in the root `AGENTS.md`, and a migration tool becomes a 1.0 requirement.

## Related files

- [`AGENTS.md`](../../AGENTS.md)
- [`chronowarden/config.py`](../../chronowarden/config.py)
- [`chronowarden/database.py`](../../chronowarden/database.py)
