# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for principals, roles, credential resolution and the auth dependencies (ADR-015, ADR-026)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from chronowarden.auth import ANONYMOUS_ADMIN, Principal, authenticated, request_actor, require_role, role_for
from chronowarden.auth.resolve import SESSION_COOKIE, resolve_principal
from chronowarden.auth.tokens import TOKEN_PREFIX, digest, new_api_token, new_session_id
from chronowarden.config import AuthConfig
from chronowarden.database import Database
from chronowarden.timestamps import utc_timestamp

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
ROLES = {"admin": ["cw-admins"], "owner": ["teams"], "viewer": ["auditors"]}
OIDC = AuthConfig.model_validate(
    {
        "mode": "oidc",
        "roles": ROLES,
        "oidc": {"issuer": "https://idp.example.com", "client_id": "cw", "redirect_uri": "https://cw/cb"},
    }
)
PROXY = AuthConfig.model_validate({"mode": "proxy", "roles": ROLES, "proxy": {"trusted_proxies": ["10.0.0.0/8"]}})


def _request(headers: Optional[dict[str, str]] = None, peer: str = "10.1.2.3", cookies: str = "") -> Request:
    """A bare ASGI request with the given headers, cookie header and TCP peer."""
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if cookies:
        raw.append((b"cookie", cookies.encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw, "client": (peer, 1234)})


def _token(
    db: Database, role: str = "viewer", owner_id: Optional[str] = None, expires: timedelta = timedelta(days=1)
) -> str:
    token = new_api_token()
    db.create_api_token(
        f"id-{role}", f"{role}-token", digest(token), role, owner_id, utc_timestamp(NOW), utc_timestamp(NOW + expires)
    )
    return token


class TestPrincipal:
    def test_roles_are_ordered(self) -> None:
        owner = Principal(name="a", role="owner", kind="session")
        assert owner.at_least("viewer") and owner.at_least("owner") and not owner.at_least("admin")
        assert not Principal(name="a", role=None, kind="proxy").at_least("viewer")

    def test_acts_for(self) -> None:
        owner = Principal(name="a", role="owner", kind="session", owner_ids=frozenset({"o1"}))
        assert owner.acts_for(["o2", "o1"]) and not owner.acts_for(["o2"]) and not owner.acts_for([])
        assert ANONYMOUS_ADMIN.acts_for([])
        viewer = Principal(name="v", role="viewer", kind="session", owner_ids=frozenset({"o1"}))
        assert not viewer.acts_for(["o1"]), "a matching email gives rights only with the owner role"

    def test_actor(self) -> None:
        assert Principal(name="alice", role="owner", kind="session", email="a@x").actor == "user:a@x"
        assert Principal(name="alice", role="owner", kind="proxy").actor == "user:alice"
        assert Principal(name="ci", role="viewer", kind="token").actor == "token:ci"
        assert ANONYMOUS_ADMIN.actor is None

    @pytest.mark.parametrize(
        "groups,default,expected",
        [
            (["teams", "cw-admins"], None, "admin"),
            (["teams"], None, "owner"),
            (["auditors", "x"], None, "viewer"),
            (["x"], None, None),
            ([], "viewer", "viewer"),
        ],
    )
    def test_role_for(self, groups: list[str], default: Optional[str], expected: Optional[str]) -> None:
        auth = OIDC.model_copy(update={"default_role": default})
        assert role_for(groups, auth) == expected


class TestTokens:
    def test_shapes(self) -> None:
        token = new_api_token()
        assert token.startswith(TOKEN_PREFIX) and len(token) > 40 and new_api_token() != token
        assert len(digest(token)) == 64 and digest(token) == digest(token)
        assert new_session_id() != new_session_id()


