# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Every route is behind the ADR-026 permission matrix."""

import re
from collections.abc import Iterator
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from chronowarden.app import app
from chronowarden.auth.tokens import digest, new_api_token
from chronowarden.config import AppConfig, AuthConfig
from chronowarden.database import Database, SecretMetadataCache

AUTH = AuthConfig.model_validate(
    {
        "mode": "oidc",
        "oidc": {"issuer": "https://idp.example.com", "client_id": "cw", "redirect_uri": "https://cw/cb"},
    }
)

# Open for probes, scrapers and the login page (ADR-015, ADR-026)
OPEN = {
    ("GET", "/api/v1"),
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/ready"),
    ("GET", "/api/v1/metrics"),
    ("GET", "/api/v1/info"),
    ("GET", "/api/v1/auth/login"),
    ("GET", "/api/v1/auth/callback"),
    ("POST", "/api/v1/auth/logout"),
}

# Reads that are admin-only: API tokens are managed by admins (ADR-026)
ADMIN_READS = {("GET", "/api/v1/auth/tokens")}


def _api_routes() -> list[tuple[str, str]]:
    """(method, path with every parameter set to 1) for each API route of the real app, from its OpenAPI schema."""
    routes = []
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api/v1"):
            routes.extend((method.upper(), re.sub(r"\{[^}]+\}", "1", path)) for method in operations)
    return sorted(routes)


@pytest.fixture
def client(db: Database) -> Iterator[TestClient]:
    deps = (db, AppConfig(auth=AUTH), MagicMock())
    with (
        patch("chronowarden.auth.dependencies._get_auth_context", return_value=(AUTH, db)),
        patch("chronowarden.app.db", db),
        patch("chronowarden.app.app_config", AppConfig(auth=AUTH)),
        patch("chronowarden.api.secrets._get_app_dependencies", return_value=deps),
    ):
        yield TestClient(app, raise_server_exceptions=False)


def _token(db: Database, role: str, owner_id: Optional[str] = None) -> dict[str, str]:
    token = new_api_token()
    db.create_api_token(
        f"id-{role}-{owner_id}",
        f"{role}-{owner_id}",
        digest(token),
        role,
        owner_id,
        "2026-01-01T00:00:00Z",
        "2099-01-01T00:00:00Z",
    )
    return {"Authorization": f"Bearer {token}"}


def test_the_open_list_is_current() -> None:
    assert OPEN <= set(_api_routes()), "an open route was renamed; update OPEN"


