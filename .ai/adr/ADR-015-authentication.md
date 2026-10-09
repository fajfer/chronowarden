<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-015: Authentication for UI and API

- **Status:** Proposed
- **Date:** 2026-10-09
- **Evidence:** README roadmap (RBAC); `frontend/src/lib/stores/auth.ts` (placeholder, no auth backend); ADR-010.

## Context

The API is fully unauthenticated: anyone who reaches it can trigger syncs, write metadata to vaults through `PATCH` (until #73) and edit owners. RBAC is on the roadmap, and ADR-010 assumes secret owners can be identified.

## Decision

**Not decided yet.** Options:

- OIDC in the app (login flow plus bearer tokens for API clients).
- Authentication at a reverse proxy (oauth2-proxy and similar) that passes trusted identity headers.
- Both: trust headers when they're configured, otherwise use OIDC.

## Consequences

This is a prerequisite for RBAC (milestone 0.9), for real identities in the ADR-014 audit log, and for restricting
editing to effective owners (ADR-010; open until then). `/api/v1/health`, `/ready` and `/metrics` stay unauthenticated for probes and scrapers.

## Related files

- [`chronowarden/app.py`](../../chronowarden/app.py)
- [`frontend/src/lib/stores/auth.ts`](../../frontend/src/lib/stores/auth.ts)
- [`chronowarden/models/entity.py`](../../chronowarden/models/entity.py)
