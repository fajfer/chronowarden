# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Evaluate alerts, keep their state and queue the webhooks to send (ADR-025)."""

import json
import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Optional

from chronowarden.alerting.alerts import (
    AUDIT_EVENT_ALERTS,
    SECRET_STATE_ALERTS,
    VAULT_STATE_ALERTS,
    Alert,
    audit_event_alert,
    period_ended_alert,
    secret_state_alerts,
    vault_unreachable_alert,
)
from chronowarden.alerting.payload import build_payload
from chronowarden.audit.chain import canonical_json
from chronowarden.compliance.periods import ended_periods
from chronowarden.metadata import parse_date
from chronowarden.timestamps import utc_timestamp

logger = logging.getLogger("uvicorn.error")

# Last audit event turned into event alerts; on first use it starts at the newest event, so an upgrade doesn't
# send the whole history
CHECKPOINT_KEY = "alerting.audit_checkpoint"

# One evaluation at a time per process: syncs of several vaults may finish together
_lock = threading.Lock()

Notification = dict[str, Any]


def _notification(alert_state: dict[str, Any], status: str) -> Notification:
    return {
        "fingerprint": alert_state["fingerprint"],
        "alertname": alert_state["alertname"],
        "labels": json.loads(alert_state["labels"]),
        "annotations": json.loads(alert_state["annotations"]),
        "owner_ids": json.loads(alert_state["owner_ids"]),
        "status": status,
        "starts_at": alert_state["starts_at"],
        "ends_at": alert_state["ends_at"],
    }


def _state(alert: Alert, status: str, starts_at: str, ends_at: Optional[str], last_sent_at: Optional[str]) -> dict:
    return {
        "fingerprint": alert.fingerprint,
        "alertname": alert.name,
        "labels": canonical_json(alert.all_labels),
        "annotations": canonical_json(alert.annotations),
        "owner_ids": canonical_json(list(alert.owner_ids)),
        "status": status,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "last_sent_at": last_sent_at,
    }


def reconcile(
    db: Any,
    current: list[Alert],
    names: tuple[str, ...],
    now: datetime,
    repeat_seconds: Optional[int],
    in_scope: Callable[[dict[str, Any]], bool] = lambda _state: True,
) -> list[Notification]:
    """
    Compare the state alerts that hold now with the stored ones and return what to send.

    A new alert fires; a firing one is sent again once `repeat_seconds` passed since it was last sent; a stored
    firing alert that no longer holds (and is `in_scope` of this evaluation) is sent once as resolved.
    """
    stored = db.get_alert_states(names)
    stamp = utc_timestamp(now)
    notifications: list[Notification] = []
    seen = set()
    for alert in current:
        seen.add(alert.fingerprint)
        previous = stored.get(alert.fingerprint)
        if previous is None or previous["status"] == "resolved":
            state = _state(alert, "firing", stamp, None, stamp)
            notifications.append(_notification(state, "firing"))
        else:
            last_sent = parse_date(previous["last_sent_at"] or "") or now
            due = repeat_seconds is not None and now - last_sent >= timedelta(seconds=repeat_seconds)
            state = _state(alert, "firing", previous["starts_at"], None, stamp if due else previous["last_sent_at"])
            if due:
                notifications.append(_notification(state, "firing"))
        db.save_alert_state(state)
    for fingerprint, previous in stored.items():
        if previous["status"] == "firing" and fingerprint not in seen and in_scope(previous):
            resolved = {**previous, "status": "resolved", "ends_at": stamp, "last_sent_at": stamp}
            db.save_alert_state(resolved)
            notifications.append(_notification(resolved, "resolved"))
    return notifications


def fire_once(db: Any, alert: Alert, now: datetime) -> list[Notification]:
    """An event alert, sent only the first time its fingerprint is seen."""
    if db.get_alert_states((alert.name,)).get(alert.fingerprint) is not None:
        return []
    starts = alert.starts_at or utc_timestamp(now)
    state = _state(alert, "resolved", starts, starts, utc_timestamp(now))
    db.save_alert_state(state)
    return [{**_notification(state, "firing"), "ends_at": starts}]


