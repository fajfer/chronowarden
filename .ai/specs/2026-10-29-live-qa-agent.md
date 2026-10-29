<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Live QA agent

- **Status:** approved
- **Date:** 2026-10-29
- **Issue:** none

## Goal

An agent tests a change the way an operator would use it: it starts its own isolated environment (vaults, Keycloak,
webhook receiver, Chronowarden from the branch), drives the API and the real UI in a headless browser through
scenario scripts, and reports a PASS/FAIL table with evidence (logs, screenshots, recorded webhooks). It never
touches the maintainer's environment, and it tears everything down afterwards. A failure becomes a finding in the
auditor's format, so it can be fixed the same way.

## Non-goals

- Load or performance testing.
- Testing against production or any environment the agent didn't start.
- Replacing unit and integration tests: scenarios cover flows across components, not every branch.

## Scope

`qa/` (new: `scenarios/`, `conftest.py`, `report.py`), `pyproject.toml` (a `qa` dependency group with Playwright and
a `qa` pytest marker, excluded by default like `integration`), `.agents/skills/live-qa/SKILL.md`,
`.claude/agents/qa.md` (thin wrapper), root router, `.ai/docs/dev-env.md` (shared with the dev env spec).

## Load

- [root AGENTS.md](../../AGENTS.md), [frontend](../../frontend/AGENTS.md), [auth](../../chronowarden/auth/AGENTS.md),
  [alerting](../../chronowarden/alerting/AGENTS.md)
- [Isolated dev env spec](2026-10-29-isolated-dev-env-and-keycloak.md) (this spec needs its tasks 1 to 3),
  [auditor spec](2026-10-29-auditor-agent.md) (finding format)

## ADRs affected

None.

## Design

**Isolation rules** (the skill states them first; each is a check, not advice):

1. Every run uses `./dev-setup.py --run qa-<short id> --auth oidc --app --receiver` and only that run's ports,
   containers and scratch dir; it never uses the `dev` run, `./config.yaml` or `./chronowarden.db`.
2. Teardown always runs (`--cleanup --run qa-<id>`), also after a failure; a run left behind on purpose is named in
   the report.
3. Every command has a timeout; a server started in the background is never piped into `tail`.
4. Kill only processes whose PIDs are in the run's `run.json`, never by pattern.
5. No browser window on the maintainer's screen: Chromium headless only.

**Scenarios** (`qa/scenarios/`, Python Playwright with pytest, marker `qa`). Each scenario logs in through
Keycloak as a seeded user, acts, and asserts on what the UI shows and on the run's state (API, `webhooks.jsonl`, the
vaults):

| Scenario | Proves |
|---|---|
| `test_roles.py` | admin, owner and viewer log in through Keycloak; each sees only the controls ADR-026 allows; logout ends the session |
| `test_rotation.py` | a secret rotated in Vault is detected on sync, shows "awaiting confirmation", the owner confirms it, the next rotation is recalculated |
| `test_permissions.py` | the owner can't confirm a secret it doesn't own (UI hides it, API answers 403); a viewer's API token can read and not write |
| `test_api_tokens.py` | an admin creates a token (shown once), uses it, revokes it; the audit log names the token |
| `test_webhooks.py` | an expired secret sends one signed webhook to the receiver; a test-route sends; a malformed address is refused |
| `test_limits.py` | an oversized body gets 413, 1001 owner ids get 422 |

`qa/report.py` writes `<scratch>/qa-report.md`: a PASS/FAIL table, and for each failure the step, the screenshot,
the last app log lines, and a finding block in the auditor's format.

**When it runs.** On request ("test it live"), before a release PR, and nightly in CI (`qa.yaml`, all scenarios,
report and screenshots as artifacts). The skill picks the scenarios that cover a diff (by changed modules);
`-m qa` runs them all. Screenshots are evidence for failed steps only; there are no visual baselines.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `qa` dependency group and marker; `qa/conftest.py` starting and tearing down a run (fixture), Keycloak login helper | `pyproject.toml`, dev env runbook | One scenario passes from a clean checkout; teardown leaves no container | todo | |
| 2 | The six scenarios | `frontend/src/routes/`, task 1 files | `uv run pytest -m qa` all green on `main` | todo | |
| 3 | `qa/report.py` (PASS/FAIL table, failure evidence, finding blocks) | auditor spec | A deliberately broken check produces a complete finding | todo | |
| 4 | `.agents/skills/live-qa/SKILL.md` (isolation rules, choosing scenarios, reading results) and `.claude/agents/qa.md` | root | A Claude Code session lists the `qa` agent; the skill reads standalone | todo | |
| 5 | Nightly `qa.yaml` workflow (minimal permissions, SHA-pinned actions, artifacts on failure) | deploy | A scheduled run is green; zizmor clean | todo | |
| 6 | Router row "Test a change live", runbook section, CHANGELOG | root | `check_agents_docs.py` passes | todo | |

## Validation

`uv run pytest -m qa` green on `main` twice in a row with no container left afterwards (`podman ps -a --filter
label=chronowarden.devenv.run`), while the maintainer's `dev` run keeps running untouched.

## Open questions

Asked and answered 2026-10-29:

1. Scenarios run **nightly in CI and on request** (and before release PRs), not on every PR.
2. **Playwright for Python in `qa/`**.
3. Screenshots are **evidence on failure only**; no baselines.
