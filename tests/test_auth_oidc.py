# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the OIDC login against a fake identity provider (ADR-015, ADR-026)."""

import time
from collections.abc import Iterator
from typing import Any, Optional
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import RSAKey

from chronowarden.api.auth import router, safe_next
from chronowarden.auth.oidc import OidcClient, OidcError
from chronowarden.auth.resolve import SESSION_COOKIE
from chronowarden.auth.tokens import digest
from chronowarden.config import AuthConfig
from chronowarden.database import Database
from chronowarden.timestamps import utc_timestamp

ISSUER = "https://idp.example.com/realms/main"
AUTH = AuthConfig.model_validate(
    {
        "mode": "oidc",
        "roles": {"admin": ["cw-admins"], "owner": ["teams"]},
        "oidc": {
            "issuer": ISSUER,
            "client_id": "chronowarden",
            "client_secret": "s3cret",
            "redirect_uri": "https://cw.example.com/api/v1/auth/callback",
        },
    }
)


class FakeIdp:
    """Discovery, keys and a token endpoint that returns whatever ID token the test sets."""

    def __init__(self) -> None:
        self.key = RSAKey.generate_key(2048, parameters={"kid": "k1"})
        self.discovery = {
            "issuer": ISSUER,
            "authorization_endpoint": f"{ISSUER}/auth",
            "token_endpoint": f"{ISSUER}/token",
            "jwks_uri": f"{ISSUER}/certs",
            "id_token_signing_alg_values_supported": ["RS256"],
        }
        self.claims: dict[str, Any] = {}
        self.exchanges: list[dict[str, Any]] = []

    def sign(self, claims: dict[str, Any], key: Optional[RSAKey] = None) -> str:
        key = key or self.key
        return jwt.encode({"alg": "RS256", "kid": key.kid}, claims, key)

    def get_json(self, url: str) -> dict[str, Any]:
        if url.endswith("/.well-known/openid-configuration"):
            return self.discovery
        if url == self.discovery["jwks_uri"]:
            return {"keys": [self.key.as_dict(private=False)]}
        raise OidcError(f"unexpected {url}")

    def fetch_token(self, url: str, **kwargs: Any) -> dict[str, Any]:
        self.exchanges.append({"url": url, **kwargs})
        return {"access_token": "at", "id_token": self.sign(self.claims)}


