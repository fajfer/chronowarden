# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for the audit log (ADR-014)."""

import json
from collections.abc import Iterator
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import StreamingResponse

from chronowarden.assignments import AssignmentIndex
from chronowarden.audit import verify_chain
from chronowarden.audit.revert import RevertError, revert_event
from chronowarden.auth import Principal, authenticated, check_acts_for, owner_or_admin, request_actor
from chronowarden.models.audit import AuditChainStatus, AuditEvent

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(authenticated)])

# Header the frontend sends so events can tell UI changes from other API clients until authentication exists
CLIENT_HEADER = "X-Chronowarden-Client"


def _get_db() -> Any:
    """Get the database from the app module."""
    from chronowarden.app import db

    return db


def request_source(request: Request) -> str:
    """Return the audit source of a request: `ui` for the web UI, `api` for any other client."""
    return "ui" if request.headers.get(CLIENT_HEADER) == "ui" else "api"


@router.get("/events", response_model=list[AuditEvent], summary="List audit events")
async def list_events(
    vault_name: Optional[str] = Query(None),
    engine_id: Optional[str] = Query(None),
    secret_path: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, description="e.g. secret.system, system.created, config.changed"),
    subject: Optional[str] = Query(None, description="e.g. system:<id>"),
    since: Optional[str] = Query(None, description="ISO 8601 UTC, inclusive"),
    until: Optional[str] = Query(None, description="ISO 8601 UTC, inclusive"),
    before_id: Optional[int] = Query(None, description="Page backwards: only events older than this id"),
    limit: int = Query(200, ge=1, le=1000),
) -> list[AuditEvent]:
    """
    List audit events, newest first, with optional filters.

    Returns:
        Matching events.
    """
    rows = _get_db().list_audit_events(
        limit=limit,
        vault_name=vault_name,
        engine_id=engine_id,
        secret_path=secret_path,
        event_type=event_type,
        subject=subject,
        since=since,
        until=until,
        before_id=before_id,
    )
    return [AuditEvent.from_stored(row) for row in rows]


@router.get("/events.jsonl", summary="Export the whole audit log as JSON Lines")
async def export_events() -> StreamingResponse:
    """
    Export every event in id order, exactly as stored (before/after as the hashed JSON text), one per line.

    Returns:
        A JSON Lines download anyone can verify with the recipe in `chronowarden/audit/AGENTS.md`.
    """
    rows = _get_db().iter_audit_events()

    def lines() -> Iterator[str]:
        for row in rows:
            yield json.dumps(row, ensure_ascii=False) + "\n"

    return StreamingResponse(
        lines(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="chronowarden-audit.jsonl"'},
    )


@router.get("/verify", response_model=AuditChainStatus, summary="Verify the audit log's hash chain")
async def verify() -> AuditChainStatus:
    """
    Recompute every hash and link of the audit log.

    Returns:
        Whether the chain is intact, its length and head hash, and the first broken event if any.
    """
    return AuditChainStatus(**verify_chain(_get_db().iter_audit_events())._asdict())


@router.post(
    "/events/{event_id}/revert",
    response_model=AuditEvent,
    status_code=status.HTTP_201_CREATED,
    summary="Revert an event",
)
async def revert(
    request: Request,
    event_id: int = Path(description="Audit event ID"),
    principal: Principal = Depends(owner_or_admin),
) -> AuditEvent:
    """
    Restore the value an event replaced; the revert is recorded as a new event that names the reverted one.

    Only Chronowarden's own data can be reverted (ADR-004): a secret's system and owners, its privileged flag and
    rotation confirmations.

    Returns:
        The new event.

    Raises:
        HTTPException: 404 for an unknown event, 403 unless the caller is an admin or acts for the secret's effective
            owners, 422 if the event can't be reverted, 409 if the value changed since or what it refers to no longer
            exists.
    """
    db = _get_db()
    event = db.get_audit_event(event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit event {event_id} not found")
    if event["vault_name"] is None:
        check_acts_for(principal, [], "this")
    else:
        identity = (event["vault_name"], event["engine_id"], event["secret_path"])
        check_acts_for(principal, [owner.id for owner in AssignmentIndex(db).effective_owners_of(identity)])
    try:
        from chronowarden.app import app_config, vault_manager

        return AuditEvent.from_stored(
            revert_event(db, event, request_source(request), app_config, vault_manager, request_actor(request))
        )
    except RevertError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None
