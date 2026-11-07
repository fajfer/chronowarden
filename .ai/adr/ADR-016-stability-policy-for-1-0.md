<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-016: What 1.0 guarantees

- **Status:** Accepted
- **Date:** 2026-11-07
- **Evidence:** maintainer decisions of 2026-11-07; issues #16, #30 (no deprecations before 1.x); root `AGENTS.md`
  pre-1.0 rule
- **Supersedes:** none

## Context

Before 1.0, config, API, metrics, webhook payloads and DB schema change freely with no compatibility shims. Users
need to know what 1.0 promises, and contributors need to know what they may no longer break within 1.x.

## Decision

From 1.0, within a major version:

- **REST API:** `/api/v1` stays backward compatible: fields and endpoints may be added, never removed, renamed or
  given a different meaning. A breaking change goes to `/api/v2`.
- **Metrics:** Prometheus metric names and labels don't change (alert rules depend on them, ADR-022). New metrics
  and new label values may be added.
- **Webhook payloads:** fields may be added, never removed or renamed, and existing fields keep their meaning
  (ADR-025).
- **Database:** every 1.x release upgrades the database in place on start (`PRAGMA user_version`, ADR-023), with no
  manual step.
- **Config:** keys are only added in 1.x; removing or renaming a key waits for 2.0. There are no deprecation
  warnings or aliases. Instead, all config keys are reviewed and renamed or removed **before 1.0**, as a task on the
  1.0 milestone.

## Consequences

- The pre-1.0 rule in the root `AGENTS.md` (no deprecation warnings or shims) holds until 1.0 ships; from then on,
  the guarantees above are the rule, and the root `AGENTS.md` changes with the 1.0 release.
- The config key review is a 1.0 requirement, as is a check that metric names, API fields and webhook payload
  fields are ones the project wants to keep.
- A change that would break one of these guarantees in 1.x needs a new major version, or a superseding ADR.

## Related files

- [`AGENTS.md`](../../AGENTS.md)
- [`chronowarden/config.py`](../../chronowarden/config.py)
- [`chronowarden/database.py`](../../chronowarden/database.py)
