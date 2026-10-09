# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for metadata synchronization."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, status

from chronowarden.database import SecretMetadataCache

router = APIRouter(prefix="/sync", tags=["sync"])

logger = logging.getLogger("uvicorn.error")


def _get_app_dependencies() -> tuple[Any, Any, Any]:
    """
    Get the vault manager, config, and database from the app module.

    Returns:
        Tuple of (VaultManager, AppConfig, Database).
    """
    from chronowarden.app import app_config, db, vault_manager

    return vault_manager, app_config, db


async def sync_vault_now(manager: Any, vault_name: str, config: Any, database: Any) -> list[SecretMetadataCache]:
    """
    Sync one vault while holding its sync lock, running the blocking backend calls in a worker thread.

    Used by the sync endpoint and by the sync that follows a background reconnect.

    Args:
        manager: The VaultManager.
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
        return await asyncio.to_thread(metadata.detect_changes, vault, vault_name, config, database)


@router.post(
    "/vault/{vault_name}",
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
        HTTPException: 404 if the vault is unknown; 503 if it can't be reconnected. The 503 detail has
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
