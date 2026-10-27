<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Authentication

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

Since 0.9 every request needs a caller, except the health endpoints (`/api/v1/health`, `/ready`, `/metrics`,
`/info`) and the login flow. Chronowarden refuses to start without an `auth` section in `config.yaml`.

## Choose a mode

| `auth.mode` | Who logs people in | Use it when |
|---|---|---|
| `oidc` | Chronowarden itself, against any OIDC provider (Keycloak, Entra ID, Okta, Dex, …) | you can register a client at your IdP |
| `proxy` | a reverse proxy in front of Chronowarden (oauth2-proxy, Pomerium, …) that passes identity headers | your platform already authenticates at the edge |
| `none` | nobody: every request is an admin | only on a trusted network, e.g. your laptop |

API tokens work in `oidc` and `proxy` mode.

## Roles

Map IdP groups to roles; a user in groups of several roles gets the highest.

```yaml
auth:
  roles:
    admin: [chronowarden-admins]
    owner: [platform-teams, payments-team]
    viewer: [auditors]
  # default_role: viewer   # for users in none of these groups; unset means they get 403
```

| | viewer | owner | admin |
|---|---|---|---|
| Read everything (secrets, audit log, compliance, alerts) | ✔ | ✔ | ✔ |
| Assign system and owners, confirm rotations, set the privileged flag, revert those changes | | secrets they own | ✔ |
| Rename their owner, manage its webhook routes | | ✔ | ✔ |
| Trigger a sync | | ✔ | ✔ |
| Systems, owners (create, delete, email, IdP group), snapshots, purges, API tokens | | | ✔ |

**Which secrets does an owner own?** A user acts for every owner whose **email** matches their verified email, and
for every owner whose **IdP group** (Settings → Owners → Edit) is one of their groups. They own the secrets those
owners are effectively responsible for: the secret's own owners, or else its system's owners. Secrets without any
owner are assigned by admins.

Role changes in the IdP apply at the next login; owner changes in Chronowarden apply at once.

## OIDC

Register a confidential client (or a public one; PKCE is always used) with the redirect URI
`https://<your host>/api/v1/auth/callback`, and make sure the ID token carries the groups.

```yaml
auth:
  mode: oidc
  oidc:
    issuer: https://idp.example.com/realms/main
    client_id: chronowarden
    client_secret_env: CHRONOWARDEN_OIDC_CLIENT_SECRET   # or client_secret_file
    redirect_uri: https://chronowarden.example.com/api/v1/auth/callback
    # groups_claim: groups
    # username_claim: preferred_username
  roles:
    admin: [chronowarden-admins]
  # session_lifetime: 12h
```

- Keycloak: add a *Group Membership* mapper (claim `groups`, *Full group path* off) to the client's dedicated scope.
- Entra ID: set `groupMembershipClaims` in the app manifest; groups arrive as object IDs, so map those IDs in `roles`.
- Chronowarden checks the ID token's signature, issuer, audience, expiry and nonce. Emails count for owner matching
  only when the IdP doesn't mark them unverified (`email_verified: false`).
- Sessions are stored in `chronowarden.db` (only a hash of the session ID); the cookie is `HttpOnly`, `SameSite=Lax`,
  and `Secure` when the redirect URI is HTTPS.
- An IdP with a private CA: point `REQUESTS_CA_BUNDLE` at a bundle that includes it.

## Reverse proxy

The proxy authenticates the user and passes their name, email and groups in headers. Chronowarden believes those
headers only from `trusted_proxies`; requests from anywhere else must log in another way or get 401.

```yaml
auth:
  mode: proxy
  proxy:
    trusted_proxies: [10.0.0.0/8]       # the proxy's address(es); required
    # user_header: X-Forwarded-User      # oauth2-proxy defaults
    # email_header: X-Forwarded-Email
    # groups_header: X-Forwarded-Groups  # comma-separated
    logout_url: /oauth2/sign_out
  roles:
    admin: [chronowarden-admins]
```

With oauth2-proxy as a reverse proxy, `--pass-user-headers` (the default) sends these headers; include the groups
with your provider's groups scope or claim. Pipelines with an API token can't log in at the proxy: let them reach
Chronowarden on a path that bypasses it, such as the internal Kubernetes Service. Requests on that path come from
an untrusted peer, so any identity headers they carry are ignored and only the token counts.

## API tokens

Admins create tokens in **Settings → API tokens**: a name, a role, an expiry (at most `token_max_lifetime`, default
one year) and, for the owner role, the owner it acts for. The token is shown once.

```bash
curl -H "Authorization: Bearer cwt_..." https://chronowarden.example.com/api/v1/secrets/
```

Chronowarden stores only a hash of each token. Changes made with a token appear in the audit log as
`token:<name>`; changes made by people as `user:<email or name>`. Revoking a token takes effect at once.

## Upgrading to 0.9

Add an `auth` section before upgrading; without one the server stops at startup with a message saying so. To keep
the old behaviour on a trusted network, add:

```yaml
auth:
  mode: none
```

The one-shot `python -m chronowarden sync` doesn't serve HTTP and doesn't need the section.
