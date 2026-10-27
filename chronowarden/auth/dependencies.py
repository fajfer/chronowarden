# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""FastAPI dependencies that authenticate requests and check the ADR-026 permission matrix."""

from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status

from chronowarden.auth.principal import Principal
from chronowarden.auth.resolve import resolve_principal
from chronowarden.config import AuthConfig, Role


def _get_auth_context() -> tuple[Optional[AuthConfig], Any]:
    """Get the auth settings and the database from the app module."""
    from chronowarden.app import app_config, db

    return app_config.auth, db


async def authenticated(request: Request) -> Principal:
    """
    The caller of this request; every router under /api/v1 except health depends on it.

    Returns:
        The principal, also kept in `request.state.principal` for `request_actor`.

    Raises:
        HTTPException: 401 without valid credentials, 403 for a user without a role, 503 if auth isn't configured
            (the server refuses to start that way, so only a broken setup gets here).
    """
    cached = getattr(request.state, "principal", None)
    if isinstance(cached, Principal):
        return cached
    auth, db = _get_auth_context()
    if auth is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured")
    principal = resolve_principal(request, auth, db, datetime.now(tz=timezone.utc))
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Log in or send an API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if principal.role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has no Chronowarden role; an admin can map one of your groups in auth.roles",
        )
    request.state.principal = principal
    return principal


def require_role(role: Role) -> Callable[..., Awaitable[Principal]]:
    """
    A dependency that lets `role` and higher roles through.

    Args:
        role: The lowest role allowed.

    Returns:
        The dependency, which returns the principal.
    """

    async def dependency(principal: Principal = Depends(authenticated)) -> Principal:
        if not principal.at_least(role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"This needs the {role} role")
        return principal

    return dependency


def check_acts_for(principal: Principal, owner_ids: Iterable[str], what: str = "this secret") -> None:
    """
    Refuse unless the caller acts for one of the owners (admins always do).

    Args:
        principal: The caller.
        owner_ids: The effective owners of what is being changed.
        what: Named in the error.

    Raises:
        HTTPException: 403 otherwise.
    """
    if not principal.acts_for(owner_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Only its owners or an admin can change {what}"
        )


def request_actor(request: Request) -> Optional[str]:
    """The audit actor of a request that passed `authenticated`; None without authentication."""
    principal = getattr(request.state, "principal", None)
    return principal.actor if isinstance(principal, Principal) else None
