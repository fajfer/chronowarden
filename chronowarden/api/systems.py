# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for systems (ADR-010)."""

import logging
import sqlite3
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Request, status

from chronowarden.api.audit import request_source
from chronowarden.assignments import AssignmentIndex
from chronowarden.models.system import OwnerIds, System, SystemCreate, SystemUpdate

router = APIRouter(prefix="/systems", tags=["systems"])

logger = logging.getLogger("uvicorn.error")


def _get_db() -> Any:
    """Get the database from the app module."""
    from chronowarden.app import db

    return db


def _build_system(system: dict, index: AssignmentIndex) -> System:
    """Build a System response from a database dict."""
    return System(
        id=system["id"],
        name=system["name"],
        description=system["description"],
        cmdb_uri=system["cmdb_uri"],
        asset_number=system["asset_number"],
        created_at=system["created_at"],
        owners=index.system_owner_refs(system),
    )


def _require_system(db: Any, system_id: str) -> dict:
    """
    Return a system or raise 404.

    Raises:
        HTTPException: If the system doesn't exist.
    """
    system = db.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"System '{system_id}' not found")
    return system


def require_known_owners(db: Any, owner_ids: list[str]) -> None:
    """
    Check that every owner ID exists.

    Raises:
        HTTPException: 422 listing the unknown owner IDs.
    """
    known = {owner["id"] for owner in db.list_owners()}
    unknown = sorted(set(owner_ids) - known)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown owner ID(s): {', '.join(unknown)}")


def _audit_view(system: dict) -> dict:
    """A system's fields as recorded in audit events."""
    return {key: system[key] for key in ("name", "description", "cmdb_uri", "asset_number", "owner_ids")}


def _name_taken(name: str) -> HTTPException:
    """Build the 409 response for a duplicate system name."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A system named '{name}' already exists")


@router.get("/", response_model=list[System], summary="List systems")
async def list_systems() -> list[System]:
    """List all systems with their owners."""
    db = _get_db()
    index = AssignmentIndex(db)
    return [_build_system(system, index) for system in db.list_systems()]


@router.post("/", response_model=System, status_code=status.HTTP_201_CREATED, summary="Create a system")
async def create_system(data: SystemCreate, request: Request) -> System:
    """
    Create a system, optionally with owners.

    Raises:
        HTTPException: 409 if the name is taken, 422 for unknown owner IDs.
    """
    db = _get_db()
    require_known_owners(db, data.owner_ids)
    system_id = str(uuid.uuid4())
    try:
        db.create_system(system_id, data.name, data.description, data.cmdb_uri, data.asset_number)
    except sqlite3.IntegrityError:
        raise _name_taken(data.name) from None
    db.set_system_owners(system_id, data.owner_ids)
    system = _require_system(db, system_id)
    db.append_audit_event(
        "system.created", request_source(request), subject=f"system:{system_id}", after=_audit_view(system)
    )
    return _build_system(system, AssignmentIndex(db))


@router.get("/{system_id}", response_model=System, summary="Get a system")
async def get_system(system_id: str = Path(description="System ID")) -> System:
    """
    Get a system with its owners.

    Raises:
        HTTPException: 404 if the system doesn't exist.
    """
    db = _get_db()
    return _build_system(_require_system(db, system_id), AssignmentIndex(db))


@router.put("/{system_id}", response_model=System, summary="Update a system")
async def update_system(data: SystemUpdate, request: Request, system_id: str = Path(description="System ID")) -> System:
    """
    Update a system's fields; omitted fields stay unchanged.

    Raises:
        HTTPException: 404 if the system doesn't exist, 409 if the new name is taken.
    """
    db = _get_db()
    before = _require_system(db, system_id)
    fields = data.model_dump(exclude_unset=True)
    try:
        db.update_system(system_id, fields)
    except sqlite3.IntegrityError:
        raise _name_taken(str(fields.get("name"))) from None
    after = _require_system(db, system_id)
    changed = [key for key in fields if before[key] != after[key]]
    if changed:
        db.append_audit_event(
            "system.updated",
            request_source(request),
            subject=f"system:{system_id}",
            before={key: before[key] for key in changed},
            after={key: after[key] for key in changed},
        )
    return _build_system(after, AssignmentIndex(db))


@router.put("/{system_id}/owners", response_model=System, summary="Replace a system's owners")
async def set_system_owners(data: OwnerIds, request: Request, system_id: str = Path(description="System ID")) -> System:
    """
    Replace the owners of a system.

    Raises:
        HTTPException: 404 if the system doesn't exist, 422 for unknown owner IDs.
    """
    db = _get_db()
    _require_system(db, system_id)
    require_known_owners(db, data.owner_ids)
    previous = db.set_system_owners(system_id, data.owner_ids)
    system = _require_system(db, system_id)
    if previous != system["owner_ids"]:
        db.append_audit_event(
            "system.owners",
            request_source(request),
            subject=f"system:{system_id}",
            before={"owner_ids": previous},
            after={"owner_ids": system["owner_ids"]},
        )
    return _build_system(system, AssignmentIndex(db))


@router.delete("/{system_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a system")
async def delete_system(request: Request, system_id: str = Path(description="System ID")) -> None:
    """
    Delete a system that no secret is assigned to.

    Raises:
        HTTPException: 404 if the system doesn't exist, 409 listing the secrets still assigned to it.
    """
    db = _get_db()
    system = _require_system(db, system_id)
    assigned = db.list_secrets_of_system(system_id)
    if assigned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"System '{system['name']}' still has {len(assigned)} secret(s); unassign them first",
                "secrets": ["/".join(identity) for identity in assigned],
            },
        )
    db.delete_system(system_id)
    db.append_audit_event(
        "system.deleted", request_source(request), subject=f"system:{system_id}", before=_audit_view(system)
    )