class TestResolve:
    def test_none_mode_is_anonymous_admin(self, db: Database) -> None:
        assert resolve_principal(_request(), AuthConfig(mode="none"), db, NOW) is ANONYMOUS_ADMIN

    def test_api_token(self, db: Database) -> None:
        db.create_owner("o1", "Team", "t@x")
        token = _token(db, "owner", "o1")
        principal = resolve_principal(_request({"Authorization": f"Bearer {token}"}), OIDC, db, NOW)
        assert principal == Principal(name="owner-token", role="owner", kind="token", owner_ids=frozenset({"o1"}))
        assert db.list_api_tokens()[0]["last_used_at"] == utc_timestamp(NOW)

    def test_last_used_is_written_at_most_every_five_minutes(self, db: Database) -> None:
        token = _token(db)
        request = _request({"Authorization": f"Bearer {token}"})
        resolve_principal(request, OIDC, db, NOW)
        resolve_principal(request, OIDC, db, NOW + timedelta(minutes=4))
        assert db.list_api_tokens()[0]["last_used_at"] == utc_timestamp(NOW)
        resolve_principal(request, OIDC, db, NOW + timedelta(minutes=6))
        assert db.list_api_tokens()[0]["last_used_at"] == utc_timestamp(NOW + timedelta(minutes=6))

    @pytest.mark.parametrize("credential", ["cwt_unknown", "not-a-token", ""])
    def test_bad_token(self, db: Database, credential: str) -> None:
        assert resolve_principal(_request({"Authorization": f"Bearer {credential}"}), OIDC, db, NOW) is None

    def test_expired_and_revoked_tokens(self, db: Database) -> None:
        token = _token(db, expires=timedelta(hours=1))
        request = _request({"Authorization": f"Bearer {token}"})
        assert resolve_principal(request, OIDC, db, NOW + timedelta(hours=2)) is None
        assert resolve_principal(request, OIDC, db, NOW) is not None
        db.revoke_api_token("id-viewer", utc_timestamp(NOW))
        assert resolve_principal(request, OIDC, db, NOW) is None

    def test_bad_token_does_not_fall_back_to_the_session(self, db: Database) -> None:
        session_id = new_session_id()
        db.create_session(
            digest(session_id), "alice", None, [], "admin", utc_timestamp(NOW), utc_timestamp(NOW + timedelta(hours=1))
        )
        request = _request({"Authorization": "Bearer cwt_wrong"}, cookies=f"{SESSION_COOKIE}={session_id}")
        assert resolve_principal(request, OIDC, db, NOW) is None

    def test_session(self, db: Database) -> None:
        db.create_owner("o1", "Alice", "alice@example.com")
        db.create_owner("o2", "Team", "team@example.com", idp_group="teams")
        session_id = new_session_id()
        db.create_session(
            digest(session_id),
            "alice",
            "alice@example.com",
            ["teams"],
            "owner",
            utc_timestamp(NOW),
            utc_timestamp(NOW + timedelta(hours=12)),
        )
        principal = resolve_principal(_request(cookies=f"{SESSION_COOKIE}={session_id}"), OIDC, db, NOW)
        assert principal is not None and principal.kind == "session" and principal.role == "owner"
        assert principal.owner_ids == {"o1", "o2"} and principal.actor == "user:alice@example.com"
        assert resolve_principal(_request(cookies=f"{SESSION_COOKIE}=forged"), OIDC, db, NOW) is None
        assert resolve_principal(_request(), OIDC, db, NOW) is None
        later = NOW + timedelta(hours=12)
        assert resolve_principal(_request(cookies=f"{SESSION_COOKIE}={session_id}"), OIDC, db, later) is None

    def test_proxy_headers_from_a_trusted_peer(self, db: Database) -> None:
        db.create_owner("o1", "Bob", "bob@example.com")
        headers = {"X-Forwarded-User": "bob", "X-Forwarded-Email": "bob@example.com", "X-Forwarded-Groups": "x, teams,"}
        principal = resolve_principal(_request(headers), PROXY, db, NOW)
        assert principal == Principal(
            name="bob",
            role="owner",
            kind="proxy",
            email="bob@example.com",
            groups=("x", "teams"),
            owner_ids=frozenset({"o1"}),
        )

    def test_ipv4_mapped_peer_is_trusted(self, db: Database) -> None:
        principal = resolve_principal(_request({"X-Forwarded-User": "bob"}, peer="::ffff:10.0.0.1"), PROXY, db, NOW)
        assert principal is not None and principal.name == "bob"

    def test_proxy_headers_from_anyone_else_are_ignored(self, db: Database, caplog: pytest.LogCaptureFixture) -> None:
        headers = {"X-Forwarded-User": "mallory", "X-Forwarded-Groups": "cw-admins"}
        assert resolve_principal(_request(headers, peer="192.168.1.5"), PROXY, db, NOW) is None
        assert resolve_principal(_request(headers, peer="not-an-ip"), PROXY, db, NOW) is None
        assert "not in auth.proxy.trusted_proxies" in caplog.text

    def test_proxy_without_user_or_role(self, db: Database) -> None:
        assert resolve_principal(_request({"X-Forwarded-Email": "a@x"}), PROXY, db, NOW) is None
        principal = resolve_principal(_request({"X-Forwarded-User": "eve"}), PROXY, db, NOW)
        assert principal is not None and principal.role is None

    def test_proxy_accepts_api_tokens(self, db: Database) -> None:
        token = _token(db, "admin")
        principal = resolve_principal(
            _request({"Authorization": f"Bearer {token}"}, peer="192.168.1.5"), PROXY, db, NOW
        )
        assert principal is not None and principal.role == "admin"


