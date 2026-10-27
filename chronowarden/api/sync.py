# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for metadata synchronization."""

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, status

from chronowarden.alerting.engine import evaluate_inventory
from chronowarden.api.cooldown import Cooldown, enforce
from chronowarden.auth import authenticated, owner_or_admin
from chronowarden.database import SecretMetadataCache
from chronowarden.metrics.refresh import refresh_secret_metrics

router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(authenticated)])

_cooldown = Cooldown()


def _get_app_dependencies() -> tuple[Any, Any, Any]:
    """
    Get the vault manager, config, and database from the app module.

    Returns:
        Tuple of (ProviderManager, AppConfig, Database).
    """
    from chronowarden.app import app_config, db, vault_manager

    return vault_manager, app_config, db


async def sync_vault_now(manager: Any, vault_name: str, config: Any, database: Any) -> list[SecretMetadataCache]:
    """
    Sync one vault while holding its sync lock, running the blocking backend calls in a worker thread.

    Used by the sync endpoint, the schedule, the one-shot command and the sync that follows a background reconnect.
    Refreshes the secret metrics (#71) and evaluates alerts (#99) afterwards.

    Args:
        manager: The ProviderManager.
        vault_name: Name of the vault instance.
        config: Application configuration.
        database: Database for internal state.

    Returns:
        The synced metadata cache entries (empty if the vault is unknown).
    """
    from chronowarden import metadata

    vault = manager.get(vault_name)
    if vault is None:
        return []
    async with manager.sync_lock(vault_name):
        updated = await asyncio.to_thread(metadata.detect_changes, vault, vault_name, config, database)
    await asyncio.to_thread(refresh_secret_metrics, database, config)
    await asyncio.to_thread(evaluate_inventory, database, config, datetime.now(tz=timezone.utc))
    return updated


@router.post(
    "/provider/{vault_name}",
    dependencies=[Depends(owner_or_admin)],
    summary="Trigger immediate sync for a vault",
    status_code=status.HTTP_200_OK,
)
async def sync_vault(
    vault_name: str = Path(description="Name of the vault instance to sync"),
) -> dict[str, Any]:
    """
    Trigger an immediate metadata sync for a specific vault.

    A disconnected vault gets one reconnect attempt first (AppRole logins get a new token).

    Args:
        vault_name: Name of the vault instance.

    Returns:
        Sync results summary.

    Raises:
        HTTPException: 404 if the vault is unknown; 429 within `manual_sync_cooldown` of the last request for the
            vault (reconnect attempts count); 503 if it can't be reconnected. The 503 detail has
            `message`, `reason` (last error kind), `error` and `retry_scheduled`.
    """
    manager, config, database = _get_app_dependencies()
    manager.start_reconnect_loop()
    vault = manager.get(vault_name)

    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vault instance '{vault_name}' not found",
        )
    enforce(_cooldown, vault_name, config.manual_sync_cooldown, f"A sync of vault '{vault_name}'")

    connected = await asyncio.to_thread(vault.is_connected)
    if not connected and not await asyncio.to_thread(manager.reconnect, vault_name):
        reason = vault.last_error_kind or "unknown"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": f"Vault instance '{vault_name}' is not connected",
                "reason": reason,
                "error": vault.last_error,
                "retry_scheduled": reason != "auth",
            },
        )

    updated = await sync_vault_now(manager, vault_name, config, database)

    return {
        "vault": vault_name,
        "secrets_synced": len(updated),
        "secrets": [
            {
                "engine": entry.engine_id,
                "path": entry.secret_path,
                "ttl": entry.ttl,
                "severity": entry.severity,
            }
            for entry in updated
        ],
    }
