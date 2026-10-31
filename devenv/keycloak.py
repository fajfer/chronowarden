# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""A dev Keycloak with a `chronowarden` realm: one client and an admin, an owner and a viewer user."""

import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from requests.exceptions import RequestException

from devenv.runtime import ContainerRuntimeError

IMAGE = "quay.io/keycloak/keycloak:26.8.1"
PORT = 8080  # inside the container
DEV_PORT = 8180  # published by the dev run
REALM_TEMPLATE = Path(__file__).parent / "keycloak" / "realm.json"
REALM = "chronowarden"
CLIENT_ID = "chronowarden"
BOOTSTRAP_ADMIN = "bootstrap"

# The groups of the realm template, mapped to Chronowarden roles in the written config
ROLE_GROUPS = {"admin": ["cw-admins"], "owner": ["teams"], "viewer": ["auditors"]}


@dataclass(frozen=True)
class Keycloak:
    """A dev Keycloak container and where it's reachable."""

    container: str
    host_port: int
    host: str = "localhost"

    @property
    def address(self) -> str:
        """Base URL on the host."""
        return f"http://{self.host}:{self.host_port}"

    @property
    def issuer(self) -> str:
        """The realm's issuer, as Keycloak puts it into tokens for clients on this host."""
        return f"{self.address}/realms/{REALM}"


def random_password() -> str:
    """A throwaway dev password."""
    return secrets.token_urlsafe(12)


def realm(redirect_uri: str, client_secret: str, passwords: dict[str, str]) -> dict[str, Any]:
    """
    The realm template filled in for one run.

    Args:
        redirect_uri: Chronowarden's callback URL, the only one the client accepts.
        client_secret: The client's secret.
        passwords: Password per username in the template.
    """
    data = json.loads(REALM_TEMPLATE.read_text())
    client = data["clients"][0]
    client["secret"] = client_secret
    client["redirectUris"] = [redirect_uri]
    for user in data["users"]:
        user["enabled"] = True
        user["emailVerified"] = True
        user["credentials"] = [{"type": "password", "value": passwords[user["username"]], "temporary": False}]
    return data


def usernames() -> list[str]:
    """The users the realm template defines."""
    return [user["username"] for user in json.loads(REALM_TEMPLATE.read_text())["users"]]


def wait_ready(keycloak: Keycloak, timeout: float = 180) -> None:
    """
    Wait until Keycloak serves its master realm (start-dev takes 10-60 s).

    Raises:
        ContainerRuntimeError: If it doesn't within `timeout` seconds.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if requests.get(f"{keycloak.address}/realms/master", timeout=5).ok:
                return
        except RequestException:
            pass  # not up yet
        time.sleep(2)
    raise ContainerRuntimeError(f"{keycloak.container} didn't become ready at {keycloak.address} within {timeout:.0f}s")


def import_realm(keycloak: Keycloak, admin_password: str, realm_data: dict[str, Any]) -> None:
    """
    Create the realm through the admin API, logged in as the bootstrap admin.

    Raises:
        ContainerRuntimeError: If Keycloak refuses the login or the realm.
    """
    try:
        token_response = requests.post(
            f"{keycloak.address}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": BOOTSTRAP_ADMIN,
                "password": admin_password,
            },
            timeout=30,
        )
        token_response.raise_for_status()
        token = token_response.json()["access_token"]
        response = requests.post(
            f"{keycloak.address}/admin/realms",
            json=realm_data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        response.raise_for_status()
    except RequestException as exc:
        raise ContainerRuntimeError(f"Creating the {REALM} realm in {keycloak.container} failed: {exc}") from None


def oidc_auth(keycloak: Keycloak, client_secret: str, redirect_uri: str) -> dict[str, Any]:
    """The `auth` config section for logging in against this Keycloak."""
    return {
        "mode": "oidc",
        "oidc": {
            "issuer": keycloak.issuer,
            "client_id": CLIENT_ID,
            "client_secret": client_secret,  # dev only; real configs use client_secret_env or _file
            "redirect_uri": redirect_uri,
        },
        "roles": ROLE_GROUPS,
    }
