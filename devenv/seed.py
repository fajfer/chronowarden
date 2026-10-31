# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Seed a run's database with what the UI needs to be exercised: an owner, its system, a webhook route."""

import base64
import secrets
from pathlib import Path
from typing import Optional

from chronowarden.database import Database
from chronowarden.models.owner import NotificationRouteCreate

OWNER_ID = "team-owner"
OWNER_EMAIL = "owner@chronowarden.test"  # the Keycloak `owner` user
OWNER_GROUP = "teams"
SYSTEM_ID = "payments"
ROUTE_ID = "team-owner-receiver"
# Secrets the seeded owner and system get, as (vault, engine, path) of the dev seed data
OWNED_SECRETS = (("dev-openbao", "apps", "secret-1"), ("dev-vault", "apps", "secret-1"))


def signing_secret() -> str:
    """A Standard Webhooks signing secret (`whsec_` + base64 of 24 random bytes)."""
    return "whsec_" + base64.b64encode(secrets.token_bytes(24)).decode()


def seed_database(db_path: Path, receiver_url: Optional[str]) -> Optional[str]:
    """
    Create the owner (matching the `owner` user by email and IdP group), a system it owns and two secrets
    assigned to both; with `receiver_url`, a signed webhook route of the owner to it.

    Returns:
        The route's signing secret, or None without a receiver.
    """
    db = Database(db_path)
    db.connect()
    try:
        db.create_owner(OWNER_ID, "Team Owner", OWNER_EMAIL, idp_group=OWNER_GROUP)
        db.create_system(SYSTEM_ID, "Payments", "Seeded by dev-setup.py", None, None)
        db.set_system_owners(SYSTEM_ID, [OWNER_ID])
        for identity in OWNED_SECRETS:
            db.set_secret_system(identity, SYSTEM_ID)
            db.set_secret_owners(identity, [OWNER_ID])
        if receiver_url is None:
            return None
        route = NotificationRouteCreate(type="webhook", address=receiver_url)  # validated like the API does
        db.create_notification_route(ROUTE_ID, OWNER_ID, route.type, route.address, route.message_template)
        secret = signing_secret()
        db.set_route_signing_secret(ROUTE_ID, secret)
        return secret
    finally:
        db.close()
