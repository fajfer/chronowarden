# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for webhook signing and delivery against a local receiver (#99, ADR-025)."""

import base64
import hashlib
import hmac
import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from chronowarden.alerting.delivery import deliver_due
from chronowarden.alerting.signing import generate_secret
from chronowarden.config import AppConfig
from chronowarden.database import Database

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


class Receiver:
    """A local HTTP server that records requests and answers with the queued status codes (then 200)."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.answers: list[int] = []
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 (http.server's naming)
                body = self.rfile.read(int(self.headers["Content-Length"]))
                receiver.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                code = receiver.answers.pop(0) if receiver.answers else 200
                self.send_response(code)
                if code in (301, 302, 307):
                    self.send_header("Location", "http://127.0.0.1:1/elsewhere")
                self.end_headers()

            def log_message(self, *args: Any) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/hook/secret-token"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def receiver() -> Iterator[Receiver]:
    r = Receiver()
    yield r
    r.server.shutdown()


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
