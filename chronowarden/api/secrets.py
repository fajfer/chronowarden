# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for reading cached secret metadata."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status

from chronowarden.api.audit import request_source
from chronowarden.assignments import AssignmentIndex
from chronowarden.config import AppConfig
from chronowarden.confirmations import current_version, refresh_cached_ttl
from chronowarden.database import SecretIdentity, SecretMetadataCache
from chronowarden.metadata import parse_date
from chronowarden.models.audit import AuditEvent
from chronowarden.models.secret import (
    Confirmation,
    ConfirmationCreate,
    PrivilegedUpdate,
    PurgeResult,
    SecretMetadataResponse,
    SecretStatus,
)
from chronowarden.models.system import OwnerIds, SystemAssignment

router = APIRouter(prefix="/secrets", tags=["secrets"])

logger = logging.getLogger("uvicorn.error")


def _get_app_dependencies() -> tuple[Any, Any, Any]:
    """
    Get the database, config, and vault manager from the app module.

    Returns:
        Tuple of (Database, AppConfig, VaultManager).
    """
    from chronowarden.app import app_config, db, vault_manager

    return db, app_config, vault_manager


def _compute_status(days_remaining: Optional[int], alert_days: int) -> SecretStatus:
    """
    Compute the secret status from days remaining.

    Args:
        days_remaining: Number of days until expiry, or None.
        alert_days: Alert threshold of the secret's expiry profile.

    Returns:
        The computed SecretStatus.
    """
    if days_remaining is None:
        return SecretStatus.NO_TTL
    if days_remaining <= 0:
        return SecretStatus.EXPIRED
    if days_remaining <= alert_days:
        return SecretStatus.WARNING
    return SecretStatus.OK


def _validate_severity_input(severity: Optional[str], config: AppConfig, request_source: str) -> None:
    """
    Validate a request severity value against configured expiry profiles.

    Args:
        severity: Requested severity value.
        config: Application configuration.
        request_source: Human-readable source phrase used in errors (e.g. "query parameter", "request body").

    Raises:
        HTTPException: If severity is unknown.
    """
    if severity is None:
        return

    if severity == "none" or severity in config.expiry_profiles:
        return

    allowed_values = ", ".join(sorted([*config.expiry_profiles, "none"]))
    raise HTTPException(
        status_code=422,
        detail=f"Invalid severity '{severity}' in {request_source}. Allowed values: {allowed_values}",
    )


def _enrich_secret(entry: SecretMetadataCache, config: AppConfig, index: AssignmentIndex) -> SecretMetadataResponse:
    """
    Build a SecretMetadataResponse from a cache entry with computed fields.

    Args:
        entry: The raw database cache entry.
        config: Application configuration for severity/rotation lookups.
        index: System and owner assignments.

    Returns:
        Enriched response model.
    """
    severity = entry.severity or "default"
    rotation_days = config.get_rotation_days(severity)
    alert_days = config.get_alert_days(severity)
    date_format = config.resolve_date_format(entry.vault_name)

    ttl_date: Optional[datetime] = None
    days_remaining: Optional[int] = None

    if entry.ttl:
        ttl_date = parse_date(entry.ttl, date_format)
        if ttl_date is not None:
            now = datetime.now(tz=timezone.utc)
            if ttl_date.tzinfo is None:
                ttl_date = ttl_date.replace(tzinfo=timezone.utc)
            days_remaining = (ttl_date - now).days

    last_synced: Optional[datetime] = None
    if entry.last_synced:
        last_synced = parse_date(entry.last_synced)

    return SecretMetadataResponse(
        id=entry.id or 0,
        vault_name=entry.vault_name,
        engine_id=entry.engine_id,
        secret_path=entry.secret_path,
        full_path=f"{entry.vault_name}/{entry.engine_id}/{entry.secret_path}",
        ttl=entry.ttl,
        updated_time=entry.updated_time,
        ttl_date=ttl_date,
        days_remaining=days_remaining,
        severity=severity,
        rotation_period_days=rotation_days,
        alert_threshold_days=alert_days,
        last_synced=last_synced,
        status=_compute_status(days_remaining, alert_days),
        removed_at=parse_date(entry.removed_at) if entry.removed_at else None,
        privileged=entry.privileged,
        **_confirmation_fields(index, config, _identity(entry), severity),
        system=index.system_of(_identity(entry)),
        owners=index.owners_of(_identity(entry)),
        effective_owners=index.effective_owners_of(_identity(entry)),
    )


