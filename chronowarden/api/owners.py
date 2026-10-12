# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for owner management."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Path, Request, status

from chronowarden.alerting.delivery import post
from chronowarden.alerting.payload import build_payload
from chronowarden.alerting.signing import generate_secret
from chronowarden.api.audit import request_source
from chronowarden.models.owner import (
    NotificationRoute,
    NotificationRouteCreate,
    Owner,
    OwnerCreate,
    OwnerUpdate,
    RouteTestResult,
    SigningSecret,
)
from chronowarden.timestamps import utc_timestamp

router = APIRouter(prefix="/owners", tags=["owners"])

logger = logging.getLogger("uvicorn.error")


def _get_db() -> Any:
    """Get the database from the app module."""
    from chronowarden.app import db

    return db


def _require_owner(db: Any, owner_id: str) -> dict:
    """
    Return an owner or raise 404.

    Raises:
        HTTPException: If the owner doesn't exist.
    """
    owner = db.get_owner(owner_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner '{owner_id}' not found")
    return owner


def _owner_view(owner: dict) -> dict:
    """An owner's fields as recorded in audit events."""
    return {"name": owner["name"], "email": owner["email"]}


def mask_address(address: str) -> str:
    """
    Mask a webhook URL down to its scheme and host.

    Webhook URLs often carry a token in the path or query (Slack, Teams), so only the stored copy keeps them.
    """
    parts = urlsplit(address)
    if not parts.scheme or not parts.hostname:
        return "…"
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname}{port}/…"


def _route_view(route: dict) -> dict:
    """A route's fields as recorded in audit events, with the address masked."""
    return {"id": route["id"], "type": route["type"], "address": mask_address(route["address"])}


def _build_route(route: dict) -> NotificationRoute:
    """Build a NotificationRoute model from a database dict, with the address masked."""
    return NotificationRoute(
        id=route["id"],
        owner_id=route["owner_id"],
        type=route["type"],
        address=mask_address(route["address"]),
        message_template=route.get("message_template", ""),
        created_at=route.get("created_at"),
        signed=bool(route.get("signed")),
    )


def _build_owner(owner_dict: dict, routes: list[dict]) -> Owner:
    """Build an Owner model from database dicts."""
    return Owner(
        id=owner_dict["id"],
        name=owner_dict["name"],
        email=owner_dict["email"],
        created_at=owner_dict.get("created_at"),
        notification_routes=[_build_route(r) for r in routes],
    )


@router.get("/", response_model=list[Owner], summary="List all owner profiles")
async def list_owners() -> list[Owner]:
    """List all owner profiles with their notification routes."""
    db = _get_db()
    routes_by_owner: dict[str, list[dict]] = {}
    for route in db.list_all_notification_routes():
        routes_by_owner.setdefault(route["owner_id"], []).append(route)
    return [_build_owner(owner, routes_by_owner.get(owner["id"], [])) for owner in db.list_owners()]


@router.post("/", response_model=Owner, status_code=status.HTTP_201_CREATED, summary="Create an owner profile")
async def create_owner(data: OwnerCreate, request: Request) -> Owner:
    """Create a new owner profile."""
    db = _get_db()
    owner_id = str(uuid.uuid4())
    db.create_owner(owner_id, data.name, data.email)
    owner_dict = db.get_owner(owner_id)
    if owner_dict is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create owner")
    db.append_audit_event(
        "owner.created", request_source(request), subject=f"owner:{owner_id}", after=_owner_view(owner_dict)
    )
    return _build_owner(owner_dict, [])


@router.get("/{owner_id}", response_model=Owner, summary="Get an owner profile")
async def get_owner(owner_id: str = Path(description="Owner ID")) -> Owner:
    """Get an owner profile by ID."""
    db = _get_db()
    owner_dict = _require_owner(db, owner_id)
    routes = db.list_notification_routes(owner_id)
    return _build_owner(owner_dict, routes)


@router.put("/{owner_id}", response_model=Owner, summary="Update an owner profile")
async def update_owner(data: OwnerUpdate, request: Request, owner_id: str = Path(description="Owner ID")) -> Owner:
    """Update an existing owner profile."""
    db = _get_db()
    existing = _require_owner(db, owner_id)
    db.update_owner(owner_id, name=data.name, email=data.email)
    owner_dict = db.get_owner(owner_id)
    if owner_dict is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update owner")
    if _owner_view(existing) != _owner_view(owner_dict):
        db.append_audit_event(
            "owner.updated",
            request_source(request),
            subject=f"owner:{owner_id}",
            before=_owner_view(existing),
            after=_owner_view(owner_dict),
        )
    routes = db.list_notification_routes(owner_id)
    return _build_owner(owner_dict, routes)


@router.delete("/{owner_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an owner profile")
async def delete_owner(request: Request, owner_id: str = Path(description="Owner ID")) -> None:
    """Delete an owner profile and all its notification routes."""
    db = _get_db()
    existing = _require_owner(db, owner_id)
    source = request_source(request)
    _, secret_owners = db.get_assignments()
    systems_before = {system["id"]: system["owner_ids"] for system in db.list_systems()}
    names = {owner["id"]: owner["name"] for owner in db.list_owners()}
    db.delete_owner(owner_id)
    db.append_audit_event("owner.deleted", source, subject=f"owner:{owner_id}", before=_owner_view(existing))
    # The owner disappears from every secret and system it was assigned to; record those changes too
    for identity, owner_ids in secret_owners.items():
        if owner_id in owner_ids:
            db.append_audit_event(
                "secret.owners",
                source,
                identity=identity,
                before={"owners": [{"id": oid, "name": names.get(oid)} for oid in owner_ids]},
                after={"owners": [{"id": oid, "name": names.get(oid)} for oid in owner_ids if oid != owner_id]},
            )
    for system_id, owner_ids in systems_before.items():
        if owner_id in owner_ids:
            db.append_audit_event(
                "system.owners",
                source,
                subject=f"system:{system_id}",
                before={"owner_ids": owner_ids},
                after={"owner_ids": [oid for oid in owner_ids if oid != owner_id]},
            )


