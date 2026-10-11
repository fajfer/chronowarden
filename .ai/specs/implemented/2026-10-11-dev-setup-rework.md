<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Dev setup rework: podman, testcontainers, integration tests

- **Status:** implemented
- **Date:** 2026-10-11
- **Issue:** #78

## Goal

`dev-setup.py` is small, typed and safe: it runs on podman (preferred) or docker, never overwrites a config it
didn't write, and shares its backend definitions and seeding with integration tests that run Chronowarden against
real OpenBao and HashiCorp Vault containers (testcontainers) in CI, replacing the manual live checks.

## Non-goals

- Changing what the dev vaults contain (3 KV v2 engines × 5 secrets, an AppRole with the documented policy).
- Making integration tests required checks (a repository setting, the maintainer's call).
- Shipping `devenv/` in the wheel (it builds only `chronowarden/`).

## Decisions

- Runtime: `CHRONOWARDEN_CONTAINER_RUNTIME` if set, else `podman`, else `docker` (podman's CLI is compatible).
- Root token: a random token passed in with `VAULT_DEV_ROOT_TOKEN_ID` / `BAO_DEV_ROOT_TOKEN_ID` instead of parsing
  container logs; printed once at the end, never logged.
- `config.yaml` is only (re)written when it is missing, starts with the dev-setup header, or `--force` is given.
- Integration tests live in `tests/integration/`, marked `integration`, skipped by default (`addopts`), run with
  `uv run pytest -m integration`; testcontainers in the dev group (works with podman via `DOCKER_HOST`).

## Scope

`dev-setup.py`, new `devenv/`, `tests/integration/`, `tests/test_devenv.py`, `pyproject.toml`, `uv.lock`,
`.github/workflows/ci.yaml`, `README.md`, `CONTRIBUTING.md`, `deploy/AGENTS.md`.

## Load

- [root AGENTS.md](../../../AGENTS.md)
- [deploy](../../../deploy/AGENTS.md), [integrations](../../../chronowarden/integrations/AGENTS.md)

## ADRs affected

None.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `devenv/`: runtime detection, backend specs (images as today), seeding (engines, secrets, policy, AppRole) | deploy | Unit tests for runtime choice and config writing | done | 52f0741 |
| 2 | `dev-setup.py` rewritten on `devenv/` (`--cleanup`, `--force`, safe config writing, token via env) | deploy | Runs on podman and docker; refuses to overwrite a hand-written config | done | 52f0741 |
| 3 | Integration tests (both backends): connect with AppRole, sync keeps other keys and settings, removed/reappeared, privileged write, observed rotation | integrations | `uv run pytest -m integration` passes locally on docker; on podman all assertions pass but podman's API returns 500 when testcontainers removes a container | done | 9593893 |
| 4 | CI job running the integration tests | deploy | Job green on the PR | done | 9593893 |
| 5 | README "Development Environment", CONTRIBUTING, deploy AGENTS.md | deploy | Docs match | done | 9593893 |

## Validation

`uv run pytest`, `uv run pytest -m integration`, black, ruff, `check_agents_docs.py`, `dev-setup.py` on both runtimes.