def _confirmation_fields(
    index: AssignmentIndex, config: AppConfig, identity: SecretIdentity, severity: str
) -> dict[str, Any]:
    """The confirmation fields of a secret response (ADR-021), from the request's preloaded index."""
    status_ = index.confirmations.status(config, identity, severity)
    latest = status_.latest
    return {
        "confirmation_required": status_.required,
        "awaiting_confirmation": status_.awaiting,
        "confirmation_overdue": status_.overdue,
        "last_confirmation": Confirmation(**{k: latest[k] for k in Confirmation.model_fields}) if latest else None,
    }


def _identity(entry: SecretMetadataCache) -> SecretIdentity:
    """Return the secret's real identity, which assignments are keyed by (ADR-017)."""
    return (entry.vault_name, entry.engine_id, entry.secret_path)


def _assignment_state(index: AssignmentIndex, identity: SecretIdentity) -> dict[str, Any]:
    """A secret's system and own owners, as recorded in audit events."""
    system = index.system_of(identity)
    return {
        "system": system.model_dump() if system else None,
        "owners": [owner.model_dump() for owner in index.owners_of(identity)],
    }


def _record_purges(database: Any, index: AssignmentIndex, identities: list[SecretIdentity], source: str) -> None:
    """Record a `secret.purged` event, with the assignments that went with it, for each purged secret."""
    for identity in identities:
        database.append_audit_event(
            "secret.purged", source, identity=identity, before=_assignment_state(index, identity)
        )


def _require_secret(database: Any, secret_id: int) -> SecretMetadataCache:
    """
    Return a cached secret or raise 404.

    Raises:
        HTTPException: If the secret isn't in the cache.
    """
    entry = database.get_secret_by_id(secret_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with id {secret_id} not found in cache",
        )
    return entry


@router.get("/", response_model=list[SecretMetadataResponse], summary="List cached secret metadata")
async def list_secrets(
    vault_name: Optional[str] = Query(None, description="Filter by vault instance name"),
    engine_id: Optional[str] = Query(None, description="Filter by engine mount path"),
    severity: Optional[str] = Query(None, description="Filter by severity profile"),
    system_id: Optional[str] = Query(None, description="Filter by assigned system"),
    owner_id: Optional[str] = Query(None, description="Filter by effective owner"),
    unassigned: Optional[bool] = Query(None, description="true: neither system nor own owners; false: the rest"),
    include_removed: bool = Query(False, description="Also list secrets that are no longer in their backend"),
    privileged: Optional[bool] = Query(None, description="Filter by the privileged flag"),
) -> list[SecretMetadataResponse]:
    """
    List all cached secret metadata with optional filtering.

    Args:
        vault_name: Filter by vault instance name.
        engine_id: Filter by engine mount path.
        severity: Filter by severity profile.
        system_id: Filter by assigned system.
        owner_id: Filter by effective owner (own owners, or else the system's owners).
        unassigned: Filter by whether the secret has neither a system nor own owners.
        include_removed: Also list secrets that sync no longer finds in their backend (#86).
        privileged: Filter by the privileged flag (#93).

    Returns:
        List of enriched secret metadata entries.
    """
    database, config, _ = _get_app_dependencies()
    _validate_severity_input(severity, config, "query parameter")
    entries = database.list_all_secrets(
        vault_name=vault_name,
        engine_id=engine_id,
        severity=severity,
        include_removed=include_removed,
        privileged=privileged,
    )
    index = AssignmentIndex(database)
    return [
        _enrich_secret(e, config, index)
        for e in entries
        if index.matches(_identity(e), system_id=system_id, owner_id=owner_id, unassigned=unassigned)
    ]


@router.delete("/removed", response_model=PurgeResult, summary="Purge removed secrets")
async def purge_removed_secrets(
    request: Request,
    vault_name: Optional[str] = Query(None, description="Only purge removed secrets of this vault"),
    engine_id: Optional[str] = Query(None, description="Only purge removed secrets of this engine"),
) -> PurgeResult:
    """
    Delete every secret that is no longer in its backend, with its system and owner assignments.

    Args:
        vault_name: Only purge removed secrets of this vault.
        engine_id: Only purge removed secrets of this engine.

    Returns:
        How many secrets were purged, and which.
    """
    database, _, _ = _get_app_dependencies()
    index = AssignmentIndex(database)
    identities = database.purge_removed(vault_name=vault_name, engine_id=engine_id)
    _record_purges(database, index, identities, request_source(request))
    purged = ["/".join(identity) for identity in identities]
    return PurgeResult(purged=len(purged), secrets=purged)


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Purge a removed secret")
async def purge_secret(secret_id: int, request: Request) -> None:
    """
    Delete a secret that is no longer in its backend, with its system and owner assignments.

    Args:
        secret_id: The secret metadata cache row ID.

    Raises:
        HTTPException: 404 if the secret isn't cached, 409 if it still exists in its backend.
    """
    database, _, _ = _get_app_dependencies()
    entry = _require_secret(database, secret_id)
    if entry.removed_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Secret {'/'.join(_identity(entry))} still exists in its backend; "
                "only removed secrets can be purged"
            ),
        )
    index = AssignmentIndex(database)
    _record_purges(database, index, database.purge_removed(secret_id=secret_id), request_source(request))


