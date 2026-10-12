# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for alert rules, state and queuing (#99, ADR-025)."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from chronowarden.alerting.alerts import SECRET_STATE_ALERTS, Alert, secret_state_alerts
from chronowarden.alerting.engine import (
    enqueue,
    evaluate_inventory,
    evaluate_vaults,
    fire_once,
    reconcile,
)
from chronowarden.alerting.payload import ZERO_TIME, build_payload
from chronowarden.config import AppConfig
from chronowarden.database import Database, SecretMetadataCache
from chronowarden.models.secret import SecretMetadataResponse, SecretStatus
from chronowarden.models.system import OwnerRef

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
DAY = 86400


def _secret(path: str = "db", **fields: Any) -> SecretMetadataResponse:
    return SecretMetadataResponse(
        id=1, vault_name="prod", engine_id="apps", secret_path=path, full_path=f"prod/apps/{path}", **fields
    )


def _alert(path: str = "db", owners: tuple[str, ...] = ()) -> Alert:
    return Alert("SecretExpired", {"vault": "prod", "engine": "apps", "secret_path": path}, owner_ids=owners)


class TestRules:
    def test_state_alerts_by_status(self) -> None:
        alerts = secret_state_alerts(
            [
                _secret("ok", status=SecretStatus.OK),
                _secret("soon", status=SecretStatus.WARNING, ttl="2026-10-20", days_remaining=8),
                _secret("late", status=SecretStatus.EXPIRED, confirmation_overdue=True),
                _secret("gone", status=SecretStatus.EXPIRED, removed_at=NOW),
            ]
        )
        assert [(a.name, a.identity["secret_path"]) for a in alerts] == [
            ("SecretExpiringSoon", "soon"),
            ("SecretExpired", "late"),
            ("SecretRotationUnconfirmed", "late"),
        ]

    def test_fingerprint_ignores_owner_and_system_changes(self) -> None:
        before = secret_state_alerts([_secret(status=SecretStatus.EXPIRED)])[0]
        after = secret_state_alerts(
            [_secret(status=SecretStatus.EXPIRED, effective_owners=[OwnerRef(id="a", name="Alice")])]
        )[0]
        assert before.fingerprint == after.fingerprint and after.owner_ids == ("a",)
        assert after.all_labels["owners"] == "Alice"


class TestState:
    def test_fire_repeat_resolve(self, db: Database) -> None:
        def run(alerts: list[Alert], at: datetime) -> list[str]:
            return [n["status"] for n in reconcile(db, alerts, SECRET_STATE_ALERTS, at, DAY)]

        assert run([_alert()], NOW) == ["firing"]
        assert run([_alert()], NOW + timedelta(hours=23)) == [], "within the repeat interval"
        assert run([_alert()], NOW + timedelta(days=1)) == ["firing"], "repeated after a day"
        assert run([], NOW + timedelta(days=1, hours=1)) == ["resolved"]
        assert run([], NOW + timedelta(days=3)) == [], "resolved is sent once"
        assert run([_alert()], NOW + timedelta(days=4)) == ["firing"], "a new episode fires again"

    def test_no_repeat_when_off(self, db: Database) -> None:
        assert len(reconcile(db, [_alert()], SECRET_STATE_ALERTS, NOW, None)) == 1
        assert reconcile(db, [_alert()], SECRET_STATE_ALERTS, NOW + timedelta(days=30), None) == []

    def test_resolved_keeps_starts_and_owners(self, db: Database) -> None:
        reconcile(db, [_alert(owners=("alice",))], SECRET_STATE_ALERTS, NOW, DAY)
        [resolved] = reconcile(db, [], SECRET_STATE_ALERTS, NOW + timedelta(hours=2), DAY)
        assert resolved["owner_ids"] == ["alice"] and resolved["starts_at"].startswith("2026-10-12T12:00")
        assert resolved["ends_at"].startswith("2026-10-12T14:00")

    def test_event_alerts_fire_once(self, db: Database) -> None:
        alert = Alert("SecretRotated", {"vault": "prod", "event": "7"})
        assert len(fire_once(db, alert, NOW)) == 1
        assert fire_once(db, alert, NOW + timedelta(days=5)) == []

    def test_vault_alerts_resolve_only_for_checked_vaults(self, db: Database) -> None:
        config = AppConfig.model_validate({"alerting": {"default_routes": [{"name": "ops", "url": "https://h/x"}]}})
        assert evaluate_vaults(db, config, {"a": ("offline", "down"), "b": ("auth", "bad")}, {"a", "b"}, NOW) == 2
        assert evaluate_vaults(db, config, {}, {"a"}, NOW + timedelta(minutes=5)) == 1, "a is back; b wasn't checked"
        assert [s["labels"] for s in db.list_firing_alerts()] == [
            json.dumps({"alertname": "VaultUnreachable", "reason": "auth", "vault": "b"}, separators=(",", ":"))
        ]


