<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Access control: authentication, roles and API tokens

- **Status:** implemented
- **Date:** 2026-10-27
- **Issue:** #75

## Goal

Nobody can read or change Chronowarden without logging in. People sign in through any OIDC provider or through an
authenticating reverse proxy (oauth2-proxy and similar); pipelines use named API tokens issued by admins. Admins can
do everything, owners can act on the secrets they effectively own (ADR-010), viewers can only read. The audit log
names who made each change. Operators who run Chronowarden on a trusted network must say so with `auth.mode: none`;
without an `auth` section the server refuses to start.

## Non-goals

- RBAC beyond the three roles (custom roles, per-system or per-vault permissions): a later milestone.
- Editing compliance policies in the UI (they stay in config, ADR-019).
- User management in Chronowarden: identities and groups live in the IdP.
- SAML, LDAP, local passwords.
- An integration test against a real IdP container (Dex, Keycloak); the OIDC flow is tested with a fake IdP.
- Wiring or deleting `models/entity.py` (root **Ask First**).

## Scope

`chronowarden/auth/` (new: principal, roles, owner matching, sessions, tokens, OIDC, proxy headers, FastAPI
dependencies), `chronowarden/config.py`, `chronowarden/migrations.py` + `database.py`, `chronowarden/app.py`, every
router in `chronowarden/api/`, `chronowarden/models/` (auth, owner), `frontend/` (auth store, login, client, navbar,
permission-aware controls, Settings → API tokens), `pyproject.toml`/`uv.lock` (authlib), docs, README, deploy
examples, `architecture/`, CHANGELOG.

## Load

- [root AGENTS.md](../../../AGENTS.md)
- [core](../../../chronowarden/AGENTS.md), [api](../../../chronowarden/api/AGENTS.md),
  [models](../../../chronowarden/models/AGENTS.md), [audit](../../../chronowarden/audit/AGENTS.md)
- [ADR-015](../../adr/ADR-015-authentication.md), [ADR-026](../../adr/ADR-026-sessions-tokens-and-permissions.md),
  [ADR-010](../../adr/ADR-010-owners-systems-and-permissions.md)

## ADRs affected

New **ADR-026 Sessions, API tokens and the permission matrix** extends ADR-015 with the decisions below. ADR-010's
"editable without RBAC for now" and ADR-014's "actor stays null" end here: both get a dated *Update* note (task 11).

## Decisions (maintainer, 2026-10-27)

- A user acts for Owners whose **email matches** their verified email, or whose new **`idp_group`** they are in.
- Users whose groups map to no role get **403** unless `auth.default_role` is set.
- OIDC uses **Authlib**.
- **Manual sync:** owner and admin. **Compliance snapshots:** admin only.

## Design

