# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for secret metadata retrieval and management."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status

from chronowarden.config import AppConfig
from chronowarden.database import SecretMetadataCache
from chronowarden.models.secret import SecretMetadataResponse, SecretMetadataUpdate, SecretStatus

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


def _compute_status(days_remaining: Optional[int]) -> SecretStatus:
    """
    Compute the secret status from days remaining.

    Args:
        days_remaining: Number of days until expiry, or None.

    Returns:
        The computed SecretStatus.
    """
    if days_remaining is None:
        return SecretStatus.NO_TTL
    if days_remaining <= 0:
        return SecretStatus.EXPIRED
    if days_remaining <= 30:
        return SecretStatus.WARNING
    return SecretStatus.OK


def _validate_severity_input(severity: Optional[str], config: AppConfig, request_source: str) -> None:
    """
    Validate a request severity value against configured expiry profiles.

    Args:
        severity: Requested severity value.
        config: Application configuration.
        request_source: Human-readable request source label.

    Raises:
        HTTPException: If severity is unknown.
    """
    if severity is None:
        return

    if severity in config.expiry_profiles:
        return

    allowed_values = ", ".join(sorted(config.expiry_profiles))
    raise HTTPException(
        status_code=422,
        detail=f"Invalid severity '{severity}' in {request_source}. Allowed values: {allowed_values}",
    )


def _enrich_secret(entry: SecretMetadataCache, config: AppConfig) -> SecretMetadataResponse:
    """
    Build a SecretMetadataResponse from a cache entry with computed fields.

    Args:
        entry: The raw database cache entry.
        config: Application configuration for severity/rotation lookups.

    Returns:
        Enriched response model.
    """
    from chronowarden.metadata import parse_date

    severity = entry.severity or "default"
    rotation_days = config.get_rotation_days(severity)
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
        enabled=entry.enabled,
        last_synced=last_synced,
        status=_compute_status(days_remaining),
    )


@router.get("/", response_model=list[SecretMetadataResponse], summary="List cached secret metadata")
async def list_secrets(
    vault_name: Optional[str] = Query(None, description="Filter by vault instance name"),
    engine_id: Optional[str] = Query(None, description="Filter by engine mount path"),
    severity: Optional[str] = Query(None, description="Filter by severity profile"),
    enabled: Optional[bool] = Query(None, description="Filter by monitoring enabled/disabled"),
) -> list[SecretMetadataResponse]:
    """
    List all cached secret metadata with optional filtering.

    Args:
        vault_name: Filter by vault instance name.
        engine_id: Filter by engine mount path.
        severity: Filter by severity profile.
        enabled: Filter by monitoring enabled/disabled.

    Returns:
        List of enriched secret metadata entries.
    """
    database, config, _ = _get_app_dependencies()
    _validate_severity_input(severity, config, "query parameter")
    entries = database.list_all_secrets(
        vault_name=vault_name,
        engine_id=engine_id,
        severity=severity,
        enabled=enabled,
    )
    return [_enrich_secret(e, config) for e in entries]


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
    entry = database.get_secret_by_id(secret_id)

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with id {secret_id} not found in cache",
        )

    return _enrich_secret(entry, config)


@router.patch("/{secret_id}", response_model=SecretMetadataResponse, summary="Update secret metadata")
async def update_secret_metadata(secret_id: int, body: SecretMetadataUpdate) -> SecretMetadataResponse:
    """
    Update Chronowarden-specific metadata fields for a cached secret.

    Only severity and enabled can be modified. Changes are written to
    both the local cache and the vault's custom_metadata.

    Args:
        secret_id: The secret metadata cache row ID.
        body: Fields to update.

    Returns:
        The updated secret metadata.

    Raises:
        HTTPException: If secret not found or vault is unavailable.
    """
    database, config, manager = _get_app_dependencies()
    _validate_severity_input(body.severity, config, "request body")
    entry = database.get_secret_by_id(secret_id)

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with id {secret_id} not found in cache",
        )

    vault = manager.get(entry.vault_name)
    if not vault or not vault.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vault instance '{entry.vault_name}' is not connected",
        )

    metadata_fields: dict[str, str] = {}
    if body.severity is not None:
        metadata_fields["chronowarden_severity"] = body.severity
    if body.enabled is not None:
        metadata_fields["chronowarden_enabled"] = str(body.enabled).lower()

    if metadata_fields:
        try:
            vault.write_secret_metadata(entry.secret_path, metadata_fields, mount_point=entry.engine_id)
        except Exception:
            logger.exception("Failed to write metadata to vault for secret %d", secret_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to update metadata in vault",
            )

    database.update_secret_metadata_fields(
        secret_id,
        severity=body.severity,
        enabled=body.enabled,
    )

    updated = database.get_secret_by_id(secret_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with id {secret_id} not found after update",
        )

    return _enrich_secret(updated, config)