@router.get("/{secret_id}", response_model=SecretMetadataResponse, summary="Get cached secret metadata by ID")
async def get_secret(secret_id: int) -> SecretMetadataResponse:
    """
    Retrieve cached secret metadata by its database ID.

    Args:
        secret_id: The secret metadata cache row ID.

    Returns:
        Enriched secret metadata.

    Raises:
        HTTPException: If secret not found in cache.
    """
    database, config, _ = _get_app_dependencies()
    entry = _require_secret(database, secret_id)
    return _enrich_secret(entry, config, AssignmentIndex(database))


@router.put("/{secret_id}/system", response_model=SecretMetadataResponse, summary="Assign a secret to a system")
async def set_secret_system(data: SystemAssignment, secret_id: int, request: Request) -> SecretMetadataResponse:
    """
    Assign a secret to a system, or unassign it with `null`; replaces the previous assignment.

    Args:
        data: The system ID, or null.
        secret_id: The secret metadata cache row ID.

    Returns:
        The secret with its new assignment.

    Raises:
        HTTPException: 404 if the secret isn't cached, 422 if the system doesn't exist.
    """
    database, config, _ = _get_app_dependencies()
    entry = _require_secret(database, secret_id)
    if data.system_id is not None and database.get_system(data.system_id) is None:
        raise HTTPException(status_code=422, detail=f"Unknown system ID: {data.system_id}")
    before = AssignmentIndex(database).system_of(_identity(entry))
    database.set_secret_system(_identity(entry), data.system_id)
    index = AssignmentIndex(database)
    after = index.system_of(_identity(entry))
    if before != after:
        database.append_audit_event(
            "secret.system",
            request_source(request),
            identity=_identity(entry),
            before={"system": before.model_dump() if before else None},
            after={"system": after.model_dump() if after else None},
        )
    return _enrich_secret(entry, config, index)


@router.put("/{secret_id}/owners", response_model=SecretMetadataResponse, summary="Replace a secret's owners")
async def set_secret_owners(data: OwnerIds, secret_id: int, request: Request) -> SecretMetadataResponse:
    """
    Replace the owners assigned to a secret; `[]` removes them, so the system's owners apply.

    Args:
        data: The complete new list of owner IDs.
        secret_id: The secret metadata cache row ID.

    Returns:
        The secret with its new owners.

    Raises:
        HTTPException: 404 if the secret isn't cached, 422 for unknown owner IDs.
    """
    from chronowarden.api.systems import require_known_owners

    database, config, _ = _get_app_dependencies()
    entry = _require_secret(database, secret_id)
    require_known_owners(database, data.owner_ids)
    before = [owner.model_dump() for owner in AssignmentIndex(database).owners_of(_identity(entry))]
    database.set_secret_owners(_identity(entry), data.owner_ids)
    index = AssignmentIndex(database)
    after = [owner.model_dump() for owner in index.owners_of(_identity(entry))]
    if before != after:
        database.append_audit_event(
            "secret.owners",
            request_source(request),
            identity=_identity(entry),
            before={"owners": before},
            after={"owners": after},
        )
    return _enrich_secret(entry, config, index)


@router.get("/{secret_id}/history", response_model=list[AuditEvent], summary="Change history of a secret")
async def secret_history(secret_id: int) -> list[AuditEvent]:
    """
    List the audit events of one secret, newest first.

    Args:
        secret_id: The secret metadata cache row ID.

    Returns:
        Every recorded change to the secret, by its identity (so history survives a rebuilt cache).

    Raises:
        HTTPException: 404 if the secret isn't cached.
    """
    database, _, _ = _get_app_dependencies()
    vault_name, engine_id, secret_path = _identity(_require_secret(database, secret_id))
    rows = database.list_audit_events(limit=1000, vault_name=vault_name, engine_id=engine_id, secret_path=secret_path)
    return [AuditEvent.from_stored(row) for row in rows]


