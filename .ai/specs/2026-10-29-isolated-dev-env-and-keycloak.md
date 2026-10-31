<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Isolated dev environments with Keycloak

- **Status:** in progress
- **Date:** 2026-10-29
- **Issue:** none

## Goal

A person or an agent starts a complete Chronowarden environment with one command and gets one that touches nothing
else: its own containers, free ports, its own scratch directory (config, database, logs), seeded data, and
optionally a real OIDC login against Keycloak with admin, owner and viewer users. Several environments can run side
by side, and each is torn down by its name. The maintainer's existing `./dev-setup.py` flow keeps working unchanged.
A testcontainers test proves a real Keycloak login end to end.

## Non-goals

- Proxy mode in the dev env (oauth2-proxy): not chosen (2026-10-29); proxy mode stays covered by unit tests.
- Other IdPs (Dex, Authentik, Entra ID).
- Running Chronowarden from the container image by default: `--app` runs the source; `--app image` is the option.

## Scope

`dev-setup.py`, `devenv/` (new `keycloak.py`, `receiver.py`, `seed` data for owners and systems),
`devenv/keycloak/realm.json` (template), `tests/integration/test_keycloak.py`, `.github/workflows/ci.yaml`
(integration job), README "Development", `deploy/AGENTS.md`, new runbook `.ai/docs/dev-env.md`, root router.

## Load

- [root AGENTS.md](../../AGENTS.md), [deploy](../../deploy/AGENTS.md), [auth](../../chronowarden/auth/AGENTS.md)
- [ADR-015](../adr/ADR-015-authentication.md), [ADR-026](../adr/ADR-026-sessions-tokens-and-permissions.md)
- `dev-setup.py`, `devenv/*.py`, `tests/integration/test_backends.py`, `docs/guides/authentication.md`

## ADRs affected

None.

## Design

**Runs.** Every environment is a *run* with a name (`--run <name>`, default `dev`):

- Containers are named `cw-<run>-openbao`, `cw-<run>-vault`, `cw-<run>-keycloak` and labelled
  `chronowarden.devenv.run=<run>`; cleanup removes by label, so it never touches another run's containers.
- The `dev` run keeps today's names (`openbao-dev`, `vault-dev`), ports 8200/8201 and `./config.yaml`, so the
  maintainer's flow doesn't change. Any other run picks free ports and writes everything to
  `--scratch <dir>` (default `$TMPDIR/chronowarden-<run>/`): `config.yaml`, `chronowarden.db`, `app.log`,
  `run.json` (ports, URLs, users, PIDs).
- Before starting, the requested ports are checked; a busy fixed port aborts instead of silently talking to
  whatever listens there.
- `--cleanup --run <name>` stops the app and removes the run's containers and scratch dir; `--list` prints runs by
  label. Starting a run that exists replaces only that run.

**Auth.** `--auth none` (default) or `--auth oidc`:

- Keycloak (pinned image, `start-dev`, realm imported from `devenv/keycloak/realm.json` with the redirect URI filled
  in): client `chronowarden` (confidential, PKCE S256), a *Group Membership* mapper (claim `groups`, full path off),
  groups `cw-admins`, `teams`, `auditors`, and users `admin`, `owner`, `viewer` (one group each) with generated
  passwords written to `run.json`.
- The written config maps `cw-admins` → admin, `teams` → owner, `auditors` → viewer, and points `auth.oidc` at the
  realm.

**Data and helpers.**

- Seeding adds what the UI needs to be exercised: secrets in several engines (today), plus an owner whose email
  matches the `owner` user and whose IdP group is `teams`, a system with that owner, and a webhook route.
- `--receiver` starts a local webhook receiver (`devenv/receiver.py`, the logic of `tests/conftest.py` `Receiver`)
  that appends every request to `<scratch>/webhooks.jsonl`, so alerts can be checked from outside.
- `--app` also starts `uv run uvicorn chronowarden:app` on a free port with the run's config and working directory,
  logging to `app.log`, and waits for `/api/v1/ready`. `--app image` runs the locally built production image
  instead, with the scratch dir mounted, to test what ships.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Runs: names, labels, free ports, port check, scratch dir, `run.json`, `--list`, `--cleanup --run`; `dev` unchanged | `dev-setup.py`, `devenv/runtime.py`, `devenv/config.py` | Two runs side by side and `dev` untouched; unit tests for naming, port choice and cleanup by label | done | c83039c |
| 2 | Keycloak: realm template, start and wait, `--auth oidc` config | `devenv/`, `docs/guides/authentication.md` | Logging in as each user in a browser gives the expected role in `/api/v1/auth/me` | done | 02c318b |
| 3 | Seed owners and systems; `--receiver`; `--app` and `--app image` | `devenv/backends.py`, `tests/conftest.py` | A sync sends a webhook the receiver records; the `owner` user acts for the seeded owner | done | cbeea6a |
| 4 | Integration test: Keycloak in testcontainers, the full authorization code flow driven over HTTP (login form post), roles per user, logout | `tests/integration`, `chronowarden/auth/oidc.py` | `pytest -m integration` green locally and in the existing CI integration job | done | ec9cb04 |
| 5 | Runbook `.ai/docs/dev-env.md` (isolation rules, flags, what `run.json` holds), README "Development", `deploy/AGENTS.md`, router row "Run the app or a dev env", CHANGELOG | deploy, `README.md` | `check_agents_docs.py` passes | done | |

## Validation

`uv run black --check . && uv run ruff check . && uv run pytest`, `uv run pytest -m integration`,
`python3 scripts/check_agents_docs.py`, and by hand: `./dev-setup.py` (unchanged; the maintainer's check, since
agents leave the `dev` run alone), then
`./dev-setup.py --run a --auth oidc --app --receiver` and `--run b` side by side, both cleaned up by name.

## Open questions

Asked and answered 2026-10-29:

1. Chronowarden in a run: **from source by default, `--app image` as an option**.
2. The Keycloak test runs **in the existing integration job** on every PR.
