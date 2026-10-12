# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for secrets deleted in the backend: removed_at, reappearing and purging (#86)."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hvac.exceptions import Forbidden

from chronowarden.api.secrets import router as secrets_router
from chronowarden.config import AppConfig
from chronowarden.database import Database, SecretMetadataCache
from chronowarden.metadata import detect_changes


class FakeVault:
    """A vault with one KV engine whose listing can be changed or made to fail."""

    def __init__(self, tree: dict[str, list[str]]) -> None:
        self.tree = tree
        self.fail_on: set[str] = set()

    def discover_engines(self) -> list[dict[str, Any]]:
        return [{"path": "apps"}]

    def list_secrets(self, path: str, mount_point: str | None = None, strict: bool = False) -> list[str]:
        if path in self.fail_on:
            raise Forbidden("Permission denied")
        return self.tree.get(path, [])


def _fake_sync(vault: Any, vault_name: str, engine: str, path: str, config: AppConfig, db: Database) -> None:
    """Stand-in for sync_secret_metadata: cache the listed secret."""
    db.upsert_secret_metadata(SecretMetadataCache(vault_name=vault_name, engine_id=engine, secret_path=path))


def _sync(vault: FakeVault, db: Database) -> None:
    with patch("chronowarden.metadata.sync_secret_metadata", side_effect=_fake_sync):
        detect_changes(vault, "prod", AppConfig(), db)  # type: ignore[arg-type]


def _removed(db: Database) -> dict[str, bool]:
    return {e.secret_path: e.removed_at is not None for e in db.list_all_secrets(include_removed=True)}


class TestSyncMarksRemoved:
    """detect_changes and Database.reconcile_engine."""

    def test_deleted_secret_is_marked_and_comes_back(self, db: Database) -> None:
        vault = FakeVault({"": ["db", "team/"], "team/": ["token"]})
        _sync(vault, db)
        assert _removed(db) == {"db": False, "team/token": False}

        vault.tree = {"": ["team/"], "team/": ["token"]}
        _sync(vault, db)
        assert _removed(db) == {"db": True, "team/token": False}
        assert [e.secret_path for e in db.list_all_secrets()] == ["team/token"]

        vault.tree = {"": ["db", "team/"], "team/": ["token"]}
        _sync(vault, db)
        assert _removed(db) == {"db": False, "team/token": False}

    def test_empty_engine_marks_everything(self, db: Database) -> None:
        """Vault answers 'not found' when the last secret is deleted; that is an empty, complete listing."""
        vault = FakeVault({"": ["db"]})
        _sync(vault, db)
        vault.tree = {}
        _sync(vault, db)
        assert _removed(db) == {"db": True}

    def test_failed_root_listing_marks_nothing(self, db: Database) -> None:
        vault = FakeVault({"": ["db", "api"]})
        _sync(vault, db)
        vault.fail_on = {""}
        _sync(vault, db)
        assert _removed(db) == {"db": False, "api": False}

    def test_failed_folder_listing_marks_nothing(self, db: Database) -> None:
        """A partial listing (one folder failed) must not mark the secrets it missed."""
        vault = FakeVault({"": ["db", "team/"], "team/": ["token"]})
        _sync(vault, db)
        vault.fail_on = {"team/"}
        vault.tree = {"": ["team/"], "team/": ["token"]}
        _sync(vault, db)
        assert _removed(db) == {"db": False, "team/token": False}

    def test_sync_stopping_part_way_marks_nothing(self, db: Database) -> None:
        vault = FakeVault({"": ["db", "api"]})
        _sync(vault, db)
        vault.tree = {"": ["db"]}
        with patch("chronowarden.metadata.sync_secret_metadata", side_effect=ConnectionError("gone")):
            with pytest.raises(ConnectionError):
                detect_changes(vault, "prod", AppConfig(), db)  # type: ignore[arg-type]
        assert _removed(db) == {"db": False, "api": False}

    def test_other_engines_and_vaults_are_untouched(self, db: Database) -> None:
        for vault_name, engine in (("prod", "apps"), ("prod", "other"), ("dev", "apps")):
            db.upsert_secret_metadata(SecretMetadataCache(vault_name=vault_name, engine_id=engine, secret_path="x"))
        removed, reappeared = db.reconcile_engine("prod", "apps", set(), "2026-10-11T00:00:00+00:00")
        assert (removed, reappeared) == (["x"], [])
        still_there = {(e.vault_name, e.engine_id) for e in db.list_all_secrets()}
        assert still_there == {("prod", "other"), ("dev", "apps")}

    def test_resync_keeps_removed_at_until_listed(self, db: Database) -> None:
        """Updating the cache row (e.g. on a metadata read) doesn't clear removed_at; only being listed does."""
        db.upsert_secret_metadata(SecretMetadataCache(vault_name="prod", engine_id="apps", secret_path="db"))
        db.reconcile_engine("prod", "apps", set(), "2026-10-11T00:00:00+00:00")
        db.upsert_secret_metadata(SecretMetadataCache(vault_name="prod", engine_id="apps", secret_path="db", ttl="x"))
        assert _removed(db) == {"db": True}


