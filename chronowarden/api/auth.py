# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for login, logout and the caller's identity (ADR-015, ADR-026)."""

import asyncio
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import RedirectResponse, Response

from chronowarden.api.audit import request_source
from chronowarden.auth import Principal, admin_only, authenticated, request_actor, role_for
from chronowarden.auth.oidc import OidcClient, OidcError
from chronowarden.auth.resolve import SESSION_COOKIE
from chronowarden.auth.tokens import digest, new_api_token, new_session_id
from chronowarden.config import AuthConfig, OidcConfig
from chronowarden.models.auth import ApiToken, ApiTokenCreate, LogoutResult, Me, NewApiToken
from chronowarden.timestamps import utc_timestamp

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger("uvicorn.error")

# How long a login may take at the IdP before its state is forgotten
PENDING_LOGIN = timedelta(minutes=10)

_client: Optional[OidcClient] = None


def _get_app_dependencies() -> tuple[Optional[AuthConfig], Any]:
    """Get the auth settings and the database from the app module."""
    from chronowarden.app import app_config, db

    return app_config.auth, db


def _oidc_client(config: OidcConfig) -> OidcClient:
    """One client per configuration, so discovery and keys stay cached."""
    global _client
    if _client is None or _client.config is not config:
        _client = OidcClient(config)
    return _client


def _require_oidc() -> tuple[AuthConfig, OidcConfig, Any]:
    """
    The OIDC settings, or 404 when Chronowarden doesn't run the login itself.

    Raises:
        HTTPException: 404 outside `auth.mode: oidc`.
    """
    auth, db = _get_app_dependencies()
    if auth is None or auth.mode != "oidc" or auth.oidc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Login is not handled by Chronowarden")
    return auth, auth.oidc, db


def safe_next(path: Optional[str]) -> str:
    """Keep redirects after login on this site: a local absolute path, else `/`."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return path


def _login_page(error: str) -> RedirectResponse:
    """Send the browser to the login page with an error code the UI explains."""
    return RedirectResponse("/login?" + urlencode({"error": error}), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", summary="Start an OIDC login", response_class=RedirectResponse)
async def login(next: Optional[str] = Query(None, description="Local path to return to")) -> RedirectResponse:
    """
    Redirect the browser to the identity provider (authorization code flow with PKCE).

    Raises:
        HTTPException: 404 outside oidc mode, 502 when the provider can't be reached.
    """
    _, oidc, db = _require_oidc()
    now = datetime.now(tz=timezone.utc)
    try:
        start = await asyncio.to_thread(_oidc_client(oidc).start_login)
    except OidcError:
        logger.exception("Cannot start an OIDC login")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The identity provider is unreachable")
    db.delete_expired_logins(utc_timestamp(now), utc_timestamp(now - PENDING_LOGIN))
    db.add_oidc_pending(start.state, start.code_verifier, start.nonce, safe_next(next), utc_timestamp(now))
    return RedirectResponse(start.url, status_code=status.HTTP_302_FOUND)


@router.get("/callback", summary="Finish an OIDC login", response_class=RedirectResponse)
async def callback(
    state: str = Query(""), code: Optional[str] = Query(None), error: Optional[str] = Query(None)
) -> RedirectResponse:
    """
    Check the provider's answer, start a session and return to where the login began.

    Failures go to `/login?error=...`: `expired` (unknown or stale state), `denied` (the provider refused),
    `failed` (exchange or ID token invalid), `no_role` (no group maps to a role).
    """
    auth, oidc, db = _require_oidc()
    now = datetime.now(tz=timezone.utc)
    pending = db.pop_oidc_pending(state, utc_timestamp(now - PENDING_LOGIN)) if state else None
    if pending is None:
        return _login_page("expired")
    if error is not None or not code:
        logger.warning("The identity provider refused a login: %s", error)
        return _login_page("denied")
    try:
        user = await asyncio.to_thread(
            _oidc_client(oidc).finish_login, code, pending["code_verifier"], pending["nonce"]
        )
    except OidcError:
        logger.exception("OIDC login failed")
        return _login_page("failed")
    role = role_for(user.groups, auth)
    if role is None:
        logger.info("Login refused for %s: none of their groups maps to a role", user.name)
        return _login_page("no_role")
    session_id = new_session_id()
    db.create_session(
        digest(session_id),
        user.name,
        user.email,
        user.groups,
        role,
        utc_timestamp(now),
        utc_timestamp(now + timedelta(seconds=auth.session_seconds)),
    )
    response = RedirectResponse(pending["next_path"], status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=auth.session_seconds,
        path="/",
        httponly=True,
        secure=oidc.redirect_uri.lower().startswith("https://"),
        samesite="lax",
    )
    return response


@router.post("/logout", response_model=LogoutResult, summary="Log out")
async def logout(request: Request, response: Response) -> LogoutResult:
    """
    End the session; behind a proxy, return where to sign out of the proxy too.

    Returns:
        The proxy's `logout_url`, if configured.
    """
    auth, db = _get_app_dependencies()
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        db.delete_session(digest(session_id))
    response.delete_cookie(SESSION_COOKIE, path="/")
    proxy = auth.proxy if auth is not None and auth.mode == "proxy" else None
    return LogoutResult(logout_url=proxy.logout_url if proxy is not None else None)


@router.get("/me", response_model=Me, summary="The caller")
async def me(principal: Principal = Depends(authenticated)) -> Me:
    """
    Who is calling, with which role, acting for which owners.

    Returns:
        The caller; 401 when not logged in.
    """
    auth, _ = _get_app_dependencies()
    return Me(
        auth_mode=auth.mode if auth is not None else "none",
        name=principal.name,
        email=principal.email,
        role=principal.role or "viewer",
        kind=principal.kind,
        owner_ids=sorted(principal.owner_ids),
    )


def _token_view(token: dict) -> dict:
    """A token's fields as recorded in audit events: never the token or its hash."""
    return {
        "name": token["name"],
        "role": token["role"],
        "owner_id": token["owner_id"],
        "expires_at": token["expires_at"],
    }


