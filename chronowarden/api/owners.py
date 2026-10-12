# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for owner management."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Request, status

from chronowarden.api.audit import request_source
from chronowarden.models.owner import (
    NotificationRoute,
    NotificationRouteCreate,
    Owner,
    OwnerCreate,
    OwnerUpdate,
)

router = APIRouter(prefix="/owners", tags=["owners"])

logger = logging.getLogger("uvicorn.error")


def _get_db() -> Any:
    """Get the database from the app module."""
    from chronowarden.app import db

    return db


def _owner_view(owner: dict) -> dict:
    """An owner's fields as recorded in audit events."""
    return {"name": owner["name"], "email": owner["email"]}


def _build_owner(owner_dict: dict, routes: list[dict]) -> Owner:
    """Build an Owner model from database dicts."""
    return Owner(
        id=owner_dict["id"],
        name=owner_dict["name"],
        email=owner_dict["email"],
        created_at=owner_dict.get("created_at"),
        notification_routes=[
            NotificationRoute(
                id=r["id"],
                owner_id=r["owner_id"],
                type=r["type"],
                address=r["address"],
                message_template=r.get("message_template", ""),
                created_at=r.get("created_at"),
            )
            for r in routes
        ],
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
    owner_dict = db.get_owner(owner_id)
    if owner_dict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner '{owner_id}' not found")
    routes = db.list_notification_routes(owner_id)
    return _build_owner(owner_dict, routes)


@router.put("/{owner_id}", response_model=Owner, summary="Update an owner profile")
async def update_owner(data: OwnerUpdate, request: Request, owner_id: str = Path(description="Owner ID")) -> Owner:
    """Update an existing owner profile."""
    db = _get_db()
    existing = db.get_owner(owner_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner '{owner_id}' not found")
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
    existing = db.get_owner(owner_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner '{owner_id}' not found")
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
    owner_id: str = Path(description="Owner ID"),
) -> NotificationRoute:
    """Add a notification route to an owner."""
    db = _get_db()
    existing = db.get_owner(owner_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner '{owner_id}' not found")
    route_id = str(uuid.uuid4())
    db.create_notification_route(route_id, owner_id, data.type, data.address, data.message_template)
    routes = db.list_notification_routes(owner_id)
    for r in routes:
        if r["id"] == route_id:
            return NotificationRoute(
                id=r["id"],
                owner_id=r["owner_id"],
                type=r["type"],
                address=r["address"],
                message_template=r.get("message_template", ""),
                created_at=r.get("created_at"),
            )
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create route")


@router.delete(
    "/{owner_id}/routes/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a notification route",
)
async def delete_route(
    owner_id: str = Path(description="Owner ID"),
    route_id: str = Path(description="Route ID"),
) -> None:
    """
    Remove a notification route from an owner.

    Raises:
        HTTPException: 404 if the owner doesn't exist or the route isn't one of its routes.
    """
    db = _get_db()
    existing = db.get_owner(owner_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner '{owner_id}' not found")
    if not any(route["id"] == route_id for route in db.list_notification_routes(owner_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Route '{route_id}' not found")
    db.delete_notification_route(route_id)


@router.post(
    "/{owner_id}/test-route/{route_id}",
    summary="Test a notification route",
)
async def test_route(
    owner_id: str = Path(description="Owner ID"),
    route_id: str = Path(description="Route ID"),
) -> dict[str, Any]:
    """Send a test notification via a specific route."""
    db = _get_db()
    existing = db.get_owner(owner_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner '{owner_id}' not found")
    routes = db.list_notification_routes(owner_id)
    route = next((r for r in routes if r["id"] == route_id), None)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Route '{route_id}' not found")
    # Webhook URLs are credentials (Slack, Teams): never log them. Delivery comes with webhook alerting in 0.8.
    return {"success": False, "message": "Nothing was sent: notification delivery comes with webhook alerting (0.8)"}
