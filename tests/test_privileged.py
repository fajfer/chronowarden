# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the chronowarden_privileged flag (#93)."""

import copy
import json
import logging
from collections.abc import Iterator
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.api.audit import router as audit_router
from chronowarden.api.secrets import router as secrets_router
from chronowarden.config import AppConfig
from chronowarden.database import Database
from chronowarden.metadata import parse_privileged, sync_secret_metadata

IDENTITY = ("prod", "apps", "db")


class FakeVault:
    """One secret whose writes merge into its custom metadata, like the real integration."""

    def __init__(self, privileged: Optional[str] = None) -> None:
        custom = {"owner_team": "payments"}
        if privileged is not None:
            custom["chronowarden_privileged"] = privileged
        self.metadata: dict[str, Any] = {
            "custom_metadata": custom,
            "updated_time": "2026-10-01T10:00:00.000000Z",
            "current_version": 1,
            "versions": {"1": {"created_time": "2026-10-01T10:00:00.000000Z"}},
        }
        self.connected = True
        self.fail_writes = False

    def get_secret_metadata(self, path: str, mount_point: Optional[str] = None) -> dict[str, Any]:
        return copy.deepcopy(self.metadata)

    def write_secret_metadata(self, path: str, fields: dict[str, str], mount_point: Optional[str] = None) -> bool:
        if self.fail_writes:
            return False
        self.metadata["custom_metadata"].update(fields)
        return True

    def is_connected(self) -> bool:
        return self.connected


def _sync(vault: FakeVault, db: Database) -> None:
    sync_secret_metadata(vault, *IDENTITY, AppConfig(), db)  # type: ignore[arg-type]


class TestParsing:
    @pytest.mark.parametrize(
        "value,expected", [("true", True), ("TRUE", True), (" True ", True), ("false", False), (None, False)]
    )
    def test_values(self, value: Optional[str], expected: bool) -> None:
        assert parse_privileged(value, "x") is expected

    @pytest.mark.parametrize("value", ["yes", "1", ""])
    def test_invalid_values_are_not_privileged_and_warn(self, value: str, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            assert parse_privileged(value, "prod/apps/db") is False
        assert "Ignoring invalid chronowarden_privileged" in caplog.text and "prod/apps/db" in caplog.text


class TestSync:
    def test_sync_reads_the_flag_and_notices_changes(self, db: Database) -> None:
        vault = FakeVault(privileged="true")
        _sync(vault, db)
        entry = db.get_secret_metadata(*IDENTITY)
        assert entry is not None and entry.privileged is True
        vault.metadata["custom_metadata"]["chronowarden_privileged"] = "false"
        _sync(vault, db)
        entry = db.get_secret_metadata(*IDENTITY)
        assert entry is not None and entry.privileged is False


@pytest.fixture
def vault() -> FakeVault:
    return FakeVault()


@pytest.fixture
def client(db: Database, vault: FakeVault) -> Iterator[TestClient]:
    _sync(vault, db)
    manager = MagicMock()
    manager.get.side_effect = lambda name: vault if name == "prod" else None
    app = FastAPI()
    app.include_router(secrets_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    with (
        patch("chronowarden.api.secrets._get_app_dependencies", return_value=(db, AppConfig(), manager)),
        patch("chronowarden.api.audit._get_db", return_value=db),
        patch("chronowarden.app.vault_manager", manager),
    ):
        yield TestClient(app)


def _id(db: Database) -> int:
    entry = db.get_secret_metadata(*IDENTITY)
    assert entry is not None and entry.id is not None
    return entry.id


class TestApi:
    def test_toggle_writes_to_vault_and_keeps_other_keys(
        self, client: TestClient, db: Database, vault: FakeVault
    ) -> None:
        response = client.put(f"/api/v1/secrets/{_id(db)}/privileged", json={"privileged": True})
        assert response.status_code == 200 and response.json()["privileged"] is True
        assert vault.metadata["custom_metadata"] == {
            "owner_team": "payments",
            "chronowarden_severity": "default",
            "chronowarden_ttl": "2027-10-01",
            "chronowarden_privileged": "true",
        }
        event = db.list_audit_events(event_type="secret.privileged")[0]
        assert (json.loads(event["before"]), json.loads(event["after"])) == (
            {"privileged": False},
            {"privileged": True},
        )

    def test_next_sync_doesnt_report_the_write_as_a_backend_change(
        self, client: TestClient, db: Database, vault: FakeVault
    ) -> None:
        client.put(f"/api/v1/secrets/{_id(db)}/privileged", json={"privileged": True})
        _sync(vault, db)
        assert db.list_audit_events(event_type="secret.metadata") == []
        assert db.get_secret_metadata(*IDENTITY).privileged is True  # type: ignore[union-attr]

    def test_list_filter(self, client: TestClient, db: Database) -> None:
        client.put(f"/api/v1/secrets/{_id(db)}/privileged", json={"privileged": True})
        assert len(client.get("/api/v1/secrets/?privileged=true").json()) == 1
        assert client.get("/api/v1/secrets/?privileged=false").json() == []

    def test_disconnected_or_failed_write_is_503_and_changes_nothing(
        self, client: TestClient, db: Database, vault: FakeVault
    ) -> None:
        vault.connected = False
        assert client.put(f"/api/v1/secrets/{_id(db)}/privileged", json={"privileged": True}).status_code == 503
        vault.connected, vault.fail_writes = True, True
        assert client.put(f"/api/v1/secrets/{_id(db)}/privileged", json={"privileged": True}).status_code == 503
        assert db.get_secret_metadata(*IDENTITY).privileged is False  # type: ignore[union-attr]
        assert db.list_audit_events(event_type="secret.privileged") == []

    def test_revert_writes_the_previous_value_back(self, client: TestClient, db: Database, vault: FakeVault) -> None:
        client.put(f"/api/v1/secrets/{_id(db)}/privileged", json={"privileged": True})
        event = db.list_audit_events(event_type="secret.privileged")[0]
        response = client.post(f"/api/v1/audit/events/{event['id']}/revert")
        assert response.status_code == 201, response.text
        assert response.json()["after"] == {"privileged": False, "reverts": event["id"]}
        assert vault.metadata["custom_metadata"]["chronowarden_privileged"] == "false"
        assert client.post(f"/api/v1/audit/events/{event['id']}/revert").status_code == 409
