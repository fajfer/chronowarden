<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Audit follow-ups: webhook masking, route audit events, write cooldowns

- **Status:** implemented
- **Date:** 2026-10-12
- **Issue:** none (from the post-0.7.0 security audit; scope approved by the maintainer on 2026-10-12)

## Goal

Until authentication exists (0.9), anyone who reaches Chronowarden can read and change it. This spec limits
the damage: webhook URLs, which often carry a token, are no longer returned in full; adding and removing a
notification route is recorded in the audit log; and manual syncs and snapshots answer 429 when they are
requested faster than a configured interval.

## Non-goals

- Authentication or per-user limits.
- A race-free metadata write: that needs the `patch` capability, and the maintainer chose to keep the current
  Vault policy. Task 4 documents the race instead.
- Limiting scheduled syncs or period snapshots taken by Chronowarden itself.

## Scope

`chronowarden/api` (owners, sync, compliance), `chronowarden/models/owner.py`, `chronowarden/config.py`,
`config.example.yaml`, README, CHANGELOG, scoped AGENTS.md files.

## Load

- [root AGENTS.md](../../../AGENTS.md)
- [api](../../../chronowarden/api/AGENTS.md), [audit](../../../chronowarden/audit/AGENTS.md),
  [core](../../../chronowarden/AGENTS.md)

## ADRs affected

None. ADR-014 is extended with two event types, which the audit AGENTS.md event list records.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Mask webhook addresses in every owner response: scheme and host kept, path and query replaced by `…` (`https://hooks.slack.com/…`). The stored address is unchanged, so the test route keeps working. | `chronowarden/api/owners.py`, `chronowarden/models/owner.py`, `tests/test_owners.py` | No owners endpoint returns a stored path or query; regression test | done | 94527f7 |
| 2 | Record `owner.route_added` and `owner.route_deleted` (subject `owner:<id>`) with `{id, type, address}`, where the address is masked as in task 1, since audit events are kept forever. | task 1 files, `chronowarden/audit/AGENTS.md` | Both events are in the log with masked addresses; the audit event list is updated | done | 94527f7 |
| 3 | `manual_sync_cooldown` (seconds, default 30) per vault for `POST /sync/vault/{name}`, and `snapshot_min_interval` (seconds, default 60) for `POST /compliance/snapshots`; `0` turns either off. A request that arrives too soon gets 429 with `Retry-After`. The state is kept in memory, per process. | `chronowarden/config.py`, `chronowarden/api/sync.py`, `chronowarden/api/compliance.py`, `config.example.yaml`, `frontend/src/lib/stores/sync.ts` | Config tests, 429 tests for both endpoints, and the UI shows the 429 message | done | 779463a, 3ea2d56 |
| 4 | Document the read-merge-write race in `write_secret_metadata` (an edit made by another team between the read and the write is lost) in the integrations AGENTS.md Gotchas and in the README Vault Permissions section; add a CHANGELOG Unreleased entry for tasks 1-3. | `chronowarden/integrations/AGENTS.md`, `README.md`, `CHANGELOG.md` | Docs updated, `python3 scripts/check_agents_docs.py` passes | done | 670f51f |

## Validation

`uv run black --check . && uv run ruff check . && uv run pytest`, `cd frontend && npm run check`,
`python3 scripts/check_agents_docs.py`.

## Open questions

- None; the maintainer chose "mask and audit", "cooldown in config" and "keep the current policy".