class TestQueue:
    def _config(self, **alerting: Any) -> AppConfig:
        return AppConfig.model_validate(
            {"alerting": {"default_routes": [{"name": "ops", "url": "https://hooks.example.com/ops"}], **alerting}}
        )

    def test_owner_routes_then_default_routes(self, db: Database) -> None:
        db.create_owner("alice", "Alice", "alice@example.com")
        db.create_notification_route("r1", "alice", "webhook", "https://hooks.example.com/alice", "")
        db.create_owner("bob", "Bob", "bob@example.com")  # no routes
        notes = reconcile(
            db, [_alert("a", ("alice",)), _alert("b", ("bob",)), _alert("c")], SECRET_STATE_ALERTS, NOW, DAY
        )
        assert enqueue(db, self._config(), notes, NOW) == 3
        receivers = sorted((d["receiver"], d["route_id"], d["default_route"]) for d in db.list_deliveries())
        assert receivers == [("default:ops", None, "ops"), ("default:ops", None, "ops"), ("owner:alice", "r1", None)]

    def test_disabled_events_are_not_queued(self, db: Database) -> None:
        notes = reconcile(db, [_alert()], SECRET_STATE_ALERTS, NOW, DAY)
        assert enqueue(db, self._config(events=["SecretExpiringSoon"]), notes, NOW) == 0

    def test_inventory_evaluation_after_a_sync(self, db: Database) -> None:
        db.upsert_secret_metadata(
            SecretMetadataCache(vault_name="prod", engine_id="apps", secret_path="old", ttl="2020-01-01")
        )
        config = self._config()
        assert evaluate_inventory(db, config, NOW) == 1
        assert evaluate_inventory(db, config, NOW + timedelta(hours=1)) == 0, "already sent, not due again"
        assert evaluate_inventory(db, AppConfig.model_validate({"alerting": {"enabled": False}}), NOW) == 0

    def test_rotation_events_come_from_the_audit_log_after_the_checkpoint(self, db: Database) -> None:
        config = self._config()
        identity = ("prod", "apps", "db")
        db.append_audit_event("secret.version", "sync", identity=identity, before={"current": 1}, after={"current": 2})
        evaluate_inventory(db, config, NOW)
        assert db.list_deliveries() == [], "history before the first evaluation isn't sent"
        db.append_audit_event("secret.version", "sync", identity=identity, before={"current": 2}, after={"current": 3})
        assert evaluate_inventory(db, config, NOW) == 1
        payload = json.loads(db.due_deliveries("9999")[0]["payload"])
        assert payload["alerts"][0]["labels"]["alertname"] == "SecretRotated"
        assert "version 3" in payload["alerts"][0]["annotations"]["summary"]
        assert evaluate_inventory(db, config, NOW) == 0


def test_payload_is_alertmanager_shaped() -> None:
    notification = {
        "fingerprint": "f" * 64,
        "alertname": "SecretExpired",
        "labels": {"alertname": "SecretExpired", "vault": "prod"},
        "annotations": {"summary": "s"},
        "status": "firing",
        "starts_at": "2026-10-12T12:00:00.000000Z",
        "ends_at": None,
    }
    payload = build_payload(notification, "owner:alice", "https://cw.example.com/")
    assert payload["version"] == "4" and payload["receiver"] == "owner:alice" and payload["status"] == "firing"
    assert payload["externalURL"] == "https://cw.example.com"
    [alert] = payload["alerts"]
    assert alert["endsAt"] == ZERO_TIME and alert["fingerprint"] == "f" * 64
    assert alert["generatorURL"] == "https://cw.example.com/compliance"


@pytest.mark.parametrize("status", ["resolved"])
def test_resolved_payload_has_an_end(status: str) -> None:
    payload = build_payload(
        {
            "fingerprint": "x",
            "alertname": "A",
            "labels": {},
            "annotations": {},
            "status": status,
            "starts_at": "s",
            "ends_at": "e",
        },
        "default:ops",
        None,
    )
    assert payload["alerts"][0]["endsAt"] == "e" and payload["externalURL"] == ""


def test_alerts_and_deliveries_api(db: Database) -> None:
    from unittest.mock import patch

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from chronowarden.api.alerts import router

    config = AppConfig.model_validate({"alerting": {"default_routes": [{"name": "ops", "url": "https://h/x"}]}})
    enqueue(db, config, reconcile(db, [_alert()], SECRET_STATE_ALERTS, NOW, DAY), NOW)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with patch("chronowarden.api.alerts._get_db", return_value=db):
        client = TestClient(app)
        [alert] = client.get("/api/v1/alerts").json()
        [delivery] = client.get("/api/v1/webhooks/deliveries").json()
    assert alert["alertname"] == "SecretExpired" and alert["labels"]["secret_path"] == "db"
    assert (delivery["receiver"], delivery["status"], delivery["attempts"]) == ("default:ops", "pending", 0)
    assert "payload" not in delivery and "https://h/x" not in json.dumps(delivery)
