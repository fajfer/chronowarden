<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Hardening before 0.9.0: input limits, webhook responses, CA bundle cleanup

- **Status:** implemented
- **Date:** 2026-10-29
- **Issue:** none

## Goal

Robustness fixes from an internal review, shipped before 0.9.0: a malformed webhook address can't be stored or
break route listings, webhook responses are never read into memory, request bodies and owner lists are capped, and
the temporary CA bundle is removed.

## Non-goals

- Restricting webhook targets by network (private ranges, metadata endpoints): that changes the risk ADR-022
  accepts and needs its own ADR.
- Rate limiting.

## Load

- [root AGENTS.md](../../../AGENTS.md), [alerting](../../../chronowarden/alerting/AGENTS.md),
  [api](../../../chronowarden/api/AGENTS.md), [integrations](../../../chronowarden/integrations/AGENTS.md)

## ADRs affected

None.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Webhook addresses: validate port, host and characters on create; `mask_address` never raises | `chronowarden/models/owner.py`, `chronowarden/api/owners.py`, `tests/test_owners.py` | Malformed addresses → 422; a stored malformed row still lists and deletes | done | 78aa3c8 |
| 2 | Webhook delivery streams the response and closes it unread | `chronowarden/alerting/delivery.py`, `tests/test_webhook_delivery.py` | Test asserts the body is never read and the response is closed | done | 7454491 |
| 3 | Request body cap (1 MiB, also for chunked bodies) and `owner_ids` capped at 1000 | `chronowarden/app.py`, `chronowarden/models/system.py`, new `chronowarden/body_limit.py` | Oversized `Content-Length` and oversized chunked bodies → 413; 1001 owner ids → 422 | done | 344ec15 |
| 4 | Remove the CA bundle on `disconnect_all` and before recreating it | `chronowarden/integrations/manager.py`, `tests/test_manager.py` | No bundle file left after disconnect; reconnect leaves one file | done | b22c459 |
| 5 | CHANGELOG | `CHANGELOG.md` | Entries under Unreleased | done | see PR |

## Validation

`uv run black --check . && uv run ruff check . && uv run pytest`, `python3 scripts/check_agents_docs.py`.

## Open questions

None.
