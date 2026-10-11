# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for reading cached secret metadata."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status

from chronowarden.assignments import AssignmentIndex
from chronowarden.config import AppConfig
from chronowarden.database import SecretIdentity, SecretMetadataCache
from chronowarden.models.secret import SecretMetadataResponse, SecretStatus
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
    from chronowarden.metadata import parse_date

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
        ttl_date=ttl_date,
        days_remaining=days_remaining,
        severity=severity,
        rotation_period_days=rotation_days,
        alert_threshold_days=alert_days,
        last_synced=last_synced,
        status=_compute_status(days_remaining, alert_days),
        system=index.system_of(_identity(entry)),
        owners=index.owners_of(_identity(entry)),
        effective_owners=index.effective_owners_of(_identity(entry)),
    )


def _identity(entry: SecretMetadataCache) -> SecretIdentity:
    """Return the secret's real identity, which assignments are keyed by (ADR-017)."""
    return (entry.vault_name, entry.engine_id, entry.secret_path)


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

    Returns:
        List of enriched secret metadata entries.
    """
    database, config, _ = _get_app_dependencies()
    _validate_severity_input(severity, config, "query parameter")
    entries = database.list_all_secrets(
        vault_name=vault_name,
        engine_id=engine_id,
        severity=severity,
    )
    index = AssignmentIndex(database)
    return [
        _enrich_secret(e, config, index)
        for e in entries
        if index.matches(_identity(e), system_id=system_id, owner_id=owner_id, unassigned=unassigned)
    ]


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
async def set_secret_system(data: SystemAssignment, secret_id: int) -> SecretMetadataResponse:
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
    previous = database.set_secret_system(_identity(entry), data.system_id)
    logger.info("Secret %s system changed from %s to %s", "/".join(_identity(entry)), previous, data.system_id)
    return _enrich_secret(entry, config, AssignmentIndex(database))


@router.put("/{secret_id}/owners", response_model=SecretMetadataResponse, summary="Replace a secret's owners")
async def set_secret_owners(data: OwnerIds, secret_id: int) -> SecretMetadataResponse:
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
    previous = database.set_secret_owners(_identity(entry), data.owner_ids)
    logger.info(
        "Secret %s owners changed from %s to %s", "/".join(_identity(entry)), previous, sorted(set(data.owner_ids))
    )
    return _enrich_secret(entry, config, AssignmentIndex(database))
