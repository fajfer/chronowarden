<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# compliance: evidence for periodic reviews

## Purpose

Inventory and evidence for reviews done in any process (#93-#95): summaries, gaps, opt-in reporting periods and
frozen, hashed snapshots. Chronowarden stores **no review state** (no checkboxes, no review tables).

## Files

- `periods.py`: `Period`, `period_containing`, `ended_periods`, `period_by_id` (IDs `2026-09`, `2026-Q3`,
  `2026-H2`, `2026`; bounds `[start, end)` in UTC).
- `evidence.py`: `in_scope`, `gaps_of` (`GAP_TYPES`), `summary`, `snapshot_row`, `build_document`, `rows_to_csv`.
  Pure functions over enriched `SecretMetadataResponse`s.
- `../api/compliance.py`: `/compliance/settings`, `/summary`, `/gaps`, `/periods`, `/snapshots` (+ `.json`, `.csv`).
- `../models/compliance.py`, config models `ComplianceScope`, `ReportingCadence` in `../config.py`.

## Contracts

- Config `compliance.reporting.cadences` (one per period kind, scope vaults must exist). None = not opted in: only
  ad-hoc snapshots (label + scope).
- Table `compliance_snapshots` (migration 9): triggers abort UPDATE/DELETE. A correction is a new snapshot with
  `supersedes`; closing a closed period without `supersedes` = latest id is 409.
- Snapshot document = canonical JSON (`audit.chain.canonical_json`) of `{format, created_at, label, cadence,
  period, scope, supersedes, audit: {events, head_hash}, rows}`; `sha256` is over its UTF-8 bytes and `GET .json`
  returns exactly those bytes (`X-Content-SHA256`). The audit head anchors the log against truncation.
- Rows: identity, severity, status, TTL, last rotation (`updated_time`), system (name, CMDB URI, asset number),
  effective owner names, privileged, `removed_at`, last confirmed applied date, awaiting confirmation (null where
  not required). Periodic snapshots also include secrets removed since the period started.
- Gaps (`no_owner`, `no_system`, `expired`, `no_ttl`, `privileged_without_owner`, `awaiting_confirmation`) are shown
  before freezing and never stored in snapshots.
- Every snapshot is a `compliance.snapshot` audit event (subject `snapshot:<id>`).

## How to

- **New row field**: add it to `snapshot_row` and `CSV_COLUMNS`, bump `SNAPSHOT_FORMAT`; old snapshots stay as
  they were hashed.
- **New gap type**: add it to `GAP_TYPES` and `gaps_of`, and its label in `frontend/src/lib/components/GapDialog.svelte`.

## Gotchas

- `/periods` lists periods that ended after the first audit event (startup always records `config.baseline`).
- Status in a snapshot is as of its creation time, not the period end.
- Exports list secret paths; readable by anyone who reaches the API until 0.9 (README warning).

## Related ADRs

[ADR-014](../../.ai/adr/ADR-014-rotation-confirmation-and-audit-log.md),
[ADR-017](../../.ai/adr/ADR-017-sqlite-holds-assignments.md),
[ADR-004](../../.ai/adr/ADR-004-metadata-only-access.md)

## Validate

`uv run pytest tests/test_compliance.py tests/test_privileged.py`
