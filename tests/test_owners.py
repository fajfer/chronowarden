# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for owner management functionality."""

import json
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.api.owners import mask_address, router
from chronowarden.config import AppConfig
from chronowarden.database import Database
from tests.conftest import Receiver


class TestOwnerDatabase:
    """Test owner-related database operations."""

    def setup_method(self) -> None:
        """Set up test database."""
        self.db = Database(db_path=Path(":memory:"))
        self.db.connect()

    def teardown_method(self) -> None:
        """Clean up test database."""
        self.db.close()

    def test_create_owner(self) -> None:
        """Test creating an owner."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        owner = self.db.get_owner("owner-1")
        assert owner is not None
        assert owner["name"] == "Alice"
        assert owner["email"] == "alice@example.com"
        assert owner["created_at"] is not None

    def test_list_owners(self) -> None:
        """Test listing owners."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_owner("owner-2", "Bob", "bob@example.com")
        owners = self.db.list_owners()
        assert len(owners) == 2

    def test_update_owner(self) -> None:
        """Test updating an owner."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.update_owner("owner-1", name="Alice Updated")
        owner = self.db.get_owner("owner-1")
        assert owner is not None
        assert owner["name"] == "Alice Updated"
        assert owner["email"] == "alice@example.com"

    def test_delete_owner(self) -> None:
        """Test deleting an owner."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.delete_owner("owner-1")
        owner = self.db.get_owner("owner-1")
        assert owner is None

    def test_create_notification_route(self) -> None:
        """Test creating a notification route."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_notification_route(
            "route-1", "owner-1", "webhook", "https://hooks.example.com/alice", "Test: {secret_name}"
        )
        routes = self.db.list_notification_routes("owner-1")
        assert len(routes) == 1
        assert routes[0]["type"] == "webhook"
        assert routes[0]["address"] == "https://hooks.example.com/alice"
        assert routes[0]["message_template"] == "Test: {secret_name}"

    def test_delete_notification_route(self) -> None:
        """Test deleting a notification route."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_notification_route("route-1", "owner-1", "webhook", "https://hooks.example.com/alice", "Test")
        self.db.delete_notification_route("route-1")
        routes = self.db.list_notification_routes("owner-1")
        assert len(routes) == 0

    def test_delete_owner_cascades_routes(self) -> None:
        """Test that deleting an owner also deletes routes."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_notification_route("route-1", "owner-1", "webhook", "https://hooks.example.com/alice", "Test")
        self.db.delete_owner("owner-1")
        routes = self.db.list_notification_routes("owner-1")
        assert len(routes) == 0

    def test_get_nonexistent_owner(self) -> None:
        """Test getting a nonexistent owner returns None."""
        owner = self.db.get_owner("nonexistent")
        assert owner is None

    def test_update_owner_both_fields(self) -> None:
        """Test updating both name and email at once."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.update_owner("owner-1", name="Alice Updated", email="newalice@example.com")
        owner = self.db.get_owner("owner-1")
        assert owner is not None
        assert owner["name"] == "Alice Updated"
        assert owner["email"] == "newalice@example.com"

    def test_update_owner_no_fields(self) -> None:
        """Test updating with no fields is a no-op."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.update_owner("owner-1")
        owner = self.db.get_owner("owner-1")
        assert owner is not None
        assert owner["name"] == "Alice"
        assert owner["email"] == "alice@example.com"

    def test_update_owner_email_only(self) -> None:
        """Test updating only the email field."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.update_owner("owner-1", email="new@example.com")
        owner = self.db.get_owner("owner-1")
        assert owner is not None
        assert owner["name"] == "Alice"
        assert owner["email"] == "new@example.com"

    def test_create_duplicate_owner(self) -> None:
        """Test creating a duplicate owner raises an integrity error."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        try:
            self.db.create_owner("owner-1", "Bob", "bob@example.com")
            assert False, "Expected IntegrityError for duplicate owner"
        except sqlite3.IntegrityError:
            pass

    def test_multiple_notification_routes(self) -> None:
        """Test creating multiple notification routes for the same owner."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_notification_route(
            "route-1", "owner-1", "webhook", "https://hooks.example.com/alice", "Template 1"
        )
        self.db.create_notification_route("route-2", "owner-1", "webhook", "https://hooks.example.com", "Template 2")
        routes = self.db.list_notification_routes("owner-1")
        assert len(routes) == 2
        assert {r["address"] for r in routes} == {"https://hooks.example.com/alice", "https://hooks.example.com"}

    def test_email_route_rejected_by_schema(self) -> None:
        """Email routes were removed in 0.7 (ADR-022): the table only accepts webhooks."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        try:
            self.db.create_notification_route("route-1", "owner-1", "email", "alice@example.com", "Test")
            assert False, "Expected IntegrityError for an email route"
        except sqlite3.IntegrityError:
            pass

    def test_list_notification_routes_empty(self) -> None:
        """Test listing routes for an owner with no routes returns empty list."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        routes = self.db.list_notification_routes("owner-1")
        assert routes == []

    def test_list_notification_routes_nonexistent_owner(self) -> None:
        """Test listing routes for a nonexistent owner returns empty list."""
        routes = self.db.list_notification_routes("nonexistent")
        assert routes == []

    def test_list_owners_empty(self) -> None:
        """Test listing owners when none exist returns empty list."""
        owners = self.db.list_owners()
        assert owners == []

    def test_delete_nonexistent_owner(self) -> None:
        """Test deleting a nonexistent owner does not raise."""
        self.db.delete_owner("nonexistent")

    def test_delete_nonexistent_notification_route(self) -> None:
        """Test deleting a nonexistent route does not raise."""
        self.db.delete_notification_route("nonexistent")


