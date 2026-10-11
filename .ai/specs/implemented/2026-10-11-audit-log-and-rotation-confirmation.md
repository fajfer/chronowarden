<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Audit log, change history and rotation confirmation

- **Status:** implemented
- **Date:** 2026-10-11
- **Issue:** #24 (retitled "Audit log, change history and rotation confirmation"), #18

## Goal

Every change Chronowarden sees on a secret is recorded in a tamper-evident audit log with date, before/after and
who, so its history can be read and, where allowed, reverted. Rotations that need a human or automated hand-over are
confirmed in Chronowarden, and the next rotation date follows the confirmed date.

## Non-goals

- Authenticated actors (0.9; until then the source only: "sync", "config", "ui", "api"; UI actions are anonymous).
- Reverting other teams' metadata keys or Vault settings (ADR-004).
- Alerts on unconfirmed rotations (0.8, ADR-022): 0.7 records and shows them.

## Design

**Audit log.** Append-only table `audit_events` (id, timestamp, actor, source = `sync` | `ui` | `api` | `config`,
event type, secret identity `vault_name` + `engine_id` + `secret_path` where applicable, before JSON, after JSON,
`prev_hash`, `hash`). `hash` = SHA-256 over the canonical event including `prev_hash`; a verifier walks the chain.
Never updated or deleted; kept forever. JSONL export.

**Observing changes.** Sync keeps the last-seen state of each secret in a table keyed by identity: full
`custom_metadata`, `delete_version_after`, `max_versions`, `cas_required`, current version and its `created_time`.
Differences become events (actor "sync"): custom metadata keys added, changed or removed (keys and values), settings
changed, new versions (rotations; values never read). On first sight (including the first 0.7 sync of every
existing secret) a secret gets one "baseline" event, not a
diff. A removed secret that reappears gets a "reappeared" event; a purge writes a "purged" event.
Config changes that affect secrets (severity, confirmation cascade) are recorded at startup/reload.

**Revert.** `POST /api/v1/audit/events/{id}/revert` creates a new event restoring the previous value. Allowed for:
system and owner assignments, `chronowarden_privileged` (written to Vault with read-merge-write), confirmations.
Refused (422) for other custom metadata keys, Vault settings, severity and TTL.

**Rotation confirmation.** `confirmation_required` cascade in config (vault → engine → secret, like severity; default
`false`); `confirmation_grace` per expiry profile with a global default. Table `rotation_confirmations` (identity,
version confirmed, applied_at, confirmed_by, recorded_at). A secret needs confirmation when it is required and its
newest version is newer than the last confirmation; it then shows **awaiting confirmation** (badge, gap) while
counting as rotated. Confirming: UI dialog in the secret detail view (applied date, which may be in the past;
anonymous before 0.9) or `POST /api/v1/secrets/{id}/confirmations` (`{applied_at, confirmed_by}`). `applied_at` must
lie between the newest version's `created_time` and now (422 otherwise); a confirmation covers the newest version
only. Next rotation =
max(Vault `updated_time`, applied_at) + rotation period; `chronowarden_ttl` written to Vault follows it. Confirmations
stay in the database only. Corrections go through revert: reverting a confirmation returns the secret to awaiting
confirmation and recalculates the next rotation from `updated_time`.

**UI.** Compliance tab → Audit log (filters: secret, vault, system, event type, date; JSONL download; chain verify
status). Secret detail → History (events for that secret, Revert where allowed) and Confirm rotation.

## Scope

`chronowarden/database.py`, `chronowarden/metadata.py`, `chronowarden/config.py`, `config.example.yaml`,
`chronowarden/models/`, `chronowarden/api/`, new `chronowarden/audit/`, `frontend/`, `architecture/main.c4`,
`README.md`, `CHANGELOG.md`.

## Load

- [root AGENTS.md](../../../AGENTS.md)
- [core](../../../chronowarden/AGENTS.md), [models](../../../chronowarden/models/AGENTS.md),
  [api](../../../chronowarden/api/AGENTS.md), [integrations](../../../chronowarden/integrations/AGENTS.md),
  [frontend](../../../frontend/AGENTS.md)
- [ADR-004](../../adr/ADR-004-metadata-only-access.md), [ADR-006](../../adr/ADR-006-config-source-of-truth.md),
  [ADR-014](../../adr/ADR-014-rotation-confirmation-and-audit-log.md), [ADR-021](../../adr/ADR-021-rotation-handover.md),
  [ADR-022](../../adr/ADR-022-webhooks-and-optional-metrics.md),
  [ADR-017](../../adr/ADR-017-sqlite-holds-assignments.md)

## ADRs affected

ADR-014 accepted; ADR-021 new.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `audit_events` with hash chain, append-only writer, chain verifier, JSONL export, `GET /api/v1/audit/events` | models, api | Tests: chain verifies; tampering a row is detected; no update/delete path | done | 1b35320 |
| 2 | Observed state table and sync diffing into events (custom metadata, settings, versions, baseline) | core, integrations | Tests against fixtures; live check on both dev vaults: change a key in Vault → event with before/after | done | 845abcb |
| 3 | Move #61 assignment logging and privileged changes (privileged: recorded by the compliance spec, which adds the flag) into events; config-change events at startup | core, api | Tests | done | 1b35320 |
| 4 | Revert endpoint with the allowed/refused rules | api | Tests for each allowed and refused type | done | ac9c643 |
| 5 | Confirmation cascade + grace config, `rotation_confirmations`, awaiting-confirmation status, TTL from max(updated_time, applied_at), confirm endpoint | core, models, api | Tests: required/not required via cascade, historic date, TTL recalculation, revert of a confirmation | done | f2639d3 |
| 6 | UI: Audit log page, secret History with Revert, Confirm rotation dialog, awaiting-confirmation badge | frontend | `npm run check` clean; walk-through against the dev vaults | done | 2da6b08 |
| 7 | ADR-014 accepted text, ADR-021; `main.c4`; README; CHANGELOG; `chronowarden/audit/AGENTS.md` | [.ai/adr](../../adr/README.md) | Docs match the code | done | 2da6b08 |

## Validation

`uv run pytest`, black, ruff, `npm run check`, `check_agents_docs.py`, and the walk-through in the release spec.
