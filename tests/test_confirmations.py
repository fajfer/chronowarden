# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for rotation confirmation (#24, ADR-021)."""

import json
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from chronowarden.api.audit import router as audit_router
from chronowarden.api.secrets import router as secrets_router
from chronowarden.config import AppConfig, SecretConfig
from chronowarden.confirmations import confirmation_status, rotation_base
from chronowarden.database import Database, SecretMetadataCache

IDENTITY = ("prod", "apps", "db")
UPDATED = "2026-01-01T00:00:00.000000Z"


def _config(**vault: Any) -> AppConfig:
    return AppConfig.model_validate(
        {"vaults": [{"name": "prod", "address": "http://v:8200", "token_env": "T", **vault}]}
    )


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@pytest.fixture
def db(db: Database) -> Database:
    """A secret at version 1 (created 2026-01-01), cached with the default 365d profile."""
    database = db  # the shared fixture from conftest.py, seeded here
    database.upsert_secret_metadata(
        SecretMetadataCache(
            vault_name="prod",
            engine_id="apps",
            secret_path="db",
            updated_time=UPDATED,
            severity="default",
            ttl="2027-01-01",
        )
    )
    _set_version(database, 1, UPDATED)
    return database


def _set_version(db: Database, version: int, created: str) -> None:
    db.set_observed_state(
        IDENTITY, {"custom_metadata": {}, "settings": {}, "version": {"current": version, "created_time": created}}
    )


class TestConfig:
    def test_cascade_secret_engine_vault_default(self) -> None:
        config = _config(
            confirmation_required=True,
            engines=[
                {
                    "name": "auto",
                    "confirmation_required": False,
                    "secrets": [{"path": "manual", "confirmation_required": True}],
                }
            ],
        )
        assert config.resolve_confirmation_required("apps", "prod", "x") is True
        assert config.resolve_confirmation_required("auto", "prod", "x") is False
        assert config.resolve_confirmation_required("auto", "prod", "manual") is True
        assert _config().resolve_confirmation_required("apps", "prod", "x") is False
        assert AppConfig().resolve_confirmation_required("apps", "unknown", "x") is False

    def test_secret_entry_must_override_something(self) -> None:
        with pytest.raises(ValidationError, match="neither severity nor confirmation_required"):
            SecretConfig(path="x")
        assert SecretConfig(path="x", confirmation_required=True).severity is None

    def test_secret_confirmation_only_keeps_the_engine_severity(self) -> None:
        config = _config(
            engines=[
                {"name": "apps", "severity": "critical", "secrets": [{"path": "db", "confirmation_required": True}]}
            ]
        )
        assert config.resolve_severity("apps", "prod", secret_path="db") == "critical"

    def test_grace_per_profile_then_global(self) -> None:
        config = AppConfig.model_validate(
            {
                "confirmation_grace": "3d",
                "expiry_profiles": {"critical": {"rotation_period": "6m", "confirmation_grace": "1d"}},
            }
        )
        assert config.get_confirmation_grace_days("critical") == 1
        assert config.get_confirmation_grace_days("default") == 3
        assert AppConfig().get_confirmation_grace_days("default") == 7

    def test_invalid_grace_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig.model_validate({"confirmation_grace": "soon"})


class TestStatus:
    def test_not_required_never_awaits(self, db: Database) -> None:
        status = confirmation_status(db, _config(), IDENTITY, "default")
        assert (status.required, status.awaiting, status.overdue) == (False, False, False)

    def test_required_and_unconfirmed_is_awaiting_and_overdue(self, db: Database) -> None:
        status = confirmation_status(db, _config(confirmation_required=True), IDENTITY, "default")
        assert status.awaiting and status.overdue, "version 1 was created months ago, past the 7d grace"

    def test_new_version_awaits_again(self, db: Database) -> None:
        config = _config(confirmation_required=True)
        db.add_confirmation(IDENTITY, 1, "2026-01-02T00:00:00.000000Z", None)
        assert not confirmation_status(db, config, IDENTITY, "default").awaiting
        _set_version(db, 2, _iso(datetime.now(tz=timezone.utc)))
        status = confirmation_status(db, config, IDENTITY, "default")
        assert status.awaiting and not status.overdue, "a fresh version is within the grace period"

    def test_rotation_base_uses_the_later_applied_date(self, db: Database) -> None:
        db.add_confirmation(IDENTITY, 1, "2026-01-10T00:00:00.000000Z", None)
        assert rotation_base(db, IDENTITY, UPDATED) == "2026-01-10T00:00:00.000000Z"
        _set_version(db, 2, "2026-02-01T00:00:00.000000Z")
        assert (
            rotation_base(db, IDENTITY, "2026-02-01T00:00:00.000000Z") == "2026-02-01T00:00:00.000000Z"
        ), "a confirmation of an older version doesn't count"


