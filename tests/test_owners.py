# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for owner management functionality."""

from pathlib import Path

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
