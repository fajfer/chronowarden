# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the hash-chained audit log and the events Chronowarden records (#24, ADR-014)."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.api.audit import router as audit_router
from chronowarden.api.owners import router as owners_router
from chronowarden.api.secrets import router as secrets_router
from chronowarden.api.systems import router as systems_router
from chronowarden.audit import GENESIS_HASH, verify_chain
from chronowarden.audit.config_events import record_config_change
from chronowarden.config import AppConfig
from chronowarden.database import Database, SecretMetadataCache

UI = {"X-Chronowarden-Client": "ui"}


@pytest.fixture
def db(db: Database) -> Database:
    """A migrated database with one cached secret and two owners."""
    database = db  # the shared fixture from conftest.py, seeded here
    database.upsert_secret_metadata(SecretMetadataCache(vault_name="prod", engine_id="apps", secret_path="db"))
    database.create_owner("alice", "Alice", "alice@example.com")
    database.create_owner("bob", "Bob", "bob@example.com")
    return database


@pytest.fixture
def client(db: Database) -> Iterator[TestClient]:
    app = FastAPI()
    for router in (audit_router, owners_router, secrets_router, systems_router):
        app.include_router(router, prefix="/api/v1")
    with (
        patch("chronowarden.api.audit._get_db", return_value=db),
        patch("chronowarden.api.owners._get_db", return_value=db),
        patch("chronowarden.api.systems._get_db", return_value=db),
        patch("chronowarden.api.secrets._get_app_dependencies", return_value=(db, AppConfig(), MagicMock())),
    ):
        yield TestClient(app)


def _types(db: Database) -> list[str]:
    return [e["event_type"] for e in reversed(db.list_audit_events(limit=1000))]