@router.post(
    "/{secret_id}/confirmations",
    response_model=SecretMetadataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm a rotation was applied",
)
async def confirm_rotation(data: ConfirmationCreate, secret_id: int, request: Request) -> SecretMetadataResponse:
    """
    Confirm that the newest version of a secret is applied where it is used (ADR-021).

    The next rotation then counts from the applied date when that is later than the backend's update.

    Args:
        data: When it was applied (may be in the past) and, for automation, who confirmed it.
        secret_id: The secret metadata cache row ID.

    Returns:
        The secret with its new confirmation state.

    Raises:
        HTTPException: 404 if the secret isn't cached, 409 before its first sync, 422 for an applied date before the
            version was created or in the future.
    """
    database, config, _ = _get_app_dependencies()
    entry = _require_secret(database, secret_id)
    identity = _identity(entry)
    version = current_version(database, identity)
    if version is None or version.get("current") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="The secret's versions aren't known yet; sync it first"
        )
    applied = data.applied_at if data.applied_at.tzinfo else data.applied_at.replace(tzinfo=timezone.utc)
    created = parse_date(version.get("created_time") or "")
    if applied > datetime.now(tz=timezone.utc) + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="applied_at is in the future")
    if created is not None and applied < created:
        raise HTTPException(
            status_code=422,
            detail=f"applied_at is before version {version['current']} was created ({version['created_time']})",
        )
    applied_text = applied.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    confirmation = database.add_confirmation(identity, version["current"], applied_text, data.confirmed_by)
    database.append_audit_event(
        "secret.confirmed",
        request_source(request),
        identity=identity,
        after={k: confirmation[k] for k in ("id", "version", "applied_at", "confirmed_by")},
    )
    refresh_cached_ttl(database, config, identity)
    return _enrich_secret(database.get_secret_by_id(secret_id), config, AssignmentIndex(database))


@router.put("/{secret_id}/privileged", response_model=SecretMetadataResponse, summary="Set the privileged flag")
async def set_privileged(data: PrivilegedUpdate, secret_id: int, request: Request) -> SecretMetadataResponse:
    """
    Write `chronowarden_privileged` to the backend (merged with the other metadata, ADR-004) and cache it.

    Args:
        data: The new value.
        secret_id: The secret metadata cache row ID.

    Returns:
        The secret with its new flag.

    Raises:
        HTTPException: 404 if the secret isn't cached, 503 if its vault isn't connected or the write failed.
    """
    database, config, manager = _get_app_dependencies()
    entry = _require_secret(database, secret_id)
    write_privileged(database, manager, entry, data.privileged, request_source(request))
    return _enrich_secret(database.get_secret_by_id(secret_id), config, AssignmentIndex(database))


def write_privileged(
    database: Any, manager: Any, entry: SecretMetadataCache, value: bool, source: str, reverts: Optional[int] = None
) -> None:
    """
    Write the privileged flag to the backend, cache it and record the change (also used by revert, with `reverts`).

    Raises:
        HTTPException: 503 if the vault isn't connected or the write failed.
    """
    from chronowarden.audit.observe import remember_written
    from chronowarden.metadata import PRIVILEGED_KEY

    vault = manager.get(entry.vault_name)
    if vault is None or not vault.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Vault '{entry.vault_name}' is not connected"
        )
    written = {PRIVILEGED_KEY: "true" if value else "false"}
    if not vault.write_secret_metadata(entry.secret_path, written, mount_point=entry.engine_id):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Writing {PRIVILEGED_KEY} to vault '{entry.vault_name}' failed; see the server log",
        )
    remember_written(database, _identity(entry), written)
    if entry.privileged != value:
        database.upsert_secret_metadata(entry.model_copy(update={"privileged": value}))
        database.append_audit_event(
            "secret.privileged",
            source,
            identity=_identity(entry),
            before={"privileged": entry.privileged},
            after={"privileged": value, **({"reverts": reverts} if reverts is not None else {})},
        )


def enriched_secrets(database: Any, config: AppConfig, include_removed: bool = False) -> list[SecretMetadataResponse]:
    """Every cached secret as the API returns it (status, assignments, confirmation), for compliance views."""
    index = AssignmentIndex(database)
    return [_enrich_secret(e, config, index) for e in database.list_all_secrets(include_removed=include_removed)]
