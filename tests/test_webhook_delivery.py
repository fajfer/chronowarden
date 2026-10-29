# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for webhook signing and delivery against a local receiver (#99, ADR-025)."""

import asyncio
import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from chronowarden.alerting.delivery import deliver_due, post
from chronowarden.alerting.signing import generate_secret
from chronowarden.config import AppConfig
from chronowarden.database import Database
from chronowarden.scheduler import sync_and_alert
from tests.conftest import Receiver

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


def _queue(db: Database, route_id: str | None = None, default_route: str | None = None) -> None:
    db.enqueue_delivery(
        "2026-10-12T11:00:00.000000Z", "r", route_id, default_route, "SecretExpired", "fp", '{"version":"4"}'
    )


def _verify(secret: str, headers: dict[str, str], body: bytes) -> bool:
    """Standard Webhooks verification, written from the spec rather than with Chronowarden's code."""
    key = base64.b64decode(secret.split("_", 1)[1])
    signed = f"{headers['webhook-id']}.{headers['webhook-timestamp']}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return any(sig == f"v1,{expected}" for sig in headers["webhook-signature"].split(" "))


def test_signed_delivery_to_an_owner_route(db: Database, receiver: Receiver) -> None:
    db.create_owner("alice", "Alice", "a@example.com")
    db.create_notification_route("r1", "alice", "webhook", receiver.url, "")
    secret = generate_secret()
    db.set_route_signing_secret("r1", secret)
    _queue(db, route_id="r1")
    assert deliver_due(db, AppConfig(), NOW) == 1
    [request] = receiver.requests
    assert request["body"] == b'{"version":"4"}' and request["headers"]["Content-Type"] == "application/json"
    assert _verify(secret, request["headers"], request["body"])
    assert request["headers"]["webhook-timestamp"] == str(int(NOW.timestamp()))
    [delivery] = db.list_deliveries()
    assert (delivery["status"], delivery["attempts"], delivery["last_status_code"]) == ("delivered", 1, 200)


def test_unsigned_routes_send_no_signature(db: Database, receiver: Receiver) -> None:
    config = AppConfig.model_validate({"alerting": {"default_routes": [{"name": "ops", "url": receiver.url}]}})
    _queue(db, default_route="ops")
    deliver_due(db, config, NOW)
    assert "webhook-signature" not in receiver.requests[0]["headers"]
    assert receiver.requests[0]["headers"]["webhook-id"].startswith("msg_")


def test_retries_back_off_then_give_up(db: Database, receiver: Receiver) -> None:
    config = AppConfig.model_validate(
        {"alerting": {"max_attempts": 3, "default_routes": [{"name": "ops", "url": receiver.url}]}}
    )
    receiver.answers = [503, 429, 500]
    _queue(db, default_route="ops")
    deliver_due(db, config, NOW)
    [delivery] = db.list_deliveries()
    assert (delivery["status"], delivery["next_attempt_at"][:16]) == ("pending", "2026-10-12T12:01")
    assert deliver_due(db, config, NOW + timedelta(seconds=30)) == 0, "not due yet"
    deliver_due(db, config, NOW + timedelta(minutes=1))
    assert db.list_deliveries()[0]["next_attempt_at"][:16] == "2026-10-12T12:06", "5 minutes after the 2nd attempt"
    deliver_due(db, config, NOW + timedelta(minutes=6))
    [delivery] = db.list_deliveries()
    assert (delivery["status"], delivery["attempts"], delivery["last_error"]) == ("failed", 3, "HTTP 500")


def test_client_errors_and_redirects_are_not_retried(db: Database, receiver: Receiver) -> None:
    config = AppConfig.model_validate({"alerting": {"default_routes": [{"name": "ops", "url": receiver.url}]}})
    receiver.answers = [404, 302]
    _queue(db, default_route="ops")
    _queue(db, default_route="ops")
    deliver_due(db, config, NOW)
    statuses = sorted((d["status"], d["last_error"]) for d in db.list_deliveries())
    assert statuses == [("failed", "HTTP 302: redirects aren't followed"), ("failed", "HTTP 404")]
    assert len(receiver.requests) == 2, "the redirect wasn't followed"


