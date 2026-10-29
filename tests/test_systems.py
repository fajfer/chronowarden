# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for systems and the system/owner assignments of secrets (#61)."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.api.owners import router as owners_router
from chronowarden.api.secrets import router as secrets_router
from chronowarden.api.systems import router as systems_router
from chronowarden.config import AppConfig
from chronowarden.database import Database, SecretMetadataCache


@pytest.fixture
def db(db: Database) -> Database:
    """A migrated database with two cached secrets and two owners."""
    database = db  # the shared fixture from conftest.py, seeded here
    for path in ("app/db", "app/api"):
        database.upsert_secret_metadata(
            SecretMetadataCache(vault_name="prod", engine_id="secret", secret_path=path, ttl="2030-01-01")
        )
    database.create_owner("alice", "Alice", "alice@example.com")
    database.create_owner("bob", "Bob", "bob@example.com")
    return database


@pytest.fixture
def client(db: Database) -> Iterator[TestClient]:
    """A client for the systems, secrets and owners routers on the test database."""
    app = FastAPI()
    for router in (systems_router, secrets_router, owners_router):
        app.include_router(router, prefix="/api/v1")
    with (
        patch("chronowarden.api.systems._get_db", return_value=db),
        patch("chronowarden.api.owners._get_db", return_value=db),
        patch("chronowarden.api.secrets._get_app_dependencies", return_value=(db, AppConfig(), MagicMock())),
    ):
        yield TestClient(app)


