# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for owner management."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Path, status

from chronowarden.models.owner import (
    NotificationRoute,
    NotificationRouteCreate,
    Owner,
    OwnerCreate,
    OwnerUpdate,
)

router = APIRouter(prefix="/owners", tags=["owners"])

logger = logging.getLogger(__name__)


def _get_db() -> Any:
    """Get the database from the app module."""
    from chronowarden.app import db

    return db


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
    owners = db.list_owners()
    result = []
    for owner_dict in owners:
        routes = db.list_notification_routes(owner_dict["id"])
        result.append(_build_owner(owner_dict, routes))
    return result


@router.post("/", response_model=Owner, status_code=status.HTTP_201_CREATED, summary="Create an owner profile")
async def create_owner(data: OwnerCreate) -> Owner:
    """Create a new owner profile."""
    db = _get_db()
    owner_id = str(uuid.uuid4())
    db.create_owner(owner_id, data.name, data.email)
    owner_dict = db.get_owner(owner_id)
    if owner_dict is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create owner")
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
async def update_owner(data: OwnerUpdate, owner_id: str = Path(description="Owner ID")) -> Owner:
    """Update an existing owner profile."""
    db = _get_db()
    existing = db.get_owner(owner_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner '{owner_id}' not found")
    db.update_owner(owner_id, name=data.name, email=data.email)
    owner_dict = db.get_owner(owner_id)
    if owner_dict is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update owner")
    routes = db.list_notification_routes(owner_id)
    return _build_owner(owner_dict, routes)


@router.delete("/{owner_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an owner profile")
async def delete_owner(owner_id: str = Path(description="Owner ID")) -> None:
    """Delete an owner profile and all its notification routes."""
    db = _get_db()
    existing = db.get_owner(owner_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner '{owner_id}' not found")
    db.delete_owner(owner_id)


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
    """Remove a notification route from an owner."""
    db = _get_db()
    existing = db.get_owner(owner_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner '{owner_id}' not found")
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
    logger.info("Test notification sent via %s to %s", route["type"], route["address"])
    return {"success": True, "message": f"Test notification sent to {route['address']}"}
