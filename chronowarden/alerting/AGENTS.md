<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# alerting: webhook alerts

## Purpose

Chronowarden's own alerting (#99, [ADR-022](../../.ai/adr/ADR-022-webhooks-and-optional-metrics.md),
[ADR-025](../../.ai/adr/ADR-025-alert-lifecycle-and-webhook-delivery.md)): Alertmanager-compatible webhooks to the
owners' routes and to `alerting.default_routes`, with state, repeats, retries and Standard Webhooks signing.

## Files

- `alerts.py`: `Alert` (name, `identity` labels → fingerprint, other labels, annotations, `owner_ids`) and the
  rules: `secret_state_alerts`, `vault_unreachable_alert`, `audit_event_alert` (`AUDIT_EVENT_ALERTS`),
  `period_ended_alert`. Pure functions.
- `engine.py`: `reconcile` (fire, repeat after `repeat_interval`, resolve once), `fire_once` (event alerts),
  `enqueue` (owner routes, else default routes; `alerting.events` filter), `evaluate_inventory` (after syncs,
  confirmations, snapshots), `evaluate_vaults` (scheduler and one-shot).
- `payload.py`: `build_payload` (Alertmanager webhook v4, one alert per body). `signing.py`: `generate_secret`,
  `signature_headers`. `delivery.py`: `post`, `send`, `deliver_due`, `DeliveryWorker` (in `lifespan`, every 15 s).
- DB (`../database.py`, migration 10): `alert_state`, `webhook_deliveries`, `notification_routes.signing_secret`.

## Contracts

- Fingerprints hash the name and `identity` only (vault/engine/path, vault, cadence/period, snapshot, audit event
  id), so owner, system or severity changes don't refire an alert.
- Event alerts read the audit log after `alerting.audit_checkpoint` (audit state); the first evaluation only sets
  the checkpoint, so an upgrade doesn't send history. Each event alert is stored once in `alert_state`.
- Deliveries store the payload and the route id or default-route name, never the URL; `_target` looks it up at send
  time. Error texts and logs never contain a URL (webhook URLs carry tokens); `logging_config` keeps urllib3's
  request lines out of DEBUG.
- Retries: network errors, 429, 5xx; backoff `BACKOFF_SECONDS`; other answers and redirects fail at once.
- Route listings return `signed`, never `signing_secret`; only `POST .../signing` returns a new secret.

## How to

- **New alert**: add its name to `ALERT_NAMES`/`AlertName` in `../config.py`, a builder in `alerts.py`, wire it in
  `engine.py` (state: add to the `*_STATE_ALERTS` tuple and `reconcile`; event: `fire_once`), its row in
  `docs/guides/webhooks.md`, and tests in `tests/test_alerting.py`.

## Gotchas

- Evaluation is serialised per process (`engine._lock`); a server and a CronJob on one database could both send.
  The docs pair a CronJob with `polling_interval: off`, and the server still delivers what the CronJob queued.
- Alerts follow the sync schedule: an expiry is noticed at the next sync after it happens.

## Validate

`uv run pytest tests/test_alerting.py tests/test_webhook_delivery.py tests/test_owners.py`
