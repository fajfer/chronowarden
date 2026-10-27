<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# auth: authentication and permissions

## Purpose

Who is calling and what they may do ([ADR-015](../../.ai/adr/ADR-015-authentication.md),
[ADR-026](../../.ai/adr/ADR-026-sessions-tokens-and-permissions.md)): OIDC sessions, trusted proxy headers or API
tokens become a `Principal` with a role (`admin` > `owner` > `viewer`) and the owners it acts for.

## Files

- `principal.py`: `Principal` (`actor`, `at_least`, `acts_for`), `ANONYMOUS_ADMIN` (`auth.mode: none`),
  `role_for(groups, auth)` (highest mapped role, else `default_role`).
- `tokens.py`: `new_session_id`, `new_api_token` (`cwt_` prefix), `digest` (SHA-256; only hashes are stored).
- `resolve.py`: `resolve_principal(request, auth, db, now)`, `SESSION_COOKIE`. Bearer token first (a bad one never
  falls back), then the session cookie (oidc) or the identity headers (proxy, only from `trusted_proxies`).
- `dependencies.py`: `authenticated` (401/403/503, caches the principal on `request.state`), `require_role`,
  `admin_only`, `owner_or_admin`, `check_acts_for`, `request_actor`.
- `oidc.py`: `OidcClient` (Authlib code flow with PKCE, cached discovery and keys, ID token checks), `OidcError`.
- `../api/auth.py`: `/auth/login`, `/callback`, `/logout`, `/me`, `/tokens`. `../models/auth.py`: `Me`, `ApiToken*`.
- `../config.py`: `AuthConfig`, `OidcConfig`, `ProxyConfig`, `RoleGroups`, `ROLES`, `require_auth` (lifespan).

## Contracts

- Every router except health and auth's login/callback/logout has `dependencies=[Depends(authenticated)]`; write
  routes add `admin_only`, `owner_or_admin` or an ownership dependency (`secrets.secret_access`,
  `owners.owner_record_access`) per the ADR-026 matrix. `tests/test_permissions.py` walks the OpenAPI schema: a new
  route fails it until it is protected (or listed as open, which needs an ADR change).
- Owners act for Owners matched by verified email or `idp_group` (`Database.owner_ids_for`), re-read on every
  request; roles are fixed at login for sessions, per request for proxy headers.
- Audit events from the API pass `actor=request_actor(request)`; `source` keeps its meaning (`ui`/`api`).
- Never store or log session IDs or tokens; store `digest(...)` only. Never put them in audit events.

## Gotchas

- Tests run in `none` mode through the autouse `no_login` fixture in `tests/conftest.py`; auth tests patch
  `chronowarden.auth.dependencies._get_auth_context` (and `chronowarden.api.auth._get_app_dependencies`) on top.
- `api.auth._client` caches one `OidcClient` per config object; patch it to `None` to force fresh discovery.
- `last_used_at` of a token is written at most every 5 minutes; it is a hint, not audit data.
- With `auth: None` (server never started) `authenticated` answers 503: fail closed.

## Related ADRs

[ADR-015](../../.ai/adr/ADR-015-authentication.md), [ADR-026](../../.ai/adr/ADR-026-sessions-tokens-and-permissions.md),
[ADR-010](../../.ai/adr/ADR-010-owners-systems-and-permissions.md)

## Validate

`uv run pytest tests/test_auth.py tests/test_auth_oidc.py tests/test_api_tokens.py tests/test_permissions.py`