def _create_system(client: TestClient, name: str = "Billing", owner_ids: list[str] | None = None) -> dict:
    response = client.post(
        "/api/v1/systems/",
        json={"name": name, "cmdb_uri": "https://cmdb.example.com/ci/42", "owner_ids": owner_ids or []},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _secret_id(db: Database, path: str = "app/db") -> int:
    entry = db.get_secret_metadata("prod", "secret", path)
    assert entry is not None and entry.id is not None
    return entry.id


class TestSystemsApi:
    """CRUD on /systems."""

    def test_create_and_get(self, client: TestClient) -> None:
        created = _create_system(client, owner_ids=["bob", "alice"])
        assert created["name"] == "Billing"
        assert created["cmdb_uri"] == "https://cmdb.example.com/ci/42"
        assert [o["id"] for o in created["owners"]] == ["alice", "bob"]
        fetched = client.get(f"/api/v1/systems/{created['id']}").json()
        assert fetched == created

    def test_list_sorted_by_name(self, client: TestClient) -> None:
        _create_system(client, "CRM")
        _create_system(client, "Billing")
        assert [s["name"] for s in client.get("/api/v1/systems/").json()] == ["Billing", "CRM"]

    def test_duplicate_name_is_409(self, client: TestClient) -> None:
        _create_system(client)
        assert client.post("/api/v1/systems/", json={"name": "Billing"}).status_code == 409

    def test_blank_name_is_422(self, client: TestClient) -> None:
        assert client.post("/api/v1/systems/", json={"name": "   "}).status_code == 422

    def test_unknown_owner_is_422(self, client: TestClient) -> None:
        response = client.post("/api/v1/systems/", json={"name": "Billing", "owner_ids": ["ghost"]})
        assert response.status_code == 422
        assert "ghost" in response.json()["detail"]
        assert client.get("/api/v1/systems/").json() == []

    def test_update_keeps_omitted_fields(self, client: TestClient) -> None:
        system = _create_system(client)
        response = client.put(f"/api/v1/systems/{system['id']}", json={"asset_number": "AS-7"})
        assert response.status_code == 200
        assert response.json()["asset_number"] == "AS-7"
        assert response.json()["cmdb_uri"] == "https://cmdb.example.com/ci/42"

    def test_rename_to_taken_name_is_409(self, client: TestClient) -> None:
        _create_system(client, "CRM")
        system = _create_system(client)
        assert client.put(f"/api/v1/systems/{system['id']}", json={"name": "CRM"}).status_code == 409

    def test_replace_owners(self, client: TestClient) -> None:
        system = _create_system(client, owner_ids=["alice"])
        response = client.put(f"/api/v1/systems/{system['id']}/owners", json={"owner_ids": ["bob"]})
        assert [o["id"] for o in response.json()["owners"]] == ["bob"]

    def test_too_many_owner_ids_is_422(self, client: TestClient) -> None:
        """Regression: owner lists are capped before any id is looked up."""
        ids = [f"owner-{n}" for n in range(1001)]
        assert client.post("/api/v1/systems/", json={"name": "Billing", "owner_ids": ids}).status_code == 422
        system = _create_system(client)
        assert client.put(f"/api/v1/systems/{system['id']}/owners", json={"owner_ids": ids}).status_code == 422

    def test_unknown_system_is_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/systems/nope").status_code == 404
        assert client.put("/api/v1/systems/nope", json={"name": "X"}).status_code == 404
        assert client.put("/api/v1/systems/nope/owners", json={"owner_ids": []}).status_code == 404
        assert client.delete("/api/v1/systems/nope").status_code == 404


class TestSecretAssignments:
    """PUT /secrets/{id}/system and /owners, effective owners and filters."""

    def test_new_secret_is_unassigned(self, client: TestClient, db: Database) -> None:
        secret = client.get(f"/api/v1/secrets/{_secret_id(db)}").json()
        assert secret["system"] is None
        assert secret["owners"] == [] and secret["effective_owners"] == []

    def test_assign_change_and_unassign_system(self, client: TestClient, db: Database) -> None:
        billing, crm = _create_system(client), _create_system(client, "CRM")
        url = f"/api/v1/secrets/{_secret_id(db)}/system"
        assert client.put(url, json={"system_id": billing["id"]}).json()["system"]["name"] == "Billing"
        assert client.put(url, json={"system_id": crm["id"]}).json()["system"]["name"] == "CRM"
        assert client.put(url, json={"system_id": None}).json()["system"] is None

    def test_effective_owners_fall_back_to_the_system(self, client: TestClient, db: Database) -> None:
        system = _create_system(client, owner_ids=["bob"])
        secret_id = _secret_id(db)
        secret = client.put(f"/api/v1/secrets/{secret_id}/system", json={"system_id": system["id"]}).json()
        assert secret["owners"] == []
        assert [o["id"] for o in secret["effective_owners"]] == ["bob"]
        secret = client.put(f"/api/v1/secrets/{secret_id}/owners", json={"owner_ids": ["alice"]}).json()
        assert [o["id"] for o in secret["owners"]] == ["alice"]
        assert [o["id"] for o in secret["effective_owners"]] == ["alice"]

    def test_owners_replace_the_whole_list(self, client: TestClient, db: Database) -> None:
        url = f"/api/v1/secrets/{_secret_id(db)}/owners"
        client.put(url, json={"owner_ids": ["alice", "bob"]})
        assert [o["id"] for o in client.put(url, json={"owner_ids": ["bob"]}).json()["owners"]] == ["bob"]
        assert client.put(url, json={"owner_ids": []}).json()["owners"] == []

    def test_unknown_ids(self, client: TestClient, db: Database) -> None:
        secret_id = _secret_id(db)
        assert client.put(f"/api/v1/secrets/{secret_id}/system", json={"system_id": "nope"}).status_code == 422
        assert client.put(f"/api/v1/secrets/{secret_id}/owners", json={"owner_ids": ["ghost"]}).status_code == 422
        assert client.put("/api/v1/secrets/999/system", json={"system_id": None}).status_code == 404
        assert client.put("/api/v1/secrets/999/owners", json={"owner_ids": []}).status_code == 404

    def test_filters(self, client: TestClient, db: Database) -> None:
        system = _create_system(client, owner_ids=["bob"])
        client.put(f"/api/v1/secrets/{_secret_id(db)}/system", json={"system_id": system["id"]})

        def paths(query: str) -> list[str]:
            return [s["secret_path"] for s in client.get(f"/api/v1/secrets/?{query}").json()]

        assert paths(f"system_id={system['id']}") == ["app/db"]
        assert paths("owner_id=bob") == ["app/db"]
        assert paths("owner_id=alice") == []
        assert paths("unassigned=true") == ["app/api"]
        assert paths("unassigned=false") == ["app/db"]

    def test_unchanged_assignment_records_nothing(self, client: TestClient, db: Database) -> None:
        client.put(f"/api/v1/secrets/{_secret_id(db)}/owners", json={"owner_ids": []})
        assert db.list_audit_events(event_type="secret.owners") == []

    def test_assignments_survive_a_rebuilt_cache(self, client: TestClient, db: Database) -> None:
        """ADR-017: assignments are keyed by identity, so deleting and re-syncing the cache row keeps them."""
        system = _create_system(client)
        client.put(f"/api/v1/secrets/{_secret_id(db)}/system", json={"system_id": system["id"]})
        client.put(f"/api/v1/secrets/{_secret_id(db)}/owners", json={"owner_ids": ["alice"]})
        old_id = _secret_id(db)
        db.delete_secret_metadata("prod", "secret", "app/db")
        db.upsert_secret_metadata(SecretMetadataCache(vault_name="prod", engine_id="secret", secret_path="app/db"))
        new_id = _secret_id(db)
        assert new_id != old_id
        secret = client.get(f"/api/v1/secrets/{new_id}").json()
        assert secret["system"]["id"] == system["id"]
        assert [o["id"] for o in secret["owners"]] == ["alice"]


class TestDeleting:
    """Deleting systems and owners that are in use."""

    def test_system_with_secrets_is_409_with_the_list(self, client: TestClient, db: Database) -> None:
        system = _create_system(client)
        client.put(f"/api/v1/secrets/{_secret_id(db)}/system", json={"system_id": system["id"]})
        response = client.delete(f"/api/v1/systems/{system['id']}")
        assert response.status_code == 409
        assert response.json()["detail"]["secrets"] == ["prod/secret/app/db"]
        client.put(f"/api/v1/secrets/{_secret_id(db)}/system", json={"system_id": None})
        assert client.delete(f"/api/v1/systems/{system['id']}").status_code == 204
        assert client.get(f"/api/v1/systems/{system['id']}").status_code == 404

    def test_deleting_an_owner_removes_it_everywhere(self, client: TestClient, db: Database) -> None:
        system = _create_system(client, owner_ids=["alice", "bob"])
        client.put(f"/api/v1/secrets/{_secret_id(db)}/owners", json={"owner_ids": ["alice"]})
        assert client.delete("/api/v1/owners/alice").status_code == 204
        assert [o["id"] for o in client.get(f"/api/v1/systems/{system['id']}").json()["owners"]] == ["bob"]
        assert client.get(f"/api/v1/secrets/{_secret_id(db)}").json()["owners"] == []


@pytest.mark.parametrize("uri", ["javascript:alert(document.domain)", "data:text/html,x", "  JavaScript:x", "ftp://x"])
def test_cmdb_uri_must_be_http(client: TestClient, uri: str) -> None:
    """Regression (0.7.1): the UI renders cmdb_uri as a link, so a javascript: URL would run in Chronowarden."""
    assert client.post("/api/v1/systems/", json={"name": "X", "cmdb_uri": uri}).status_code == 422
    system = client.post("/api/v1/systems/", json={"name": "Y"}).json()
    assert client.put(f"/api/v1/systems/{system['id']}", json={"cmdb_uri": uri}).status_code == 422


def test_cmdb_uri_http_and_https_are_accepted(client: TestClient) -> None:
    for i, uri in enumerate(["https://cmdb.example.com/ci/1", "HTTP://cmdb.example.com/ci/2"]):
        assert client.post("/api/v1/systems/", json={"name": f"S{i}", "cmdb_uri": uri}).status_code == 201