def _claims(nonce: str, **overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": "chronowarden",
        "sub": "u-1",
        "iat": now,
        "exp": now + 300,
        "nonce": nonce,
        "preferred_username": "alice",
        "email": "alice@example.com",
        "email_verified": True,
        "groups": ["teams"],
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


@pytest.fixture
def idp() -> Iterator[FakeIdp]:
    fake = FakeIdp()
    with (
        patch.object(OidcClient, "_get_json", lambda self, url: fake.get_json(url)),
        patch(
            "chronowarden.auth.oidc.OAuth2Session.fetch_token",
            lambda self, url, **kwargs: fake.fetch_token(url, **kwargs),
        ),
    ):
        yield fake


@pytest.fixture
def client(db: Database) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with (
        patch("chronowarden.api.auth._get_app_dependencies", return_value=(AUTH, db)),
        patch("chronowarden.auth.dependencies._get_auth_context", return_value=(AUTH, db)),
    ):
        yield TestClient(app, base_url="https://cw.example.com", follow_redirects=False)


def _start(client: TestClient, next_path: str = "/secrets") -> dict[str, str]:
    response = client.get("/api/v1/auth/login", params={"next": next_path})
    assert response.status_code == 302
    query = {k: v[0] for k, v in parse_qs(urlsplit(response.headers["location"]).query).items()}
    return query


class TestLogin:
    def test_redirects_to_the_idp_with_pkce(self, client: TestClient, idp: FakeIdp, db: Database) -> None:
        query = _start(client)
        assert query["response_type"] == "code" and query["client_id"] == "chronowarden"
        assert query["code_challenge_method"] == "S256" and len(query["code_challenge"]) == 43
        assert query["redirect_uri"] == "https://cw.example.com/api/v1/auth/callback"
        assert set(query["scope"].split()) == {"openid", "profile", "email"}
        assert query["state"] and query["nonce"]

    def test_full_login(self, client: TestClient, idp: FakeIdp, db: Database) -> None:
        db.create_owner("o1", "Alice", "ALICE@example.com")
        query = _start(client)
        idp.claims = _claims(query["nonce"])
        response = client.get("/api/v1/auth/callback", params={"state": query["state"], "code": "c0de"})
        assert response.status_code == 303 and response.headers["location"] == "/secrets"
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie and "Max-Age=43200" in cookie
        assert idp.exchanges[0]["code"] == "c0de" and idp.exchanges[0]["code_verifier"]
        session_id = response.cookies[SESSION_COOKIE]
        session = db.get_session(digest(session_id), utc_timestamp())
        assert session is not None and (session["name"], session["role"]) == ("alice", "owner")
        me = client.get("/api/v1/auth/me").json()
        assert me == {
            "auth_mode": "oidc",
            "name": "alice",
            "email": "alice@example.com",
            "role": "owner",
            "kind": "session",
            "owner_ids": ["o1"],
        }

    def test_state_is_used_once(self, client: TestClient, idp: FakeIdp) -> None:
        query = _start(client)
        idp.claims = _claims(query["nonce"])
        client.get("/api/v1/auth/callback", params={"state": query["state"], "code": "c"})
        again = client.get("/api/v1/auth/callback", params={"state": query["state"], "code": "c"})
        assert again.headers["location"] == "/login?error=expired"

    @pytest.mark.parametrize("state", ["", "forged"])
    def test_unknown_state(self, client: TestClient, idp: FakeIdp, state: str) -> None:
        response = client.get("/api/v1/auth/callback", params={"state": state, "code": "c"})
        assert response.headers["location"] == "/login?error=expired" and not idp.exchanges

    def test_provider_refused(self, client: TestClient, idp: FakeIdp) -> None:
        query = _start(client)
        response = client.get("/api/v1/auth/callback", params={"state": query["state"], "error": "access_denied"})
        assert response.headers["location"] == "/login?error=denied"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"nonce": "other"},
            {"iss": "https://evil.example.com"},
            {"aud": "another-client"},
            {"aud": ["chronowarden", "other"], "azp": "other"},
            {"exp": int(time.time()) - 3600},
            {"sub": None},
        ],
    )
    def test_invalid_id_token(self, client: TestClient, idp: FakeIdp, db: Database, overrides: dict) -> None:
        query = _start(client)
        claims = _claims(query["nonce"])
        claims.update(overrides)
        idp.claims = {k: v for k, v in claims.items() if v is not None}
        response = client.get("/api/v1/auth/callback", params={"state": query["state"], "code": "c"})
        assert response.headers["location"] == "/login?error=failed"
        assert SESSION_COOKIE not in response.cookies

    def test_wrong_signing_key(self, client: TestClient, idp: FakeIdp) -> None:
        query = _start(client)
        forged = idp.sign(_claims(query["nonce"]), RSAKey.generate_key(2048, parameters={"kid": "k1"}))
        with patch.object(idp, "fetch_token", lambda url, **kw: {"id_token": forged}):
            response = client.get("/api/v1/auth/callback", params={"state": query["state"], "code": "c"})
        assert response.headers["location"] == "/login?error=failed"

    def test_no_role(self, client: TestClient, idp: FakeIdp, db: Database) -> None:
        query = _start(client)
        idp.claims = _claims(query["nonce"], groups=["strangers"])
        response = client.get("/api/v1/auth/callback", params={"state": query["state"], "code": "c"})
        assert response.headers["location"] == "/login?error=no_role"

    def test_unverified_email_matches_no_owner(self, client: TestClient, idp: FakeIdp, db: Database) -> None:
        db.create_owner("o1", "Alice", "alice@example.com")
        query = _start(client)
        idp.claims = _claims(query["nonce"], email_verified=False)
        client.get("/api/v1/auth/callback", params={"state": query["state"], "code": "c"})
        me = client.get("/api/v1/auth/me").json()
        assert me["email"] is None and me["owner_ids"] == []

    def test_logout_ends_the_session(self, client: TestClient, idp: FakeIdp) -> None:
        query = _start(client)
        idp.claims = _claims(query["nonce"])
        session_id = client.get("/api/v1/auth/callback", params={"state": query["state"], "code": "c"}).cookies[
            SESSION_COOKIE
        ]
        response = client.post("/api/v1/auth/logout")
        assert response.json() == {"logout_url": None}
        assert SESSION_COOKIE not in client.cookies
        client.cookies.set(SESSION_COOKIE, session_id)  # a copy of the cookie is useless after logout
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_discovery_must_name_the_issuer(self, client: TestClient, idp: FakeIdp) -> None:
        idp.discovery["issuer"] = "https://evil.example.com"
        with patch("chronowarden.api.auth._client", None):
            assert client.get("/api/v1/auth/login").status_code == 502


class TestOutsideOidcMode:
    def test_login_is_404(self, db: Database) -> None:
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        with patch("chronowarden.api.auth._get_app_dependencies", return_value=(AuthConfig(mode="none"), db)):
            client = TestClient(app)
            assert client.get("/api/v1/auth/login").status_code == 404
            assert client.get("/api/v1/auth/callback").status_code == 404

    def test_proxy_logout_url(self, db: Database) -> None:
        auth = AuthConfig.model_validate(
            {"mode": "proxy", "proxy": {"trusted_proxies": ["10.0.0.0/8"], "logout_url": "/oauth2/sign_out"}}
        )
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        with patch("chronowarden.api.auth._get_app_dependencies", return_value=(auth, db)):
            assert TestClient(app).post("/api/v1/auth/logout").json() == {"logout_url": "/oauth2/sign_out"}


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/secrets?x=1", "/secrets?x=1"),
        (None, "/"),
        ("https://evil.example.com", "/"),
        ("//evil.example.com", "/"),
        ("/\\evil.example.com", "/"),
        ("secrets", "/"),
    ],
)
def test_safe_next(path: Optional[str], expected: str) -> None:
    assert safe_next(path) == expected