@router.get("/tokens", response_model=list[ApiToken], dependencies=[Depends(admin_only)], summary="List API tokens")
async def list_tokens() -> list[ApiToken]:
    """
    List every API token, newest first, including expired and revoked ones.

    Returns:
        The tokens, without their values.
    """
    _, db = _get_app_dependencies()
    return [ApiToken(**token) for token in db.list_api_tokens()]


@router.post(
    "/tokens",
    response_model=NewApiToken,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(admin_only)],
    summary="Create an API token",
)
async def create_token(data: ApiTokenCreate, request: Request) -> NewApiToken:
    """
    Issue a token for a pipeline or another client; its value is returned only now.

    Raises:
        HTTPException: 422 when the owner is missing, unknown or given for another role, or the expiry is too long;
            409 when the name is taken.
    """
    auth, db = _get_app_dependencies()
    max_days = auth.token_max_days if auth is not None else 0
    if data.expires_in_days > max_days:
        raise HTTPException(
            status_code=422, detail=f"Tokens expire after at most {max_days} days (auth.token_max_lifetime)"
        )
    if (data.role == "owner") != (data.owner_id is not None):
        raise HTTPException(status_code=422, detail="An owner_id is required for the owner role, and only for it")
    if data.owner_id is not None and db.get_owner(data.owner_id) is None:
        raise HTTPException(status_code=422, detail=f"Unknown owner ID: {data.owner_id}")
    now = datetime.now(tz=timezone.utc)
    token, token_id = new_api_token(), str(uuid.uuid4())
    expires_at = utc_timestamp(now + timedelta(days=data.expires_in_days))
    try:
        db.create_api_token(
            token_id, data.name, digest(token), data.role, data.owner_id, utc_timestamp(now), expires_at
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"A token named '{data.name}' exists"
        ) from None
    created = next(t for t in db.list_api_tokens() if t["id"] == token_id)
    db.append_audit_event(
        "token.created",
        request_source(request),
        actor=request_actor(request),
        subject=f"token:{token_id}",
        after=_token_view(created),
    )
    return NewApiToken(**created, token=token)


@router.delete(
    "/tokens/{token_id}",
    response_model=ApiToken,
    dependencies=[Depends(admin_only)],
    summary="Revoke an API token",
)
async def revoke_token(request: Request, token_id: str = Path(description="Token ID")) -> ApiToken:
    """
    Revoke a token at once; it stays listed as revoked.

    Raises:
        HTTPException: 404 for an unknown or already revoked token.
    """
    _, db = _get_app_dependencies()
    revoked = db.revoke_api_token(token_id, utc_timestamp())
    if revoked is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No active token '{token_id}'")
    db.append_audit_event(
        "token.revoked",
        request_source(request),
        actor=request_actor(request),
        subject=f"token:{token_id}",
        before=_token_view(revoked),
    )
    return ApiToken(**revoked)
