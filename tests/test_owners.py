# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for owner management functionality."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.api.owners import router
from chronowarden.database import Database


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
        self.db.create_notification_route("route-1", "owner-1", "email", "alice@example.com", "Test: {secret_name}")
        routes = self.db.list_notification_routes("owner-1")
        assert len(routes) == 1
        assert routes[0]["type"] == "email"
        assert routes[0]["address"] == "alice@example.com"

    def test_delete_notification_route(self) -> None:
        """Test deleting a notification route."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_notification_route("route-1", "owner-1", "email", "alice@example.com", "Test")
        self.db.delete_notification_route("route-1")
        routes = self.db.list_notification_routes("owner-1")
        assert len(routes) == 0

    def test_delete_owner_cascades_routes(self) -> None:
        """Test that deleting an owner also deletes routes."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_notification_route("route-1", "owner-1", "email", "alice@example.com", "Test")
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
        self.db.create_notification_route("route-1", "owner-1", "email", "alice@example.com", "Template 1")
        self.db.create_notification_route("route-2", "owner-1", "webhook", "https://hooks.example.com", "Template 2")
        routes = self.db.list_notification_routes("owner-1")
        assert len(routes) == 2
        types = {r["type"] for r in routes}
        assert types == {"email", "webhook"}

    def test_list_notification_routes_empty(self) -> None:
        """Test listing routes for an owner with no routes returns empty list."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        routes = self.db.list_notification_routes("owner-1")
        assert routes == []

    def test_list_notification_routes_nonexistent_owner(self) -> None:
        """Test listing routes for a nonexistent owner returns empty list."""
        routes = self.db.list_notification_routes("nonexistent")
        assert routes == []

    def test_notification_route_message_template(self) -> None:
        """Test that notification route preserves the message template."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        template = "Secret {secret_name} in {vault} expires in {days_until_expiry} days"
        self.db.create_notification_route("route-1", "owner-1", "email", "alice@example.com", template)
        routes = self.db.list_notification_routes("owner-1")
        assert len(routes) == 1
        assert routes[0]["message_template"] == template

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

    def test_owner_has_created_at(self) -> None:
        """Test that created_at is populated automatically."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        owner = self.db.get_owner("owner-1")
        assert owner is not None
        assert owner["created_at"] is not None


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
                json={"type": "email", "address": "alice@example.com", "message_template": "Test: {secret_name}"},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["type"] == "email"
            assert data["address"] == "alice@example.com"
            assert data["owner_id"] == "owner-1"

    def test_add_route_owner_not_found(self) -> None:
        """Test adding a route to a nonexistent owner returns 404."""
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.post(
                "/api/v1/owners/nonexistent/routes",
                json={"type": "email", "address": "test@example.com"},
            )
            assert response.status_code == 404

    def test_delete_notification_route(self) -> None:
        """Test deleting a notification route via API."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_notification_route("route-1", "owner-1", "email", "alice@example.com", "Test")
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
        self.db.create_notification_route("route-1", "owner-1", "email", "alice@example.com", "Template")
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

    def test_test_route_success(self) -> None:
        """Test the test-route endpoint returns success."""
        self.db.create_owner("owner-1", "Alice", "alice@example.com")
        self.db.create_notification_route("route-1", "owner-1", "email", "alice@example.com", "Test")
        client = self._build_client()
        with patch("chronowarden.api.owners._get_db", return_value=self.db):
            response = client.post("/api/v1/owners/owner-1/test-route/route-1")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

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
