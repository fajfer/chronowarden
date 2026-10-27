<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-026: Sessions, API tokens and the permission matrix

- **Status:** Accepted
- **Date:** 2026-10-27
- **Evidence:** maintainer decisions of 2026-10-27 (owner matching, unmapped users, Authlib, sync and snapshot
  rights); issue #75; [ADR-015](ADR-015-authentication.md), [ADR-010](ADR-010-owners-systems-and-permissions.md)
- **Supersedes:** none (extends ADR-015)

## Context

ADR-015 settled how people and API clients log in and which three roles exist. It left open how a login maps to the
Owner records that decide what someone "effectively owns" (ADR-010), what a user without a mapped group gets, where
sessions live, and which role may call which endpoint.

## Decision

- **Owner matching:** a user acts for every Owner whose `email` equals the user's verified email
  (case-insensitive), and for every Owner whose new optional `idp_group` is one of the user's IdP groups (team
  owners). Matching gives rights only together with the `owner` role; `admin` acts everywhere, `viewer` nowhere.
- **Unmapped users:** an authenticated user whose groups match none of `auth.roles` gets 403, unless
  `auth.default_role` is set.
- **OIDC library:** Authlib, for discovery, the authorization code flow with PKCE and ID token validation.
- **Sessions:** server-side in SQLite. The browser holds only a random session ID in an `HttpOnly`,
  `SameSite=Lax` cookie (`Secure` unless the redirect URI is plain HTTP); the database stores its SHA-256 hash with
  the user's name, email, groups and role, resolved at login. Sessions end after `auth.session_lifetime` (default
  `12h`) or at logout; role changes in the IdP apply at the next login.
- **API tokens:** `cwt_<random>`, sent as `Authorization: Bearer`, stored as a SHA-256 hash, with a name, a role,
  an expiry (required, at most `auth.token_max_lifetime`, default `1y`) and, for the `owner` role, exactly one Owner
  it acts for. Admins create and revoke them; the token is shown once. Tokens work in every mode except `none`.
- **Actor:** audit events record `user:<email or username>` or `token:<name>` in `actor`; `source` keeps its
  meaning. A rotation confirmation's `confirmed_by` is the actor, no longer a request field.
- **Permission matrix:**

  | Action | viewer | owner | admin |
  |---|---|---|---|
  | Every `GET` under `/api/v1` | yes | yes | yes |
  | Secret system/owners, confirm rotation, privileged flag | no | secrets they effectively own | yes |
  | Revert an audit event on a secret | no | secrets they effectively own | yes |
  | Own Owner record: name, webhook routes, signing, test send | no | yes | yes |
  | Owner email or `idp_group`, create or delete owners | no | no | yes |
  | `POST /sync/vault/{name}` | no | yes | yes |
  | Systems, compliance snapshots, purging removed secrets, API tokens | no | no | yes |

  Assigning an unowned secret is admin-only (no effective owners means nobody else owns it).
- **Open endpoints:** `/api/v1/health`, `/ready`, `/metrics` (ADR-015), `/info` (the login page needs the theme and
  the auth mode), the login and callback endpoints, and `/docs` / `/openapi.json` (schema only, no data).
- **`auth.mode: none`:** every request is an anonymous admin with a null actor; startup logs a warning and the UI
  shows a banner.

## Consequences

- Upgrading to 0.9 needs an `auth` section; the server refuses to start without one. The one-shot
  `python -m chronowarden sync` does not serve HTTP and doesn't need it.
- Sessions survive restarts, can be revoked, and the cookie carries nothing to sign, so there is no signing key to
  configure.
- A route-coverage test must keep every non-open route behind a permission check; new endpoints need a matrix row.
- Owners with neither a matching email nor an `idp_group` can be edited only by admins.
- `models/entity.py` (reserved users and groups) stays unwired; this design does not need it.

## Related files

- `chronowarden/auth/` (new), `chronowarden/config.py`, `chronowarden/migrations.py`, `chronowarden/api/`
- `frontend/src/lib/stores/auth.ts`