class TestOwnersAPI:
    """Test owner API endpoints using FastAPI TestClient."""

    def setup_method(self) -> None:
        """Set up test database and app."""
        self.db = Database(db_path=Path(":memory:"))
        self.db.connect()

    def teardown_method(self) -> None:
        """Clean up test database."""
        self.db.close()

    def _build_client(self) -> TestClient:
        """Build a TestClient for the owners API router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return TestClient(app)

    def test_list_owners_empty(self) -> None:
        """Test listing owners when none exist."""
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.get("/api/v1/owners/")
            assert response.status_code == 200
            assert response.json() == []

    def test_create_owner(self) -> None:
        """Test creating an owner via API."""
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.post("/api/v1/owners/", json={"name": "Alice", "email": "alice@example.com"})
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Alice"
            assert data["email"] == "alice@example.com"
            assert "id" in data
            assert data["notification_routes"] == []

    def test_idp_group_is_set_cleared_and_audited(self) -> None:
        """Members of an owner's IdP group act for it (ADR-026); an empty string clears the group."""
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            created = client.post(
                "/api/v1/owners/", json={"name": "Payments", "email": "pay@example.com", "idp_group": "team-pay"}
            ).json()
            assert created["idp_group"] == "team-pay"
            updated = client.put(f"/api/v1/owners/{created['id']}", json={"idp_group": ""}).json()
            assert updated["idp_group"] is None
        event = self.db.list_audit_events(event_type="owner.updated")[0]
        assert (json.loads(event["before"])["idp_group"], json.loads(event["after"])["idp_group"]) == ("team-pay", None)

    def test_get_owner(self) -> None:
        """Test getting an owner by ID via API."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.get("/api/v1/owners/owner-1")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Alice"
            assert data["email"] == "alice@example.com"

    def test_get_owner_not_found(self) -> None:
        """Test getting a nonexistent owner returns 404."""
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.get("/api/v1/owners/nonexistent")
            assert response.status_code == 404

    def test_update_owner(self) -> None:
        """Test updating an owner via API."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.put("/api/v1/owners/owner-1", json={"name": "Alice Updated", "email": "new@example.com"})
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Alice Updated"
            assert data["email"] == "new@example.com"

    def test_update_owner_not_found(self) -> None:
        """Test updating a nonexistent owner returns 404."""
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.put("/api/v1/owners/nonexistent", json={"name": "Ghost"})
            assert response.status_code == 404

    def test_delete_owner(self) -> None:
        """Test deleting an owner via API."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.delete("/api/v1/owners/owner-1")
            assert response.status_code == 204
            assert self.db.get_owner("owner-1") is None

    def test_delete_owner_not_found(self) -> None:
        """Test deleting a nonexistent owner returns 404."""
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.delete("/api/v1/owners/nonexistent")
            assert response.status_code == 404

    def test_add_notification_route(self) -> None:
        """Test adding a notification route via API."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.post(
                "/api/v1/owners/owner-1/routes",
                json={"type": "webhook", "address": "https://hooks.example.com/alice", "message_template": "Test"},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["type"] == "webhook"
            assert data["address"] == "https://hooks.example.com/…"
            assert data["owner_id"] == "owner-1"
            assert self.db.list_notification_routes("owner-1")[0]["address"] == "https://hooks.example.com/alice"

    def test_add_route_owner_not_found(self) -> None:
        """Test adding a route to a nonexistent owner returns 404."""
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.post(
                "/api/v1/owners/nonexistent/routes",
                json={"type": "webhook", "address": "https://hooks.example.com"},
            )
            assert response.status_code == 404

    def test_add_email_route_rejected(self) -> None:
        """The API refuses email routes with 422 (removed in 0.7, ADR-022)."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.post(
                "/api/v1/owners/owner-1/routes", json={"type": "email", "address": "alice@example.com"}
            )
            assert response.status_code == 422
            assert self.db.list_notification_routes("owner-1") == []

    def test_delete_notification_route(self) -> None:
        """Test deleting a notification route via API."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_notification_route("route-1", "owner-1", "webhook", "https://hooks.example.com/alice", "Test")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.delete("/api/v1/owners/owner-1/routes/route-1")
            assert response.status_code == 204
            routes = self.db.list_notification_routes("owner-1")
            assert len(routes) == 0

    def test_delete_route_owner_not_found(self) -> None:
        """Test deleting a route from a nonexistent owner returns 404."""
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.delete("/api/v1/owners/nonexistent/routes/route-1")
            assert response.status_code == 404

    def test_get_owner_with_routes(self) -> None:
        """Test that getting an owner includes their notification routes."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_notification_route(
            "route-1", "owner-1", "webhook", "https://hooks.example.com/alice", "Template"
        )
        self.db.create_notification_route("route-2", "owner-1", "webhook", "https://hooks.example.com", "Template")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.get("/api/v1/owners/owner-1")
            assert response.status_code == 200
            data = response.json()
            assert len(data["notification_routes"]) == 2

    def test_list_owners_with_data(self) -> None:
        """Test listing multiple owners via API."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_owner("owner-2", "Bob", "bob@example.com")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.get("/api/v1/owners/")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    def test_delete_route_of_another_owner_is_404(self) -> None:
        """Regression (0.7.1): deleting checked only the owner, so any owner's URL could delete any route."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_owner("owner-2", "Bob", "bob@example.com")
        self.db.create_notification_route("route-b", "owner-2", "webhook", "https://hooks.example.com/bob", "Test")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            assert client.delete("/api/v1/owners/owner-1/routes/route-b").status_code == 404
            assert client.delete("/api/v1/owners/owner-1/routes/unknown").status_code == 404
        assert [r["id"] for r in self.db.list_notification_routes("owner-2")] == ["route-b"]

    def test_test_route_owner_not_found(self) -> None:
        """Test the test-route endpoint returns 404 for missing owner."""
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.post("/api/v1/owners/nonexistent/test-route/route-1")
            assert response.status_code == 404

    def test_test_route_route_not_found(self) -> None:
        """Test the test-route endpoint returns 404 for missing route."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.post("/api/v1/owners/owner-1/test-route/nonexistent")
            assert response.status_code == 404


