<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# audit: hash-chained audit log

## Purpose

Tamper-evident record of every change Chronowarden makes or sees (ADR-014): assignments, systems, owners,
removed/reappeared/purged secrets, and config changes that affect secrets. Kept forever.

## Files

- `chain.py`: `canonical_json`, `event_hash`, `verify_chain`, `GENESIS_HASH`. Pure functions, no I/O.
- `config_events.py`: `record_config_change(db, config)`, called in `app.py` `lifespan` after the DB opens.
- `revert.py`: `revert_event(db, event, source)`, `RevertError` (422 not revertible, 409 changed since or gone).
- `observe.py`: `observed_state(metadata)`, `record_observed_changes`, `record_config_applied`; called from
  `metadata.sync_secret_metadata`. The last state per secret is in `observed_state` (migration 6).
- `../database.py`: `append_audit_event`, `list_audit_events`, `iter_audit_events`, `get/set_audit_state`.
- `../api/audit.py`: `GET /audit/events`, `/audit/events.jsonl`, `/audit/verify`; `request_source(request)`.
- `../models/audit.py`: `AuditEvent` (before/after parsed), `AuditChainStatus`.

## Contracts

- Table `audit_events` (migration 5): `id` is 1, 2, 3, …; triggers abort any `UPDATE` or `DELETE`. Never add code
  that changes or removes events; corrections are new events.
- **Hash recipe** (also how anyone checks the JSONL export): `hash = sha256(json.dumps({id, timestamp, source,
  actor, event_type, subject, vault_name, engine_id, secret_path, before, after, prev_hash}, sort_keys=True,
  separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()`. `before`/`after` are the **stored JSON
  text**, not parsed objects. The first event's `prev_hash` is 64 zeros.
- `source`: `sync`, `config`, `ui` (requests with header `X-Chronowarden-Client: ui`, set by the frontend client) or
  `api`. `actor` stays null until authentication (0.9).
- Event types: `secret.system`, `secret.owners` (`{"owners": [{id, name}]}`), `secret.removed`, `secret.reappeared`,
  `secret.purged` (with the assignments that went), `system.created|updated|owners|deleted` (subject `system:<id>`),
  `owner.created|updated|deleted` (subject `owner:<id>`), `config.baseline|changed` (subject `config`). From sync:
  `secret.baseline` (first sight), `secret.metadata` (custom keys, values included), `secret.settings`,
  `secret.version` (rotation; values never read), `secret.config_applied` (Chronowarden's own severity/TTL write).
  `secret.confirmed` (rotation confirmed as applied, ADR-021), `secret.privileged` (revertible; written to the
  backend), `compliance.snapshot` (subject `snapshot:<id>`).
- Secret events are keyed by identity (`vault_name`, `engine_id`, `secret_path`), so history survives a rebuilt
  cache (ADR-017). Unchanged values record nothing.
- Config events store only expiry profiles and the severity cascade, never addresses or credentials.
- Revert (`POST /audit/events/{id}/revert`) restores `before` for `secret.system` / `secret.owners`, and revokes
  the confirmation of a `secret.confirmed` event (TTL recalculated), only while the event's `after` is still current; the new event's `after` carries `"reverts": <id>`. Everything else is 422:
  backend data isn't Chronowarden's to change (ADR-004), severity/TTL come from config (ADR-006).

## How to

- **Record a new kind of change**: call `db.append_audit_event(type, source, identity=… or subject=…, before=…,
  after=…)` right after the change, with a `<thing>.<what>` type; add it to the list above and test it in
  `tests/test_audit.py`.

## Gotchas

- `verify_chain` can't see the newest events being cut off; snapshots record the head hash for that (#94).
- The change and its event are separate commits; a crash between them loses the event, not the change.
- Other teams' metadata values are stored here and readable by anyone who reaches the API until 0.9; accepted and
  documented next to the README "unauthenticated" warning.
- Every write of Chronowarden's own keys must go through `record_config_applied`, or the next sync reports it as a
  backend change.

## Related ADRs

[ADR-014](../../.ai/adr/ADR-014-rotation-confirmation-and-audit-log.md),
[ADR-017](../../.ai/adr/ADR-017-sqlite-holds-assignments.md), [ADR-004](../../.ai/adr/ADR-004-metadata-only-access.md)

## Validate

`uv run pytest tests/test_audit.py tests/test_migrations.py`
