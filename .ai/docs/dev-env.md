<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Dev environments (runs)

How to start a complete Chronowarden environment that touches nothing else, use it, and tear it down. Every
environment is a **run** of `./dev-setup.py` with a name.

## Isolation rules

Each rule is a check, not advice:

1. Use your own run: `--run <name>`, e.g. `--run qa-<short id>`. The `dev` run (no `--run`) belongs to the
   maintainer: never start, replace or clean it up, and never use `./config.yaml` or `./chronowarden.db`.
2. Clean up what you start, also after a failure: `./dev-setup.py --cleanup --run <name>`. A run you leave on
   purpose is named in your report.
3. Every command gets a timeout. A server started in the background is never piped into `tail`; read its log file.
4. Stop processes only through `--cleanup` (it uses the PIDs in `run.json`), never by name or pattern.
5. `./dev-setup.py --list` shows the runs that have containers; touch only yours.

## Start

```bash
./dev-setup.py --run a --auth oidc --receiver --app      # everything, Chronowarden from source
./dev-setup.py --run a --auth oidc --receiver --app image # the same with the production image
./dev-setup.py --run b                                    # vaults only, no login
```

| Flag | Starts |
|---|---|
| (always) | OpenBao and Vault dev servers (`cw-<run>-openbao`, `cw-<run>-vault`) on free ports, seeded with 3 KV v2 engines × 5 secrets and an AppRole |
| `--auth oidc` | Keycloak 26 (`cw-<run>-keycloak`), realm `chronowarden`, users `admin`, `owner`, `viewer` in groups `cw-admins`, `teams`, `auditors`; the config maps them to the three roles |
| `--receiver` | `devenv/receiver.py` on a free port: answers 200 and appends each request to `<scratch>/webhooks.jsonl` |
| `--app` | `uvicorn chronowarden:app` from this checkout on the run's app port, working dir = scratch, log `<scratch>/app.log` |
| `--app image` | the local `chronowarden:test` image (`docker build -t chronowarden:test .`), host network, scratch as `/data`; logs: `podman logs cw-<run>-app` |

A named run always seeds its database: owner `team-owner` (email `owner@chronowarden.test`, IdP group `teams`, so
the Keycloak `owner` user acts for it), system `payments`, and both `apps/secret-1` secrets assigned to them. With
`--receiver`, the owner has a signed route to `<receiver>/owner` and the config a default route to
`<receiver>/default`.

`--app` serves the UI from `frontend/build`: run `cd frontend && npm run build` first when the UI changed.

## run.json

`<scratch>/run.json` (mode 0600; scratch defaults to `$TMPDIR/chronowarden-<run>/`, mode 0700) holds everything
needed to use the run: `urls` (`app`, `dev-openbao`, `dev-vault`, `keycloak`, `receiver`), `users` (Keycloak
passwords), `root_tokens` (per vault, to change secrets in Vault), `signing_secrets` (`owner-route`, to verify
webhook signatures), `pids` and `containers`. These are throwaway dev credentials; don't copy them into reports.

## Using it

- Browser: open `urls.app`, log in as a Keycloak user. Cookies are per host, not per port, so two runs in one
  browser profile log each other out; use one profile (or Playwright context) per run.
- Scripts with `requests`: Keycloak sets `Secure` cookies, which browsers send to `http://localhost` but
  `requests` doesn't. After loading the login form, set `cookie.secure = False` on the session's cookies
  (`tests/integration/test_keycloak.py` shows the whole flow).
- State-changing API calls with a session cookie need `Sec-Fetch-Site: same-origin` (the CSRF guard); API tokens
  don't.
- Change a secret: `hvac.Client(url=urls["dev-vault"], token=root_tokens["dev-vault"])`, then sync through the API
  (`POST /api/v1/sync/provider/dev-vault`).

## Clean up

`./dev-setup.py --cleanup --run <name>` stops the run's processes, removes its containers (by the label
`chronowarden.devenv.run=<name>`) and deletes the scratch dir, but only a scratch dir that has a `run.json`.
Starting a run with an existing name replaces that run alone.
