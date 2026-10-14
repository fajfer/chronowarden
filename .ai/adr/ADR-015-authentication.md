<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-015: Authentication for UI and API

- **Status:** Accepted
- **Date:** 2026-10-09
- **Evidence:** maintainer decisions of 2026-10-14; README roadmap (RBAC); `frontend/src/lib/stores/auth.ts` (placeholder, no auth backend); ADR-010.

## Context

The API is fully unauthenticated: anyone who reaches it can trigger syncs, write metadata to vaults through `PATCH` (until #73) and edit owners. RBAC is on the roadmap, and ADR-010 assumes secret owners can be identified.

## Decision

Settled by the maintainer on 2026-10-14 (milestone 0.9):

- **Login:** built-in OIDC (authorization code flow with PKCE against any OIDC provider) **or** trusted identity
  headers from an authenticating reverse proxy (e.g. oauth2-proxy), chosen in config.
- **API clients:** named API tokens issued in Chronowarden by admins, scoped to a role, with an expiry, stored
  hashed, and attributed in the audit log.
- **Roles:** `admin` (everything), `owner` (confirm rotations, set the privileged flag and manage routes for secrets
  they effectively own, ADR-010) and `viewer` (read-only); roles come from IdP groups mapped in config.
- **Default:** Chronowarden refuses to start unless authentication is configured or `auth.mode: none` is set
  explicitly for trusted networks.

## Consequences

This is a prerequisite for RBAC (milestone 0.9), for real identities in the ADR-014 audit log, and for restricting
editing to effective owners (ADR-010; open until then). `/api/v1/health`, `/ready` and `/metrics` stay unauthenticated for probes and scrapers.

## Related files

- [`chronowarden/app.py`](../../chronowarden/app.py)
- [`frontend/src/lib/stores/auth.ts`](../../frontend/src/lib/stores/auth.ts)
- [`chronowarden/models/entity.py`](../../chronowarden/models/entity.py)
