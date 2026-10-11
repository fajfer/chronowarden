<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Compliance evidence: privileged flag, snapshots, Compliance tab

- **Status:** in progress
- **Date:** 2026-10-11
- **Issue:** #93, #94, #95

## Goal

Chronowarden provides **inventory and evidence** for periodic reviews done in any process: secrets carry a
privileged flag set in Vault; a **Compliance** tab shows summaries, frozen snapshots, the audit log, a read-only tree
and the compliance settings. Snapshots freeze the inventory of a chosen scope with a SHA-256, either ad hoc or for a
period of an opt-in cadence, after warning about gaps.

## Non-goals

- Review state (no checkboxes, no review tables): reviews happen elsewhere.
- Editing settings in the UI (config only until authentication, 0.9).
- Automatic period closing (0.8) and policies/PDF (0.7.x).
- Writing anything to Vault except `chronowarden_privileged` (ADR-004).

## Design

**Privileged flag.** Vault custom-metadata key `chronowarden_privileged`; only `"true"` (case-insensitive) counts,
other values are logged as warnings. Sync reads it into a new cache column (part of the 0.7 migration; rebuildable
from Vault). `PUT /api/v1/secrets/{id}/privileged` (`{"privileged": true|false}`) writes it to Vault with the 0.6.3
read-merge-write and records the change in the audit log. `GET /secrets/` gains a `privileged` filter.

**Config.**

```yaml
compliance:
  reporting:                 # absent or empty = not opted in
    cadences:
      - period: quarterly    # monthly | quarterly | half-yearly | yearly
        scope: { systems: [Billing, CRM], privileged_only: true }
      - period: yearly
        scope: {}            # whole instance
```

Strict like the rest of `config.py`; shown read-only in the Compliance tab.

**Snapshots.** A snapshot freezes, for its scope (vaults, engines, systems, privileged only), one row per secret:
vault, engine, path, severity, status, TTL date, last rotation, system (name, CMDB URI, asset number), effective
owners, privileged, `removed_at` within the period, last confirmed applied date and awaiting confirmation (where
required). The snapshot also stores the audit log head hash and row count. Canonical JSON (sorted keys, UTF-8, no
extra whitespace, UTC ISO
8601) and its SHA-256 are stored; a correction is a new snapshot referencing the old one; no update or delete through
the API. `POST /api/v1/compliance/snapshots` (`{label | period, scope}`), list, get, and exports
`GET /api/v1/compliance/snapshots/{id}.csv` / `.json`. Ad-hoc snapshots carry a free label and a scope chosen when
taken; periodic ones carry the period and the cadence's scope from config.

**Gaps.** Before creating or closing, `GET /api/v1/compliance/gaps?scope=…` lists secrets with no effective owner, no
system, expired or no TTL, privileged without an owner, or a rotation awaiting confirmation. The UI warns and lets the
user continue; the snapshot records nothing about gaps.

**Periods.** With a cadence configured, the tab shows ended, unclosed periods ("Q3 2026 ended, close it"); closing
creates the periodic snapshot.

**Summaries.** Total and privileged counts per vault, engine and system.

**Compliance tab.** Sidebar section with Summaries, Snapshots (list, create with scope, close period, downloads,
hash), Audit log (from the audit-log spec), Tree (read-only: vault → engine → path, or system → secrets; nodes show
total, privileged and status counts, leaves link to the detail view), Settings
(read-only view of `compliance` config and the confirmation cascade). The secrets table gets a Privileged column and
filter; the secret detail view a privileged toggle.

## Scope

`chronowarden/config.py`, `config.example.yaml`, `chronowarden/database.py`, `chronowarden/metadata.py`,
`chronowarden/models/`, `chronowarden/api/`, new `chronowarden/compliance/`, `frontend/`, `architecture/main.c4`,
`README.md`, `CHANGELOG.md`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [core](../../chronowarden/AGENTS.md), [models](../../chronowarden/models/AGENTS.md),
  [api](../../chronowarden/api/AGENTS.md), [frontend](../../frontend/AGENTS.md)
- [ADR-004](../adr/ADR-004-metadata-only-access.md), [ADR-010](../adr/ADR-010-owners-systems-and-permissions.md),
  [ADR-017](../adr/ADR-017-sqlite-holds-assignments.md), [ADR-014](../adr/ADR-014-rotation-confirmation-and-audit-log.md)
- [systems and owners spec](implemented/2026-10-09-systems-and-owners.md)

## ADRs affected

None new; follows ADR-004 (only `chronowarden_*` keys written), ADR-010, ADR-017 and ADR-014.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Privileged: sync reads `chronowarden_privileged` (strict, warnings), cache column via migration, `PUT /secrets/{id}/privileged` writing to Vault, `privileged` filter, audit event | core, models, api | Tests: true/false/invalid values, toggle round-trips through Vault, other keys untouched, filter | done | f47ebb5 |
| 2 | Frontend: Privileged column, filter and detail toggle | frontend | `npm run check` clean; manual check against both dev vaults | done | 99f8e7c |
| 3 | `compliance` config models and `config.example.yaml` (cadences with scope) | core | Config tests: valid, unknown period, bad scope | todo | |
| 4 | Snapshots: tables, canonical JSON + SHA-256, scope filter, create/list/get, CSV/JSON export, supersedes link, no update/delete | models, api | Tests: same state → same hash; scope filters; correction references the original; no update path | todo | |
| 5 | Gaps endpoint and period tracking (ended, unclosed periods per cadence) | api | Unit tests per gap type and period boundary | todo | |
| 6 | Summaries endpoint (total, privileged per vault/engine/system) | api | Unit tests | todo | |
| 7 | Compliance tab: Summaries, Snapshots (create with scope, close period with gap warning, downloads), Tree, Settings | frontend | `npm run check` clean; walk-through against the dev vaults | todo | |
| 8 | `main.c4` (compliance component), README (features, API, export warning next to the unauthenticated notice), `chronowarden/compliance/AGENTS.md`, CHANGELOG | [architecture](../../architecture/AGENTS.md) | Docs match the code; `check_agents_docs.py` passes | todo | |

## Validation

`uv run pytest`, black, ruff, `npm run check`, `check_agents_docs.py`, and the walk-through in the release spec.