@router.post(
    "/{owner_id}/routes",
    response_model=NotificationRoute,
    status_code=status.HTTP_201_CREATED,
    summary="Add a notification route",
)
async def add_route(
    data: NotificationRouteCreate,
    request: Request,
    owner_id: str = Path(description="Owner ID"),
) -> NotificationRoute:
    """Add a notification route to an owner. The response masks the address down to its scheme and host."""
    db = _get_db()
    _require_owner(db, owner_id)
    route_id = str(uuid.uuid4())
    db.create_notification_route(route_id, owner_id, data.type, data.address, data.message_template)
    route = next((r for r in db.list_notification_routes(owner_id) if r["id"] == route_id), None)
    if route is not None:
        db.append_audit_event(
            "owner.route_added", request_source(request), subject=f"owner:{owner_id}", after=_route_view(route)
        )
        return _build_route(route)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create route")


@router.delete(
    "/{owner_id}/routes/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a notification route",
)
async def delete_route(
    request: Request,
    owner_id: str = Path(description="Owner ID"),
    route_id: str = Path(description="Route ID"),
) -> None:
    """
    Remove a notification route from an owner.

    Raises:
        HTTPException: 404 if the owner doesn't exist or the route isn't one of its routes.
    """
    db = _get_db()
    route = _require_route(db, owner_id, route_id)
    db.delete_notification_route(route_id)
    db.append_audit_event(
        "owner.route_deleted", request_source(request), subject=f"owner:{owner_id}", before=_route_view(route)
    )


def _require_route(db: Any, owner_id: str, route_id: str) -> dict:
    """
    Return one of an owner's routes.

    Raises:
        HTTPException: 404 if the owner doesn't exist or the route isn't one of its routes.
    """
    _require_owner(db, owner_id)
    route = next((r for r in db.list_notification_routes(owner_id) if r["id"] == route_id), None)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Route '{route_id}' not found")
    return route


@router.post(
    "/{owner_id}/routes/{route_id}/signing",
    response_model=SigningSecret,
    status_code=status.HTTP_201_CREATED,
    summary="Turn on signing for a route",
)
async def enable_signing(
    request: Request, owner_id: str = Path(description="Owner ID"), route_id: str = Path(description="Route ID")
) -> SigningSecret:
    """
    Generate a new Standard Webhooks secret for the route; it is shown only in this response (ADR-025).

    Calling it again replaces the secret (rotation): update the receiver at the same time.

    Raises:
        HTTPException: 404 if the owner or route doesn't exist.
    """
    db = _get_db()
    route = _require_route(db, owner_id, route_id)
    secret = generate_secret()
    db.set_route_signing_secret(route_id, secret)
    db.append_audit_event(
        "owner.route_signing",
        request_source(request),
        subject=f"owner:{owner_id}",
        before={"id": route_id, "signed": bool(route["signed"])},
        after={"id": route_id, "signed": True},
    )
    return SigningSecret(route_id=route_id, secret=secret)


@router.delete(
    "/{owner_id}/routes/{route_id}/signing",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Turn off signing for a route",
)
async def disable_signing(
    request: Request, owner_id: str = Path(description="Owner ID"), route_id: str = Path(description="Route ID")
) -> None:
    """
    Forget the route's signing secret; deliveries go out unsigned.

    Raises:
        HTTPException: 404 if the owner or route doesn't exist.
    """
    db = _get_db()
    route = _require_route(db, owner_id, route_id)
    db.set_route_signing_secret(route_id, None)
    if route["signed"]:
        db.append_audit_event(
            "owner.route_signing",
            request_source(request),
            subject=f"owner:{owner_id}",
            before={"id": route_id, "signed": True},
            after={"id": route_id, "signed": False},
        )


@router.post(
    "/{owner_id}/test-route/{route_id}",
    response_model=RouteTestResult,
    summary="Send a test webhook to a route",
)
async def test_route(
    owner_id: str = Path(description="Owner ID"),
    route_id: str = Path(description="Route ID"),
) -> RouteTestResult:
    """
    POST a test alert to the route now, signed if signing is on, and report how the receiver answered.

    The URL never appears in the answer or the logs: webhook URLs carry tokens.

    Raises:
        HTTPException: 404 if the owner or route doesn't exist.
    """
    from chronowarden.app import app_config

    db = _get_db()
    _require_route(db, owner_id, route_id)
    target = db.get_route_target(route_id)
    now = datetime.now(tz=timezone.utc)
    notification = {
        "fingerprint": "test",
        "alertname": "ChronowardenTest",
        "labels": {"alertname": "ChronowardenTest", "owner": owner_id},
        "annotations": {"summary": "Test webhook from Chronowarden", "description": "Nothing needs to be done"},
        "status": "firing",
        "starts_at": utc_timestamp(now),
        "ends_at": utc_timestamp(now),
    }
    body = json.dumps(build_payload(notification, f"owner:{owner_id}", app_config.alerting.external_url))
    status_code, error = await asyncio.to_thread(
        post, target["address"], body.encode("utf-8"), f"msg_test_{uuid.uuid4().hex}", target["signing_secret"], now
    )
    if error:
        return RouteTestResult(success=False, status_code=status_code, message=f"The receiver answered: {error}")
    return RouteTestResult(success=True, status_code=status_code, message="Delivered")