- **Config** `auth` (optional in the model, required by the server's `lifespan`):
  - `mode`: `oidc` | `proxy` | `none`.
  - `oidc`: `issuer`, `client_id`, `client_secret` (`_env`/`_file`, resolution order as for tokens),
    `redirect_uri` (required; must be registered at the IdP), `scopes` (default `openid profile email`),
    `groups_claim` (default `groups`), `username_claim` (default `preferred_username`).
  - `proxy`: `trusted_proxies` (required, CIDRs; headers from other peers are ignored → 401), `user_header`
    (default `X-Forwarded-User`), `email_header` (`X-Forwarded-Email`), `groups_header` (`X-Forwarded-Groups`,
    comma-separated), `logout_url` (optional, e.g. `/oauth2/sign_out`).
  - `roles`: `admin`, `owner`, `viewer`, each a list of IdP groups; the highest matching role wins.
  - `default_role` (optional), `session_lifetime` (default `12h`), `token_max_lifetime` (default `1y`).
- **Principal** (resolved once per request): `name`, `email`, `groups`, `role`, `owner_ids`, `actor`, `kind`
  (`session` | `token` | `proxy` | `anonymous`). Order: `Authorization: Bearer cwt_…` → session cookie (oidc) or
  trusted headers (proxy) → 401. `none` mode yields an anonymous admin.
- **Owner IDs:** Owners with a matching email (case-insensitive; an OIDC email counts only if `email_verified` is
  not false) or an `idp_group` in the user's groups; for an owner token, its one bound Owner.
- **Storage** (migration 11): `sessions` (id hash, name, email, groups JSON, role, created_at, expires_at),
  `oidc_pending` (state, code_verifier, nonce, next path, created_at; rows older than 10 min are dropped),
  `api_tokens` (id, name, token hash, role, owner_id, created_at, expires_at, last_used_at, revoked_at), and
  `owners.idp_group`. Expired sessions and pending logins are deleted on access and at startup.
- **Endpoints** (`/api/v1/auth`): `GET /login?next=` (redirect to the IdP), `GET /callback` (verify state, nonce
  and ID token, create the session, redirect to `next`, same-origin paths only), `POST /logout` (delete the
  session; returns the proxy `logout_url` when set), `GET /me` (principal and mode), `GET/POST/DELETE /tokens`
  (admin; `POST` returns the token once). `/info` gains `auth_mode`.
- **Enforcement:** FastAPI dependencies `require_role(role)` and `require_secret_owner` (secret ID → identity →
  effective owners ∩ principal's owner IDs, admin passes), declared on every route per the ADR-026 matrix. A test
  walks `app.routes` and asserts that every route outside the open list rejects an anonymous request with 401.
- **Audit:** `append_audit_event` gets the principal's `actor` from every API call site; new events
  `token.created`, `token.revoked` (subject `token:<id>`, name, role and owner, never the token or its hash). The
  request field `confirmed_by` is removed; the stored value is the actor.
- **Frontend:** the auth store loads `/auth/me`; the client sends cookies and turns a 401 into a redirect to
  `/login`, which offers "Sign in" (oidc), explains a missing proxy login (proxy), or is skipped (none). The navbar
  shows name and role and logs out. Edit controls show only when allowed (`canEditSecret`, `isAdmin` helpers; the
  server re-checks). Settings gets an **API tokens** tab for admins; the owner dialog gets `idp_group`. `none` mode
  shows a "authentication is off" banner.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | ADR-026 and this spec | ADR-015, ADR-010 | Both merged, indexes updated | done | 4567365 |
| 2 | `AuthConfig` and the `lifespan` refusal | core, `chronowarden/config.py`, `config.example.yaml`, `chronowarden/app.py`, `tests/test_config.py` | Every key validated and documented; server without `auth` fails with a clear `ConfigError`; one-shot sync unaffected; tests | done | d58d848 |
| 3 | Migration 11 and DB methods (sessions, pending logins, tokens, `owners.idp_group`) | models, `chronowarden/migrations.py`, `chronowarden/database.py`, `chronowarden/models/owner.py`, `tests/test_migrations.py`, `tests/test_database.py` | Upgrade test from schema 10; CRUD and expiry tests | done | bd61474 |
| 4 | `chronowarden/auth/`: principal, role resolution, owner matching, token hashing, session lookup, dependencies | ADR-026, `chronowarden/assignments.py`, `chronowarden/database.py` | Unit tests for every role/matching rule, expired and revoked tokens | done | e4d6177 |
| 5 | Proxy and `none` modes in the resolver | task 4 files, `chronowarden/request_guard.py` | Untrusted peer → 401; header parsing tests; `none` → anonymous admin with warning | done | e4d6177 |
| 6 | OIDC login with Authlib: `/auth/login`, `/callback`, `/logout`, `/me` | task 4 files, `pyproject.toml` | Fake-IdP tests: happy path, bad state, bad nonce, wrong issuer/audience, expired token, open redirect refused | done | 720f5b1 |
| 7 | Enforce the matrix on every router; audit actor; `confirmed_by` from the principal | api, audit, every `chronowarden/api/*.py`, their tests, `tests/conftest.py` | Route-coverage test passes; per-role tests for each write endpoint; actor in events | done | fa3e137 |
| 8 | API token endpoints and audit events | api, audit, task 4 files | Create (shown once), list, revoke; owner tokens need an Owner; expiry cap; tests | done | 7a5cb98 |
| 9 | Frontend: auth store, login page, 401 handling, navbar, permission-aware controls, API tokens tab, `idp_group`, `none` banner | frontend, `frontend/src/lib/stores/auth.ts`, `frontend/src/lib/api/client.ts`, `frontend/src/routes/login/+page.svelte`, `frontend/src/routes/settings/+page.svelte` | `npm run check` with no new warnings; manual run in all three modes | done | 3255dea |
| 10 | Docs: guide `docs/guides/authentication.md` (AI draft notice), README warning and roadmap, deploy examples, `config.example.yaml` | deploy, `README.md`, `deploy/compose/config.yaml`, `deploy/kubernetes/` | Every mode documented with an example; the "no authentication" warnings are gone | done | 7ee83a5, df80421 |
| 11 | Architecture model, AGENTS (new `chronowarden/auth/AGENTS.md` + router row), ADR-010/014 update notes, CHANGELOG with upgrade notes | architecture, `CHANGELOG.md` | `python3 scripts/check_agents_docs.py` and LikeC4 validation pass | done | 47e101f |
| 12 | Release 0.9.0: version and changelog | deploy | Release PR merged; the tag waits for the maintainer's go | done | release/0.9.0 PR |

## Validation

`uv run black --check . && uv run ruff check . && uv run pytest`, `cd frontend && npm run check`,
`python3 scripts/check_agents_docs.py`, `docker build -t chronowarden:test .` (and `--target headless`).

## Notes

- Found while implementing: uvicorn's default `--proxy-headers` let `X-Forwarded-For` stand in for the TCP peer, so
  with `FORWARDED_ALLOW_IPS=*` anyone could pose as a trusted proxy. The images run `--no-proxy-headers` (df80421).
- The OIDC flow is tested against a fake IdP only (non-goal: a Dex/Keycloak container test).

## Open questions

None; the maintainer's decisions are recorded above.