def test_images_keep_the_tcp_peer() -> None:
    """Uvicorn must not replace the peer from X-Forwarded-For, or anyone could pose as a trusted proxy (ADR-026)."""
    dockerfile = (Path(__file__).parent.parent / "Dockerfile").read_text()
    starts = [line for line in dockerfile.splitlines() if line.startswith(("CMD", "ENTRYPOINT")) and "uvicorn" in line]
    assert len(starts) == 3 and all("--no-proxy-headers" in line for line in starts)


class TestDependencies:
    """`authenticated` and `require_role` on a tiny app."""

    @staticmethod
    def _client(peer: str = "testclient") -> TestClient:
        app = FastAPI()

        @app.get("/read")
        async def read(request: Request, principal: Principal = Depends(authenticated)) -> dict:
            return {"name": principal.name, "actor": request_actor(request)}

        @app.post("/admin", dependencies=[Depends(require_role("admin"))])
        async def admin_only() -> dict:
            return {}

        return TestClient(app, client=(peer, 50000))

    def test_unauthenticated_is_401(self, db: Database) -> None:
        with patch("chronowarden.auth.dependencies._get_auth_context", return_value=(OIDC, db)):
            response = self._client().get("/read")
        assert response.status_code == 401 and response.headers["www-authenticate"] == "Bearer"

    def test_without_a_role_is_403(self, db: Database) -> None:
        with patch("chronowarden.auth.dependencies._get_auth_context", return_value=(PROXY, db)):
            response = self._client(peer="10.0.0.1").get("/read", headers={"X-Forwarded-User": "eve"})
        assert response.status_code == 403 and "no Chronowarden role" in response.json()["detail"]

    def test_without_config_is_503(self, db: Database) -> None:
        with patch("chronowarden.auth.dependencies._get_auth_context", return_value=(None, db)):
            assert self._client().get("/read").status_code == 503

    def test_roles(self, db: Database) -> None:
        viewer, admin = _token(db, "viewer"), _token(db, "admin")
        with patch("chronowarden.auth.dependencies._get_auth_context", return_value=(OIDC, db)):
            client = self._client()
            read = client.get("/read", headers={"Authorization": f"Bearer {viewer}"})
            assert read.json() == {"name": "viewer-token", "actor": "token:viewer-token"}
            assert client.post("/admin", headers={"Authorization": f"Bearer {viewer}"}).status_code == 403
            assert client.post("/admin", headers={"Authorization": f"Bearer {admin}"}).status_code == 200

    def test_none_mode(self, db: Database) -> None:
        with patch("chronowarden.auth.dependencies._get_auth_context", return_value=(AuthConfig(mode="none"), db)):
            client = self._client()
            assert client.get("/read").json() == {"name": "anonymous", "actor": None}
            assert client.post("/admin").status_code == 200
