<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-010: Owners as alert-routing targets, systems as CMDB-linked entities, no RBAC yet

- **Status:** Proposed
- **Date:** 2026-07-28
- **Evidence:** maintainer comment on issue #61 (2026-07-28); README roadmap; PR #26 gap analysis ("Owners ≠
  systems", "Alert routes are inert").

## Context

Issue #61 asks to assign secrets to internal business systems so rotation risk can be grouped by system. Today
`Owner` and notification routes exist in the DB and API (`chronowarden/api/owners.py`), but owners can't be
assigned to secrets, and `test-route` sends nothing. There is no authentication or RBAC
(`frontend/src/lib/stores/auth.ts` is a placeholder; `models/entity.py` is reserved).

## Decision

Proposed by the maintainer in #61:

- **Owner** is the alert-routing target, in the sense Prometheus Alertmanager uses routes and receivers. Owners are
  assigned to secrets to decide where alerts go.
- **System** is its own entity with its own schema, not a free-text tag. It can reference an external CMDB via a URI
  and/or a system or asset number.
- **Permissions**: no RBAC for now. A secret's owners may edit its metadata, including its system assignment.

## Consequences

- #61 needs its specification reworked around this model before implementation (maintainer, 2026-07-28).
- The secret metadata response gains owner and system references; the frontend `Secret.owner` field (PR #60)
  prepares for this.
- RBAC (README roadmap, `models/entity.py`) stays out of scope until a later ADR.

## Related files

- [`chronowarden/models/owner.py`](../../chronowarden/models/owner.py)
- [`chronowarden/api/owners.py`](../../chronowarden/api/owners.py)
- [`chronowarden/models/entity.py`](../../chronowarden/models/entity.py)
