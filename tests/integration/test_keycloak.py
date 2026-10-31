# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""The OIDC login against a real Keycloak (ADR-015, ADR-026). Run with: pytest -m integration."""

import html
import re
from collections.abc import Iterator
from typing import NamedTuple
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.core.container import DockerContainer

from chronowarden.api import auth as auth_api
from chronowarden.config import AuthConfig
from chronowarden.database import Database
from devenv import keycloak

pytestmark = pytest.mark.integration

APP = "http://testserver"  # TestClient's host: Keycloak redirects there, the test follows by hand
REDIRECT_URI = f"{APP}/api/v1/auth/callback"


class Realm(NamedTuple):
    """A Keycloak with the dev realm, and the auth config pointing at it."""

    auth: AuthConfig
    passwords: dict[str, str]


@pytest.fixture(scope="module")
def realm() -> Iterator[Realm]:
    admin_password = keycloak.random_password()
    container = (
        DockerContainer(keycloak.IMAGE)
        .with_env("KC_BOOTSTRAP_ADMIN_USERNAME", keycloak.BOOTSTRAP_ADMIN)
        .with_env("KC_BOOTSTRAP_ADMIN_PASSWORD", admin_password)
        .with_exposed_ports(keycloak.PORT)
        .with_command("start-dev")
    )
    with container:
        idp = keycloak.Keycloak(
            "keycloak", int(container.get_exposed_port(keycloak.PORT)), container.get_container_host_ip()
        )
        keycloak.wait_ready(idp)
        client_secret = keycloak.random_password()
        passwords = {user: keycloak.random_password() for user in keycloak.usernames()}
        keycloak.import_realm(idp, admin_password, keycloak.realm(REDIRECT_URI, client_secret, passwords))
        yield Realm(AuthConfig.model_validate(keycloak.oidc_auth(idp, client_secret, REDIRECT_URI)), passwords)


@pytest.fixture
def client(realm: Realm, db: Database) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(auth_api.router, prefix="/api/v1")
    with (
        patch("chronowarden.api.auth._get_app_dependencies", return_value=(realm.auth, db)),
        patch("chronowarden.auth.dependencies._get_auth_context", return_value=(realm.auth, db)),
        patch.object(auth_api, "_client", None),  # discovery is per realm (port), not shared between modules
    ):
        yield TestClient(app, base_url=APP, follow_redirects=False)


def _log_in(client: TestClient, user: str, password: str) -> requests.Response:
    """Drive the authorization code flow as a browser would; returns Keycloak's answer to the login form."""
    start = client.get("/api/v1/auth/login")
    assert start.status_code == 302
    browser = requests.Session()
    form = browser.get(start.headers["location"], timeout=30)
    assert form.ok, form.text[:300]
    for cookie in browser.cookies:
        cookie.secure = False  # browsers send Keycloak's Secure cookies to http://localhost; requests doesn't
    action = html.unescape(re.search(r'action="([^"]+)"', form.text).group(1))
    return browser.post(action, data={"username": user, "password": password}, allow_redirects=False, timeout=30)


def _finish(client: TestClient, answer: requests.Response) -> None:
    assert answer.status_code == 302, re.sub(
        r"\s+", " ", re.sub(r"<script.*?</script>|<[^>]+>", " ", answer.text, flags=re.S)
    )[:400]
    location = urlsplit(answer.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT_URI
    assert client.get(f"{location.path}?{location.query}").status_code == 303


@pytest.mark.parametrize("user", ["admin", "owner", "viewer"])
def test_each_user_gets_its_role(client: TestClient, realm: Realm, user: str) -> None:
    _finish(client, _log_in(client, user, realm.passwords[user]))
    me = client.get("/api/v1/auth/me").json()
    assert (me["name"], me["role"], me["email"], me["kind"]) == (user, user, f"{user}@chronowarden.test", "session")


def test_logout_ends_the_session(client: TestClient, realm: Realm) -> None:
    _finish(client, _log_in(client, "viewer", realm.passwords["viewer"]))
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_wrong_password_never_reaches_chronowarden(client: TestClient, realm: Realm) -> None:
    answer = _log_in(client, "admin", "wrong")
    assert answer.status_code == 200 and "location" not in answer.headers  # the login form again
    assert client.get("/api/v1/auth/me").status_code == 401