@pytest.mark.parametrize("method,path", [r for r in _api_routes() if r not in OPEN])
def test_every_other_route_needs_a_login(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401


@pytest.mark.parametrize("method,path", [r for r in _api_routes() if r not in OPEN and r[0] != "GET"])
def test_viewers_change_nothing(client: TestClient, db: Database, method: str, path: str) -> None:
    assert client.request(method, path, headers=_token(db, "viewer"), json={}).status_code == 403


@pytest.mark.parametrize("method,path", [r for r in _api_routes() if r not in OPEN | ADMIN_READS and r[0] == "GET"])
def test_viewers_read_everything(client: TestClient, db: Database, method: str, path: str) -> None:
    assert client.request(method, path, headers=_token(db, "viewer")).status_code not in (401, 403)


ADMIN_ONLY = [
    ("GET", "/api/v1/auth/tokens", None),
    ("POST", "/api/v1/auth/tokens", {"name": "x", "role": "viewer", "expires_in_days": 1}),
    ("POST", "/api/v1/owners/", {"name": "x", "email": "x@x"}),
    ("DELETE", "/api/v1/owners/o1", None),
    ("POST", "/api/v1/systems/", {"name": "x"}),
    ("PUT", "/api/v1/systems/s1", {"name": "y"}),
    ("PUT", "/api/v1/systems/s1/owners", {"owner_ids": []}),
    ("DELETE", "/api/v1/systems/s1", None),
    ("POST", "/api/v1/compliance/snapshots", {}),
    ("DELETE", "/api/v1/secrets/removed", None),
    ("DELETE", "/api/v1/secrets/1", None),
]


class TestOwners:
    """Owners act on what they effectively own, and nothing admin-only."""

    @pytest.fixture
    def seeded(self, db: Database) -> dict[str, Any]:
        db.create_owner("o1", "Mine", "me@example.com")
        db.create_owner("o2", "Theirs", "them@example.com")
        db.create_system("s1", "Payments", "", None, None)
        db.set_system_owners("s1", ["o1"])
        ids = {}
        for path in ("mine-direct", "mine-via-system", "theirs", "unowned"):
            db.upsert_secret_metadata(
                SecretMetadataCache(vault_name="v", engine_id="e", secret_path=path, ttl="2027-01-01")
            )
            ids[path] = db.get_secret_metadata("v", "e", path).id  # type: ignore[union-attr]
        db.set_secret_owners(("v", "e", "mine-direct"), ["o1"])
        db.set_secret_system(("v", "e", "mine-via-system"), "s1")
        db.set_secret_owners(("v", "e", "theirs"), ["o2"])
        return ids

    @pytest.mark.parametrize("method,path,body", ADMIN_ONLY)
    def test_admin_only(self, client: TestClient, db: Database, method: str, path: str, body: Any) -> None:
        response = client.request(method, path, headers=_token(db, "owner", "o1"), json=body)
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "secret,allowed", [("mine-direct", True), ("mine-via-system", True), ("theirs", False), ("unowned", False)]
    )
    def test_secret_writes(
        self, client: TestClient, db: Database, seeded: dict[str, int], secret: str, allowed: bool
    ) -> None:
        response = client.put(
            f"/api/v1/secrets/{seeded[secret]}/owners",
            headers=_token(db, "owner", "o1"),
            json={"owner_ids": ["o1", "o2"]},
        )
        assert response.status_code == (200 if allowed else 403), response.text
        if allowed:
            assert db.list_audit_events(event_type="secret.owners")[0]["actor"] == "token:owner-o1"

    def test_admin_writes_any_secret(self, client: TestClient, db: Database, seeded: dict[str, int]) -> None:
        response = client.put(
            f"/api/v1/secrets/{seeded['unowned']}/system", headers=_token(db, "admin"), json={"system_id": "s1"}
        )
        assert response.status_code == 200

    def test_own_owner_record(self, client: TestClient, db: Database, seeded: dict[str, int]) -> None:
        headers = _token(db, "owner", "o1")
        assert client.put("/api/v1/owners/o1", headers=headers, json={"name": "Renamed"}).status_code == 200
        assert client.put("/api/v1/owners/o1", headers=headers, json={"email": "x@x"}).status_code == 403
        assert client.put("/api/v1/owners/o1", headers=headers, json={"idp_group": "g"}).status_code == 403
        assert client.put("/api/v1/owners/o2", headers=headers, json={"name": "Mine now"}).status_code == 403
        route = {"type": "webhook", "address": "https://hooks.example.com/x"}
        assert client.post("/api/v1/owners/o1/routes", headers=headers, json=route).status_code == 201
        assert client.post("/api/v1/owners/o2/routes", headers=headers, json=route).status_code == 403

    def test_revert_on_own_secrets_only(self, client: TestClient, db: Database, seeded: dict[str, int]) -> None:
        admin = _token(db, "admin")
        for secret in ("mine-direct", "theirs"):
            client.put(f"/api/v1/secrets/{seeded[secret]}/system", headers=admin, json={"system_id": "s1"})
        events = {e["secret_path"]: e["id"] for e in db.list_audit_events(event_type="secret.system")}
        headers = _token(db, "owner", "o1")
        assert client.post(f"/api/v1/audit/events/{events['theirs']}/revert", headers=headers).status_code == 403
        assert client.post(f"/api/v1/audit/events/{events['mine-direct']}/revert", headers=headers).status_code == 201

    def test_owner_may_sync(self, client: TestClient, db: Database) -> None:
        response = client.post("/api/v1/sync/vault/nope", headers=_token(db, "owner", "o1"))
        assert response.status_code not in (401, 403)
