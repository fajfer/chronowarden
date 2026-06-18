# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for metadata synchronization."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, status

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

    Args:
        vault_name: Name of the vault instance.

    Returns:
        Sync results summary.

    Raises:
        HTTPException: If vault not found or not connected.
    """
    from chronowarden.metadata import detect_changes

    manager, config, database = _get_app_dependencies()
    vault = manager.get(vault_name)

    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vault instance '{vault_name}' not found",
        )

    if not vault.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vault instance '{vault_name}' is not connected",
        )

    updated = detect_changes(vault, vault_name, config, database)

    return {
        "vault": vault_name,
        "secrets_synced": len(updated),
        "secrets": [
            {
                "engine": entry.engine_id,
                "path": entry.secret_path,
                "ttl": entry.ttl,
                "severity": entry.severity,
                "enabled": entry.enabled,
            }
            for entry in updated
        ],
    }
