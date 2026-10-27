# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Turn a request into a Principal: API token, session cookie, proxy headers, or nobody (ADR-015, ADR-026)."""

import ipaddress
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from starlette.requests import Request

from chronowarden.auth.principal import ANONYMOUS_ADMIN, Principal, role_for
from chronowarden.auth.tokens import TOKEN_PREFIX, digest
from chronowarden.config import AuthConfig, ProxyConfig
from chronowarden.timestamps import utc_timestamp

logger = logging.getLogger("uvicorn.error")

SESSION_COOKIE = "chronowarden_session"

# last_used_at is a hint for admins, not an audit record: write it at most this often per token
_TOUCH_INTERVAL = timedelta(minutes=5)


def resolve_principal(request: Request, auth: AuthConfig, db: Any, now: datetime) -> Optional[Principal]:
    """
    Identify the caller.

    A request with `Authorization: Bearer` is judged by its token alone, so a bad token never falls back to a
    session. Otherwise the mode decides: the session cookie (oidc) or the identity headers (proxy).

    Args:
        request: The incoming request.
        auth: The auth settings.
        db: The Chronowarden database.
        now: The current time (timezone-aware).

    Returns:
        The caller, or None when the request isn't authenticated.
    """
    if auth.mode == "none":
        return ANONYMOUS_ADMIN
    scheme, _, credential = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer":
        return _from_token(credential.strip(), db, now)
    if auth.mode == "oidc":
        session_id = request.cookies.get(SESSION_COOKIE)
        return _from_session(session_id, db, now) if session_id else None
    if auth.proxy is not None:
        return _from_proxy(request, auth, auth.proxy, db)
    return None


def _from_token(token: str, db: Any, now: datetime) -> Optional[Principal]:
    """An API token's principal, if the token is known, unexpired and not revoked."""
    if not token.startswith(TOKEN_PREFIX):
        return None
    row = db.get_api_token(digest(token), utc_timestamp(now))
    if row is None:
        return None
    if row["last_used_at"] is None or row["last_used_at"] < utc_timestamp(now - _TOUCH_INTERVAL):
        db.touch_api_token(row["id"], utc_timestamp(now))
    owner_ids = frozenset({row["owner_id"]}) if row["owner_id"] else frozenset()
    return Principal(name=row["name"], role=row["role"], kind="token", owner_ids=owner_ids)


def _from_session(session_id: str, db: Any, now: datetime) -> Optional[Principal]:
    """A logged-in user's principal; owners are matched now, so owner changes apply without a new login."""
    row = db.get_session(digest(session_id), utc_timestamp(now))
    if row is None:
        return None
    return Principal(
        name=row["name"],
        role=row["role"],
        kind="session",
        email=row["email"],
        groups=tuple(row["groups"]),
        owner_ids=frozenset(db.owner_ids_for(row["email"], row["groups"])),
    )


def _from_proxy(request: Request, auth: AuthConfig, proxy: ProxyConfig, db: Any) -> Optional[Principal]:
    """The user named by the proxy's headers, believed only when the request comes from a trusted proxy."""
    name = request.headers.get(proxy.user_header, "").strip()
    if not name or not _peer_trusted(request, proxy):
        return None
    email = request.headers.get(proxy.email_header, "").strip() or None
    groups = tuple(g.strip() for g in request.headers.get(proxy.groups_header, "").split(",") if g.strip())
    return Principal(
        name=name,
        role=role_for(groups, auth),
        kind="proxy",
        email=email,
        groups=groups,
        owner_ids=frozenset(db.owner_ids_for(email, list(groups))),
    )


def _peer_trusted(request: Request, proxy: ProxyConfig) -> bool:
    """Whether the TCP peer is one of `trusted_proxies`; anyone else could set the headers themselves."""
    if request.client is None:
        return False
    try:
        peer = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False
    if isinstance(peer, ipaddress.IPv6Address) and peer.ipv4_mapped is not None:
        peer = peer.ipv4_mapped
    if any(peer in network for network in proxy.trusted_proxies):
        return True
    logger.warning("Ignoring identity headers from %s, which is not in auth.proxy.trusted_proxies", peer)
    return False