class TestChain:
    """Append, verify and tamper detection."""

    def test_events_chain_from_genesis(self, db: Database) -> None:
        first = db.append_audit_event("test.a", "api", after={"x": 1})
        second = db.append_audit_event("test.b", "sync", identity=("prod", "apps", "db"), before={"x": 1})
        assert first is not None and second is not None
        assert first["prev_hash"] == GENESIS_HASH and second["prev_hash"] == first["hash"]
        status = verify_chain(db.iter_audit_events())
        assert status.valid and status.events == 2 and status.head_hash == second["hash"]

    def test_update_and_delete_are_refused(self, db: Database) -> None:
        db.append_audit_event("test.a", "api")
        assert db._conn is not None
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db._conn.execute("UPDATE audit_events SET after = '{}'")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db._conn.execute("DELETE FROM audit_events")

    @pytest.mark.parametrize(
        "tamper,reason",
        [
            ("UPDATE audit_events SET after = '{\"x\":2}' WHERE id = 2", "content"),
            ("DELETE FROM audit_events WHERE id = 2", "expected id"),
        ],
    )
    def test_tampering_is_detected(self, db: Database, tamper: str, reason: str) -> None:
        for n in range(3):
            db.append_audit_event("test.a", "api", after={"x": n})
        assert db._conn is not None
        # Someone with file access drops the triggers first
        db._conn.execute("DROP TRIGGER audit_events_no_update")
        db._conn.execute("DROP TRIGGER audit_events_no_delete")
        db._conn.execute(tamper)
        db._conn.commit()
        status = verify_chain(db.iter_audit_events())
        assert not status.valid and status.first_invalid_id in (2, 3) and reason in (status.reason or "")

    def test_export_verifies_without_chronowarden(self, client: TestClient, db: Database) -> None:
        """The JSONL export plus the documented recipe is enough to check the chain independently."""
        db.append_audit_event("test.a", "api", after={"zażółć": "gęślą"})
        db.append_audit_event("test.b", "api", identity=("prod", "apps", "db"))
        response = client.get("/api/v1/audit/events.jsonl")
        assert response.headers["content-type"].startswith("application/x-ndjson")
        previous = "0" * 64
        fields = (
            "id",
            "timestamp",
            "source",
            "actor",
            "event_type",
            "subject",
            "vault_name",
            "engine_id",
            "secret_path",
            "before",
            "after",
            "prev_hash",
        )
        for line in response.text.splitlines():
            event = json.loads(line)
            assert event["prev_hash"] == previous
            payload = json.dumps(
                {k: event[k] for k in fields}, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            assert hashlib.sha256(payload.encode("utf-8")).hexdigest() == event["hash"]
            previous = event["hash"]

    def test_verify_endpoint(self, client: TestClient, db: Database) -> None:
        event = db.append_audit_event("test.a", "api")
        assert event is not None
        assert client.get("/api/v1/audit/verify").json() == {
            "valid": True,
            "events": 1,
            "head_hash": event["hash"],
            "first_invalid_id": None,
            "reason": None,
        }


def test_iteration_crosses_batches(db: Database) -> None:
    """The export and verify read the log in batches; the chain must not break at batch boundaries."""
    for n in range(7):
        db.append_audit_event("test.a", "api", after={"n": n})
    assert [e["id"] for e in db.iter_audit_events(batch=3)] == list(range(1, 8))
    assert verify_chain(db.iter_audit_events(batch=3)).valid


class TestListing:
    def test_filters_and_paging(self, client: TestClient, db: Database) -> None:
        for n in range(5):
            db.append_audit_event("test.a" if n % 2 else "test.b", "api", identity=("prod", "apps", f"s{n}"))
        assert [e["secret_path"] for e in client.get("/api/v1/audit/events?event_type=test.a").json()] == ["s3", "s1"]
        page = client.get("/api/v1/audit/events?limit=2").json()
        assert [e["id"] for e in page] == [5, 4]
        assert [e["id"] for e in client.get("/api/v1/audit/events?limit=2&before_id=4").json()] == [3, 2]

    def test_before_and_after_are_parsed(self, client: TestClient, db: Database) -> None:
        db.append_audit_event("test.a", "api", before={"a": [1]}, after=None)
        event = client.get("/api/v1/audit/events").json()[0]
        assert event["before"] == {"a": [1]} and event["after"] is None


class TestRecordedEvents:
    """What the API and sync write into the log."""

    def test_assignment_history_of_a_secret(self, client: TestClient, db: Database) -> None:
        system = client.post("/api/v1/systems/", json={"name": "Billing"}, headers=UI).json()
        entry = db.get_secret_metadata("prod", "apps", "db")
        assert entry is not None
        client.put(f"/api/v1/secrets/{entry.id}/system", json={"system_id": system["id"]}, headers=UI)
        client.put(f"/api/v1/secrets/{entry.id}/owners", json={"owner_ids": ["alice"]})
        history = client.get(f"/api/v1/secrets/{entry.id}/history").json()
        assert [(e["event_type"], e["source"]) for e in history] == [("secret.owners", "api"), ("secret.system", "ui")]
        assert history[0]["after"] == {"owners": [{"id": "alice", "name": "Alice"}]}
        assert history[1]["after"]["system"]["name"] == "Billing"

    def test_system_lifecycle(self, client: TestClient, db: Database) -> None:
        system = client.post("/api/v1/systems/", json={"name": "Billing", "owner_ids": ["bob"]}).json()
        client.put(f"/api/v1/systems/{system['id']}", json={"asset_number": "AS-1", "name": "Billing"})
        client.put(f"/api/v1/systems/{system['id']}/owners", json={"owner_ids": ["alice"]})
        client.delete(f"/api/v1/systems/{system['id']}")
        assert _types(db) == ["system.created", "system.updated", "system.owners", "system.deleted"]
        updated = db.list_audit_events(event_type="system.updated")[0]
        assert json.loads(updated["after"]) == {"asset_number": "AS-1"}, "unchanged fields are left out"

    def test_owner_deletion_records_the_cascade(self, client: TestClient, db: Database) -> None:
        system = client.post("/api/v1/systems/", json={"name": "Billing", "owner_ids": ["alice", "bob"]}).json()
        entry = db.get_secret_metadata("prod", "apps", "db")
        assert entry is not None
        client.put(f"/api/v1/secrets/{entry.id}/owners", json={"owner_ids": ["alice"]})
        client.delete("/api/v1/owners/alice")
        assert _types(db)[-3:] == ["owner.deleted", "secret.owners", "system.owners"]
        system_event = db.list_audit_events(event_type="system.owners")[0]
        assert system_event["subject"] == f"system:{system['id']}"
        assert json.loads(system_event["after"]) == {"owner_ids": ["bob"]}

    def test_removed_reappeared_and_purged(self, client: TestClient, db: Database) -> None:
        from chronowarden.metadata import _reconcile_removed

        _reconcile_removed(db, "prod", "apps", [], [])
        _reconcile_removed(db, "prod", "apps", ["db"], [])
        _reconcile_removed(db, "prod", "apps", [], [])
        client.delete("/api/v1/secrets/removed")
        assert _types(db) == ["secret.removed", "secret.reappeared", "secret.removed", "secret.purged"]
        assert {e["source"] for e in db.list_audit_events()} == {"sync", "api"}

    def test_incomplete_listing_records_nothing(self, db: Database) -> None:
        from chronowarden.metadata import _reconcile_removed

        _reconcile_removed(db, "prod", "apps", [], ["apps/team/"])
        assert _types(db) == []


class TestConfigEvents:
    def test_baseline_then_only_changes(self, db: Database) -> None:
        config = AppConfig.model_validate(
            {"vaults": [{"name": "prod", "address": "http://v:8200", "token_env": "T", "severity": "critical"}]}
        )
        record_config_change(db, config)
        record_config_change(db, config)
        assert _types(db) == ["config.baseline"]
        changed = AppConfig.model_validate(
            {"vaults": [{"name": "prod", "address": "http://v:8200", "token_env": "T", "severity": "default"}]}
        )
        record_config_change(db, changed)
        event = db.list_audit_events(event_type="config.changed")[0]
        assert event["source"] == "config"
        assert json.loads(event["before"])["vaults"][0]["severity"] == "critical"
        assert json.loads(event["after"])["vaults"][0]["severity"] == "default"

    def test_addresses_and_credentials_are_not_recorded(self, db: Database) -> None:
        config = AppConfig.model_validate(
            {"vaults": [{"name": "prod", "address": "http://secret-host:8200", "token": "hvs.SECRET"}]}
        )
        record_config_change(db, config)
        stored = db.list_audit_events()[0]["after"]
        assert "secret-host" not in stored and "hvs.SECRET" not in stored


class TestRevert:
    """POST /audit/events/{id}/revert."""

    def _secret_id(self, db: Database) -> int:
        entry = db.get_secret_metadata("prod", "apps", "db")
        assert entry is not None and entry.id is not None
        return entry.id

    def test_revert_system_assignment(self, client: TestClient, db: Database) -> None:
        billing = client.post("/api/v1/systems/", json={"name": "Billing"}).json()
        crm = client.post("/api/v1/systems/", json={"name": "CRM"}).json()
        url = f"/api/v1/secrets/{self._secret_id(db)}/system"
        client.put(url, json={"system_id": billing["id"]})
        client.put(url, json={"system_id": crm["id"]})
        last = db.list_audit_events(event_type="secret.system")[0]
        response = client.post(f"/api/v1/audit/events/{last['id']}/revert", headers=UI)
        assert response.status_code == 201
        event = response.json()
        assert event["source"] == "ui" and event["after"]["reverts"] == last["id"]
        assert event["after"]["system"]["name"] == "Billing" and event["before"]["system"]["name"] == "CRM"
        assert client.get(f"/api/v1/secrets/{self._secret_id(db)}").json()["system"]["name"] == "Billing"

    def test_revert_owners(self, client: TestClient, db: Database) -> None:
        url = f"/api/v1/secrets/{self._secret_id(db)}/owners"
        client.put(url, json={"owner_ids": ["alice"]})
        client.put(url, json={"owner_ids": ["alice", "bob"]})
        last = db.list_audit_events(event_type="secret.owners")[0]
        assert client.post(f"/api/v1/audit/events/{last['id']}/revert").status_code == 201
        assert [o["id"] for o in client.get(f"/api/v1/secrets/{self._secret_id(db)}").json()["owners"]] == ["alice"]

    def test_older_event_after_a_newer_change_is_409(self, client: TestClient, db: Database) -> None:
        url = f"/api/v1/secrets/{self._secret_id(db)}/owners"
        client.put(url, json={"owner_ids": ["alice"]})
        client.put(url, json={"owner_ids": ["bob"]})
        first = db.list_audit_events(event_type="secret.owners")[-1]
        response = client.post(f"/api/v1/audit/events/{first['id']}/revert")
        assert response.status_code == 409 and "changed since" in response.json()["detail"]

    def test_deleted_system_is_409(self, client: TestClient, db: Database) -> None:
        billing = client.post("/api/v1/systems/", json={"name": "Billing"}).json()
        url = f"/api/v1/secrets/{self._secret_id(db)}/system"
        client.put(url, json={"system_id": billing["id"]})
        client.put(url, json={"system_id": None})
        client.delete(f"/api/v1/systems/{billing['id']}")
        last = db.list_audit_events(event_type="secret.system")[0]
        response = client.post(f"/api/v1/audit/events/{last['id']}/revert")
        assert response.status_code == 409 and "no longer exists" in response.json()["detail"]

    @pytest.mark.parametrize(
        "event_type,reason",
        [
            ("secret.metadata", "other teams"),
            ("secret.settings", "backend"),
            ("secret.config_applied", "config.yaml"),
            ("system.created", "only system and owner assignments"),
        ],
    )
    def test_refused_types_are_422(self, client: TestClient, db: Database, event_type: str, reason: str) -> None:
        event = db.append_audit_event(event_type, "sync", identity=("prod", "apps", "db"), before={}, after={})
        assert event is not None
        response = client.post(f"/api/v1/audit/events/{event['id']}/revert")
        assert response.status_code == 422 and reason in response.json()["detail"]

    def test_unknown_event_is_404(self, client: TestClient) -> None:
        assert client.post("/api/v1/audit/events/999/revert").status_code == 404