@pytest.fixture
def client(db: Database) -> Iterator[TestClient]:
    config = _config(confirmation_required=True)
    app = FastAPI()
    app.include_router(secrets_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    with (
        patch("chronowarden.api.secrets._get_app_dependencies", return_value=(db, config, MagicMock())),
        patch("chronowarden.api.audit._get_db", return_value=db),
        patch("chronowarden.app.app_config", config),
    ):
        yield TestClient(app)


def _secret_id(db: Database) -> int:
    entry = db.get_secret_metadata(*IDENTITY)
    assert entry is not None and entry.id is not None
    return entry.id


class TestConfirmEndpoint:
    def test_listed_secret_shows_awaiting(self, client: TestClient, db: Database) -> None:
        secret = client.get(f"/api/v1/secrets/{_secret_id(db)}").json()
        assert (
            secret["confirmation_required"] and secret["awaiting_confirmation"] and secret["last_confirmation"] is None
        )

    def test_historic_confirmation_moves_the_ttl(self, client: TestClient, db: Database) -> None:
        response = client.post(
            f"/api/v1/secrets/{_secret_id(db)}/confirmations",
            json={"applied_at": "2026-03-01T12:00:00Z", "confirmed_by": "deploy-pipeline"},
        )
        assert response.status_code == 201, response.text
        secret = response.json()
        assert not secret["awaiting_confirmation"]
        assert secret["last_confirmation"]["confirmed_by"] == "deploy-pipeline"
        assert secret["ttl"] == "2027-03-01", "next rotation counts from the applied date, not the backend update"
        event = db.list_audit_events(event_type="secret.confirmed")[0]
        assert json.loads(event["after"])["applied_at"] == "2026-03-01T12:00:00.000000Z"

    @pytest.mark.parametrize(
        "applied_at,message",
        [("2025-12-31T23:59:59Z", "before version 1 was created"), ("2099-01-01T00:00:00Z", "in the future")],
    )
    def test_bad_dates_are_422(self, client: TestClient, db: Database, applied_at: str, message: str) -> None:
        response = client.post(f"/api/v1/secrets/{_secret_id(db)}/confirmations", json={"applied_at": applied_at})
        assert response.status_code == 422 and message in response.json()["detail"]

    def test_before_first_sync_is_409(self, client: TestClient, db: Database) -> None:
        db.upsert_secret_metadata(SecretMetadataCache(vault_name="prod", engine_id="apps", secret_path="new"))
        entry = db.get_secret_metadata("prod", "apps", "new")
        assert entry is not None
        response = client.post(f"/api/v1/secrets/{entry.id}/confirmations", json={"applied_at": "2026-03-01T00:00:00Z"})
        assert response.status_code == 409

    def test_revert_brings_back_awaiting_and_the_ttl(self, client: TestClient, db: Database) -> None:
        client.post(f"/api/v1/secrets/{_secret_id(db)}/confirmations", json={"applied_at": "2026-03-01T12:00:00Z"})
        event = db.list_audit_events(event_type="secret.confirmed")[0]
        response = client.post(f"/api/v1/audit/events/{event['id']}/revert")
        assert response.status_code == 201, response.text
        assert response.json()["after"]["reverts"] == event["id"]
        secret = client.get(f"/api/v1/secrets/{_secret_id(db)}").json()
        assert secret["awaiting_confirmation"] and secret["ttl"] == "2027-01-01"
        assert client.post(f"/api/v1/audit/events/{event['id']}/revert").status_code == 409

    def test_confirmation_without_requirement_is_still_recorded(self, db: Database) -> None:
        app = FastAPI()
        app.include_router(secrets_router, prefix="/api/v1")
        with patch("chronowarden.api.secrets._get_app_dependencies", return_value=(db, _config(), MagicMock())):
            response = TestClient(app).post(
                f"/api/v1/secrets/{_secret_id(db)}/confirmations",
                json={"applied_at": _iso(datetime.now(tz=timezone.utc) - timedelta(hours=1))},
            )
        assert response.status_code == 201
        assert not response.json()["confirmation_required"] and response.json()["last_confirmation"] is not None


def test_sync_writes_the_confirmed_ttl_to_the_backend(db: Database) -> None:
    """After a confirmation, the next sync keeps the TTL counted from the applied date and writes it (ADR-021)."""
    from chronowarden.metadata import sync_secret_metadata

    db.add_confirmation(IDENTITY, 1, "2026-03-01T12:00:00.000000Z", None)
    vault = MagicMock()
    vault.get_secret_metadata.return_value = {
        "custom_metadata": {"chronowarden_severity": "default", "chronowarden_ttl": "2027-01-01"},
        "updated_time": UPDATED,
        "current_version": 1,
        "versions": {"1": {"created_time": UPDATED}},
    }
    vault.write_secret_metadata.return_value = True
    entry = sync_secret_metadata(vault, *IDENTITY, _config(), db)
    assert entry is not None and entry.ttl == "2027-03-01"
    vault.write_secret_metadata.assert_called_once()
    assert vault.write_secret_metadata.call_args.args[1]["chronowarden_ttl"] == "2027-03-01"
