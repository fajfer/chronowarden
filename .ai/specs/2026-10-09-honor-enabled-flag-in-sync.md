<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Honor `chronowarden_enabled` during sync

- **Status:** draft
- **Date:** 2026-10-09

## Goal

`chronowarden_enabled=false` (set via `PATCH /secrets/{id}` or directly in the backend) means "don't track this
secret" and survives a sync. `severity: none` keeps its own meaning: tracked, never rotated or alerted. Both are
valid (decided 2026-10-09).

## Non-goals

- Removing either flag.
- Config-level `enabled` keys (not requested).

## Scope

`chronowarden/metadata.py`, `chronowarden/api/secrets.py` (read side only, if needed), `architecture/integrations.c4`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [core](../../chronowarden/AGENTS.md)
- [ADR-006](../adr/ADR-006-config-source-of-truth.md)

## ADRs affected

ADR-006 already describes both flags; no change.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `sync_secret_metadata` reads `chronowarden_enabled` with `is_secret_enabled(custom_metadata)` and stores it instead of `enabled=True`; the DB updates when only `enabled` changed | core, `chronowarden/metadata.py` | Regression test in `tests/test_metadata.py`: remote `"false"` → cache `enabled=False` after sync | todo | |
| 2 | Decide whether disabled secrets are still listed by `GET /secrets` (they are today, with `enabled=false`) | [api](../../chronowarden/api/AGENTS.md) | Answer recorded below, test added if behaviour changes | todo | |
| 3 | Keep the `integrations.c4` note consistent (already updated 2026-10-09) | [architecture](../../architecture/AGENTS.md) | Note matches behaviour | done | |

## Validation

`uv run pytest tests/test_metadata.py tests/test_secrets.py`

## Open questions

- Should disabled secrets be skipped entirely during sync (no severity/TTL write-back), or only flagged?
