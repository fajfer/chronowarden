<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-010: Owners and systems assigned to secrets, editable without RBAC for now

- **Status:** Accepted
- **Date:** 2026-10-09 (proposed 2026-07-28)
- **Evidence:** maintainer comment on issue #61 (2026-07-28); maintainer decisions 2026-10-09; README roadmap; PR #26
  gap analysis ("Owners ≠ systems", "Alert routes are inert").

## Context

Issue #61 asks to assign secrets to internal business systems so rotation risk can be grouped by system, which is
needed for compliance evidence (PCI DSS 4.0, DORA). `Owner` exists in the DB and API, but owners can't be assigned
to anything. There is no authentication or RBAC (`frontend/src/lib/stores/auth.ts` is a placeholder).

## Decision

- **System** is its own entity with `name`, `description`, `cmdb_uri` (link to the record in an external CMDB),
  `asset_number` (system or asset identifier) and owners.
- **Assignment**: a secret has at most one system and zero or more owners. Unassigned is an explicit, visible state.
  A secret's effective owners are its own owners, or else its system's owners.
- **Owner** is also the alert-routing target, in the sense Prometheus Alertmanager uses it (ADR-012). Owner and system
  become labels on metrics in the alerting milestone.
- **Where**: assignments are made through the UI/API and stored only in Chronowarden's DB. They are not written back
  to the secret backend. ADR-006's "config is the source of truth" applies to severity only.
- **Permissions**: a secret's owners may edit its metadata, including system and owner assignment. Until
  authentication exists (ADR-015), editing is open to anyone who can reach the API. This is a documented gap,
  accepted to ship compliance features first.

## Consequences

- First schema change on existing tables (`secret_metadata_cache.system_id`). There are no migrations (ADR-005), so a
  guarded `ALTER TABLE` or a migration tool is needed.
- Owner and system assignment need their own endpoints, because `PATCH /secrets/{id}` is being removed (#73,
  ADR-006).
- The audit log (ADR-014) records assignment changes, with free-text identity until ADR-015.
- When ADR-015 lands, editing is restricted to effective owners. RBAC beyond that stays on the roadmap.
- The frontend `Secret.owner` field (PR #60) and the mockups (`mockup-secret-modal.html`,
  `mockup-secrets-table.html`) already reserve space for owner and system.

## Related files

- [`chronowarden/models/owner.py`](../../chronowarden/models/owner.py)
- [`chronowarden/api/owners.py`](../../chronowarden/api/owners.py)
- [`chronowarden/database.py`](../../chronowarden/database.py)
- [`frontend/mockups/mockup-secret-modal.html`](../../frontend/mockups/mockup-secret-modal.html)