@pytest.mark.parametrize(
    "address,masked",
    [
        ("https://hooks.slack.com/services/T0/B0/secret", "https://hooks.slack.com/…"),
        ("https://user:pass@hooks.example.com:8443/x?token=t", "https://hooks.example.com:8443/…"),
        ("not a url", "…"),
    ],
)
def test_mask_address(address: str, masked: str) -> None:
    assert mask_address(address) == masked


def test_routes_are_masked_and_audited(db: Database) -> None:
    """Regression (audit follow-ups): webhook URLs carry tokens, so no response or audit event holds one."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    db.create_owner("alice", "Alice", "alice@example.com")
    token_url = "https://hooks.slack.com/services/T0/B0/secret-token"
    with patch("chronowarden.api.owners._get_db", return_value=db):
        client = TestClient(app)
        route = client.post("/api/v1/owners/alice/routes", json={"type": "webhook", "address": token_url}).json()
        responses = [client.get("/api/v1/owners/").text, client.get("/api/v1/owners/alice").text]
        assert client.delete(f"/api/v1/owners/alice/routes/{route['id']}").status_code == 204
    events = db.list_audit_events(subject="owner:alice")
    assert [e["event_type"] for e in events] == ["owner.route_deleted", "owner.route_added"]
    expected = {"id": route["id"], "type": "webhook", "address": "https://hooks.slack.com/…"}
    assert json.loads(events[1]["after"]) == expected and json.loads(events[0]["before"]) == expected
    assert all("secret-token" not in text for text in [*responses, *(json.dumps(e) for e in events)])


class TestRouteSigningAndTestSend:
    """Signing secrets and real test sends (#99, ADR-025)."""

    @pytest.fixture
    def client(self, db: Database, receiver: Receiver) -> Iterator[TestClient]:
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        db.create_owner("alice", "Alice", "alice@example.com")
        db.create_notification_route("r1", "alice", "webhook", receiver.url, "")
        with (
            patch("chronowarden.api.owners._get_db", return_value=db),
            patch("chronowarden.app.app_config", AppConfig()),
        ):
            yield TestClient(app)

    def test_test_send_reaches_the_receiver_without_leaking_the_url(
        self, client: TestClient, receiver: Receiver, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            response = client.post("/api/v1/owners/alice/test-route/r1")
        assert response.json() == {"success": True, "status_code": 200, "message": "Delivered"}
        assert json.loads(receiver.requests[0]["body"])["alerts"][0]["labels"]["alertname"] == "ChronowardenTest"
        assert "secret-token" not in caplog.text and "secret-token" not in response.text

    def test_failed_test_send_says_why(self, client: TestClient, receiver: Receiver) -> None:
        receiver.answers = [410]
        assert client.post("/api/v1/owners/alice/test-route/r1").json() == {
            "success": False,
            "status_code": 410,
            "message": "The receiver answered: HTTP 410",
        }

    def test_signing_secret_is_shown_once_and_signs_test_sends(
        self, client: TestClient, db: Database, receiver: Receiver
    ) -> None:
        created = client.post("/api/v1/owners/alice/routes/r1/signing")
        assert created.status_code == 201
        secret = created.json()["secret"]
        assert secret.startswith("whsec_")
        listed = client.get("/api/v1/owners/alice").text
        assert secret not in listed and json.loads(listed)["notification_routes"][0]["signed"] is True
        client.post("/api/v1/owners/alice/test-route/r1")
        assert receiver.requests[0]["headers"]["webhook-signature"].startswith("v1,")
        assert client.delete("/api/v1/owners/alice/routes/r1/signing").status_code == 204
        assert client.get("/api/v1/owners/alice").json()["notification_routes"][0]["signed"] is False
        events = [json.loads(e["after"]) for e in db.list_audit_events(event_type="owner.route_signing")]
        assert events == [{"id": "r1", "signed": False}, {"id": "r1", "signed": True}]
        assert all(secret not in json.dumps(e) for e in db.list_audit_events())

    @pytest.mark.parametrize("address", ["file:///etc/passwd", "gopher://x", "javascript:alert(1)", "hooks.example"])
    def test_route_address_must_be_http(self, client: TestClient, address: str) -> None:
        response = client.post("/api/v1/owners/alice/routes", json={"type": "webhook", "address": address})
        assert response.status_code == 422

    def test_signing_unknown_route_is_404(self, client: TestClient) -> None:
        assert client.post("/api/v1/owners/alice/routes/nope/signing").status_code == 404
        assert client.delete("/api/v1/owners/bob/routes/r1/signing").status_code == 404