def _routes(db: Any, config: Any, owner_ids: list[str]) -> list[tuple[str, Optional[str], Optional[str]]]:
    """(receiver, owner route id, default route name) for each webhook the notification goes to."""
    targets: list[tuple[str, Optional[str], Optional[str]]] = []
    for owner_id in owner_ids:
        targets += [(f"owner:{owner_id}", route["id"], None) for route in db.list_notification_routes(owner_id)]
    if not targets:  # no owner, or owners without routes: the default routes (ADR-025)
        targets = [(f"default:{route.name}", None, route.name) for route in config.alerting.default_routes]
    return targets


def enqueue(db: Any, config: Any, notifications: list[Notification], now: datetime) -> int:
    """Queue a webhook per route for each notification whose alert is enabled; returns how many were queued."""
    queued = 0
    for notification in notifications:
        if notification["alertname"] not in config.alerting.events:
            continue
        for receiver, route_id, default_route in _routes(db, config, notification["owner_ids"]):
            payload = build_payload(notification, receiver, config.alerting.external_url)
            db.enqueue_delivery(
                utc_timestamp(now),
                receiver,
                route_id,
                default_route,
                notification["alertname"],
                notification["fingerprint"],
                json.dumps(payload, ensure_ascii=False),
            )
            queued += 1
    return queued


def _audit_event_notifications(db: Any, secrets: list[Any], now: datetime) -> list[Notification]:
    checkpoint_text = db.get_audit_state(CHECKPOINT_KEY)
    if checkpoint_text is None:
        db.set_audit_state(CHECKPOINT_KEY, str(db.latest_audit_event_id()))
        return []
    events = db.audit_events_after(int(checkpoint_text), tuple(AUDIT_EVENT_ALERTS))
    by_identity = {(s.vault_name, s.engine_id, s.secret_path): s for s in secrets}
    notifications: list[Notification] = []
    for event in events:
        notifications += fire_once(db, audit_event_alert(event, by_identity), now)
    if events:
        db.set_audit_state(CHECKPOINT_KEY, str(events[-1]["id"]))
    return notifications


def _period_notifications(db: Any, config: Any, now: datetime) -> list[Notification]:
    if not config.compliance.reporting.cadences:
        return []
    started = parse_date(db.first_audit_timestamp() or "") or now
    closed = {(s["cadence"], s["period"]) for s in db.list_snapshots() if s["cadence"]}
    notifications: list[Notification] = []
    for cadence in config.compliance.reporting.cadences:
        for period in ended_periods(cadence.period, started, now):
            if (period.cadence, period.id) not in closed:
                alert = period_ended_alert(period.cadence, period.id, utc_timestamp(period.end))
                notifications += fire_once(db, alert, now)
    return notifications


def evaluate_inventory(db: Any, config: Any, now: datetime) -> int:
    """
    After a sync: secret state alerts, event alerts from the audit log and ended reporting periods.

    Returns:
        The number of webhooks queued (0 when alerting is off).
    """
    if not config.alerting.enabled:
        return 0
    from chronowarden.api.secrets import enriched_secrets  # the API's status and confirmation logic

    with _lock:
        secrets = enriched_secrets(db, config)
        notifications = reconcile(
            db, secret_state_alerts(secrets), SECRET_STATE_ALERTS, now, config.alerting.repeat_seconds
        )
        notifications += _audit_event_notifications(db, secrets, now)
        notifications += _period_notifications(db, config, now)
        return enqueue(db, config, notifications, now)


def evaluate_vaults(
    db: Any, config: Any, unreachable: dict[str, tuple[str, Optional[str]]], checked: set[str], now: datetime
) -> int:
    """
    Vault health: `unreachable` maps vault → (reason, error) among the `checked` vaults; the others resolve.

    Returns:
        The number of webhooks queued.
    """
    if not config.alerting.enabled:
        return 0
    alerts = [vault_unreachable_alert(name, reason, error) for name, (reason, error) in unreachable.items()]
    with _lock:
        notifications = reconcile(
            db,
            alerts,
            VAULT_STATE_ALERTS,
            now,
            config.alerting.repeat_seconds,
            in_scope=lambda state: json.loads(state["labels"]).get("vault") in checked,
        )
        return enqueue(db, config, notifications, now)