@pytest.fixture
def client(db: Database) -> Iterator[TestClient]:
    """A secrets API client on a database with one live and two removed secrets, all assigned to an owner."""
    db.create_owner("alice", "Alice", "alice@example.com")
    for engine, path in (("apps", "live"), ("apps", "gone"), ("other", "gone-too")):
        db.upsert_secret_metadata(SecretMetadataCache(vault_name="prod", engine_id=engine, secret_path=path))
        db.set_secret_owners(("prod", engine, path), ["alice"])
    db.reconcile_engine("prod", "apps", {"live"}, "2026-10-11T00:00:00+00:00")
    db.reconcile_engine("prod", "other", set(), "2026-10-11T00:00:00+00:00")
    app = FastAPI()
    app.include_router(secrets_router, prefix="/api/v1")
    with patch("chronowarden.api.secrets._get_app_dependencies", return_value=(db, AppConfig(), MagicMock())):
        yield TestClient(app)


def _id(db: Database, engine: str, path: str) -> int:
    entry = db.get_secret_metadata("prod", engine, path)
    assert entry is not None and entry.id is not None
    return entry.id


class TestApi:
    """GET include_removed and the purge endpoints."""

    def test_removed_hidden_unless_asked(self, client: TestClient) -> None:
        assert [s["secret_path"] for s in client.get("/api/v1/secrets/").json()] == ["live"]
        listed = client.get("/api/v1/secrets/?include_removed=true").json()
        assert {s["secret_path"]: s["removed_at"] is not None for s in listed} == {
            "live": False,
            "gone": True,
            "gone-too": True,
        }

    def test_purge_one_removed_secret_and_its_assignments(self, client: TestClient, db: Database) -> None:
        assert client.delete(f"/api/v1/secrets/{_id(db, 'apps', 'gone')}").status_code == 204
        assert db.get_secret_metadata("prod", "apps", "gone") is None
        assert ("prod", "apps", "gone") not in db.get_assignments()[1]
        assert ("prod", "apps", "live") in db.get_assignments()[1]

    def test_purge_refuses_live_and_unknown(self, client: TestClient, db: Database) -> None:
        assert client.delete(f"/api/v1/secrets/{_id(db, 'apps', 'live')}").status_code == 409
        assert client.delete("/api/v1/secrets/999").status_code == 404

    def test_bulk_purge_with_filter(self, client: TestClient, db: Database) -> None:
        response = client.delete("/api/v1/secrets/removed?engine_id=other")
        assert response.json() == {"purged": 1, "secrets": ["prod/other/gone-too"]}
        response = client.delete("/api/v1/secrets/removed")
        assert response.json() == {"purged": 1, "secrets": ["prod/apps/gone"]}
        assert [s["secret_path"] for s in client.get("/api/v1/secrets/?include_removed=true").json()] == ["live"]

    def test_reappeared_secret_keeps_its_assignments(self, client: TestClient, db: Database) -> None:
        db.reconcile_engine("prod", "apps", {"live", "gone"}, "2026-10-12T00:00:00+00:00")
        secret = client.get(f"/api/v1/secrets/{_id(db, 'apps', 'gone')}").json()
        assert secret["removed_at"] is None
        assert [o["id"] for o in secret["owners"]] == ["alice"]