def test_unreachable_receiver_is_retried_without_logging_the_url(
    db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    config = AppConfig.model_validate(
        {"alerting": {"default_routes": [{"name": "ops", "url": "http://127.0.0.1:1/hook/secret-token"}]}}
    )
    _queue(db, default_route="ops")
    deliver_due(db, config, NOW)
    [delivery] = db.list_deliveries()
    assert delivery["status"] == "pending" and delivery["last_error"] == "ConnectionError"
    assert "secret-token" not in caplog.text and "secret-token" not in json.dumps(delivery)


def test_deleted_route_fails_the_delivery(db: Database) -> None:
    _queue(db, route_id="gone")
    deliver_due(db, AppConfig(), NOW)
    [delivery] = db.list_deliveries()
    assert (delivery["status"], delivery["last_error"]) == ("failed", "the route was deleted")


class OneSecretVault:
    """A connected backend with one secret last rotated in 2020 (expired under the default 365d profile)."""

    last_error_kind = None
    last_error = None

    def is_connected(self) -> bool:
        return True

    def discover_engines(self) -> list[dict[str, Any]]:
        return [{"path": "apps", "type": "kv", "options": {"version": "2"}}]

    def list_secrets(self, path: str, mount_point: str | None = None, strict: bool = False) -> list[str]:
        return ["db"] if path == "" else []

    def get_secret_metadata(self, path: str, mount_point: str | None = None) -> dict[str, Any]:
        return {
            "custom_metadata": {},
            "updated_time": "2020-01-01T00:00:00Z",
            "current_version": 1,
            "versions": {"1": {"created_time": "2020-01-01T00:00:00Z"}},
        }

    def write_secret_metadata(self, path: str, fields: dict[str, str], mount_point: str | None = None) -> bool:
        return True


class OneProviderManager:
    def __init__(self, vault: Any) -> None:
        self.vault = vault
        self._locks: dict[str, Any] = {}

    @property
    def vault_names(self) -> list[str]:
        return ["prod"]

    def get(self, name: str) -> Any:
        return self.vault if name == "prod" else None

    def sync_lock(self, name: str) -> Any:
        return self._locks.setdefault(name, asyncio.Lock())


def test_a_sync_of_an_expired_secret_sends_one_webhook(db: Database, receiver: Receiver) -> None:
    """Spec task 6: sync → evaluate → queue → deliver; a second sync within repeat_interval sends nothing."""
    config = AppConfig.model_validate(
        {
            "vaults": [{"name": "prod", "address": "http://v:8200", "token": "t"}],
            "alerting": {"default_routes": [{"name": "ops", "url": receiver.url}]},
        }
    )
    manager = OneProviderManager(OneSecretVault())
    asyncio.run(sync_and_alert(manager, config, db))
    deliver_due(db, config)
    assert [json.loads(r["body"])["alerts"][0]["labels"]["alertname"] for r in receiver.requests] == ["SecretExpired"]
    asyncio.run(sync_and_alert(manager, config, db))
    deliver_due(db, config)
    assert len(receiver.requests) == 1


def test_an_unreachable_vault_alerts_the_default_routes(db: Database, receiver: Receiver) -> None:
    vault = OneSecretVault()
    vault.is_connected = lambda: False  # type: ignore[method-assign]
    vault.last_error_kind = "offline"  # type: ignore[assignment]
    vault.last_error = "Vault at http://v:8200 appears to be offline"  # type: ignore[assignment]
    config = AppConfig.model_validate({"alerting": {"default_routes": [{"name": "ops", "url": receiver.url}]}})
    asyncio.run(sync_and_alert(OneProviderManager(vault), config, db))
    deliver_due(db, config)
    [request] = receiver.requests
    alert = json.loads(request["body"])["alerts"][0]
    assert alert["labels"] == {"alertname": "VaultUnreachable", "vault": "prod", "reason": "offline"}


@pytest.mark.parametrize("status_code", [200, 302, 500])
def test_the_response_body_is_never_read(status_code: int) -> None:
    """Regression: a receiver can't make the server buffer a huge or endless response body."""
    response = MagicMock(status_code=status_code, ok=status_code < 400)
    response.__enter__.return_value = response
    type(response).content = PropertyMock(side_effect=AssertionError("the body was read"))
    type(response).text = PropertyMock(side_effect=AssertionError("the body was read"))
    with patch("chronowarden.alerting.delivery.requests.post", return_value=response) as send:
        status, _ = post("https://hooks.example.com/x", b"{}", "msg_1", None, datetime.now(tz=UTC))
    assert status == status_code
    assert send.call_args.kwargs["stream"] is True
    response.__exit__.assert_called_once()
