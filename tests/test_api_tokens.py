# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the API token endpoints (ADR-026)."""

import json
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.api.auth import router
from chronowarden.config import AuthConfig
from chronowarden.database import Database

AUTH = AuthConfig.model_validate(
    {"mode": "proxy", "proxy": {"trusted_proxies": ["10.0.0.0/8"]}, "token_max_lifetime": "90d"}
)


@pytest.fixture
def client(db: Database) -> Iterator[TestClient]:
    """An admin in `none` mode (conftest) managing tokens checked against AUTH's limits."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with patch("chronowarden.api.auth._get_app_dependencies", return_value=(AUTH, db)):
        yield TestClient(app)


def test_create_list_use_and_revoke(client: TestClient, db: Database) -> None:
    created = client.post("/api/v1/auth/tokens", json={"name": "ci", "role": "viewer", "expires_in_days": 30})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["token"].startswith("cwt_") and body["role"] == "viewer" and body["revoked_at"] is None
    listed = client.get("/api/v1/auth/tokens").json()
    assert [t["name"] for t in listed] == ["ci"] and "token" not in listed[0]

    with patch("chronowarden.auth.dependencies._get_auth_context", return_value=(AUTH, db)):
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
        assert me.json()["name"] == "ci" and me.json()["kind"] == "token"

    revoked = client.delete(f"/api/v1/auth/tokens/{body['id']}")
    assert revoked.status_code == 200 and revoked.json()["revoked_at"] is not None
    assert client.delete(f"/api/v1/auth/tokens/{body['id']}").status_code == 404

    with patch("chronowarden.auth.dependencies._get_auth_context", return_value=(AUTH, db)):
        assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['token']}"}).status_code == 401

    events = {e["event_type"]: e for e in db.list_audit_events(subject=f"token:{body['id']}")}
    assert set(events) == {"token.created", "token.revoked"}
    stored = events["token.created"]["after"] + events["token.revoked"]["before"]
    assert body["token"] not in stored and "hash" not in stored
    assert json.loads(events["token.created"]["after"])["role"] == "viewer"


def test_owner_tokens(client: TestClient, db: Database) -> None:
    db.create_owner("o1", "Team", "t@x")
    ok = client.post(
        "/api/v1/auth/tokens", json={"name": "team", "role": "owner", "owner_id": "o1", "expires_in_days": 1}
    )
    assert ok.status_code == 201 and ok.json()["owner_id"] == "o1"


@pytest.mark.parametrize(
    "body,status,message",
    [
        ({"name": "x", "role": "owner", "expires_in_days": 1}, 422, "owner_id is required"),
        ({"name": "x", "role": "admin", "owner_id": "o1", "expires_in_days": 1}, 422, "only for it"),
        ({"name": "x", "role": "owner", "owner_id": "nope", "expires_in_days": 1}, 422, "Unknown owner"),
        ({"name": "x", "role": "viewer", "expires_in_days": 91}, 422, "at most 90 days"),
        ({"name": "x", "role": "viewer", "expires_in_days": 0}, 422, "greater than or equal to 1"),
        ({"name": "", "role": "viewer", "expires_in_days": 1}, 422, "at least 1 character"),
        ({"name": "x", "role": "root", "expires_in_days": 1}, 422, "admin"),
    ],
)
def test_invalid(client: TestClient, db: Database, body: dict, status: int, message: str) -> None:
    db.create_owner("o1", "Team", "t@x")
    response = client.post("/api/v1/auth/tokens", json=body)
    assert response.status_code == status and message in response.text


def test_names_are_unique(client: TestClient) -> None:
    body = {"name": "ci", "role": "viewer", "expires_in_days": 1}
    assert client.post("/api/v1/auth/tokens", json=body).status_code == 201
    assert client.post("/api/v1/auth/tokens", json=body).status_code == 409
