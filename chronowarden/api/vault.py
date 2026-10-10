# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for Vault integration."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel

router = APIRouter(prefix="/vault", tags=["vault"])


class VaultInstanceHealth(BaseModel):
    """Health status of a single Vault instance."""

    name: str
    address: str
    connected: bool
    healthy: bool
    initialized: Optional[bool] = None
    sealed: Optional[bool] = None
    version: Optional[str] = None
    error: Optional[str] = None


def _get_vault_manager() -> Any:
    """
    Get the vault manager from the app module.

    Returns:
        The VaultManager instance.
    """
    from chronowarden.app import vault_manager

    return vault_manager


@router.get("/instances", summary="List configured Vault instances")
async def list_vault_instances() -> dict[str, list[str]]:
    """
    List all configured Vault instance names.

    Returns:
        List of vault instance names.
    """
    manager = _get_vault_manager()
    return {"instances": manager.vault_names}


@router.get("/health", response_model=list[VaultInstanceHealth], summary="Check all Vault instances health")
async def all_vault_health() -> list[VaultInstanceHealth]:
    """
    Check health of all configured Vault instances.

    Returns:
        Health status for each Vault instance.
    """
    manager = _get_vault_manager()
    all_health = manager.health()

    return [
        VaultInstanceHealth(
            name=name,
            address=health.get("address", ""),
            connected=health.get("connected", False),
            healthy=health.get("healthy", False),
            initialized=health.get("initialized"),
            sealed=health.get("sealed"),
            version=health.get("version"),
            error=health.get("error"),
        )
        for name, health in all_health.items()
    ]


@router.get(
    "/{vault_name}/health",
    response_model=VaultInstanceHealth,
    summary="Check a specific Vault instance health",
)
async def vault_instance_health(
    vault_name: str = Path(description="Name of the vault instance"),
) -> VaultInstanceHealth:
    """
    Check health of a specific Vault instance.

    Args:
        vault_name: Name of the vault instance.

    Returns:
        Health status for the Vault instance.

    Raises:
        HTTPException: If vault instance not found.
    """
    manager = _get_vault_manager()
    vault = manager.get(vault_name)

    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vault instance '{vault_name}' not found",
        )

    health = vault.check_health()
    connected = vault.is_connected()
    error = health.get("error")
    if not connected and vault.last_error is not None:
        error = vault.last_error

    return VaultInstanceHealth(
        name=vault_name,
        address=vault.address,
        connected=connected,
        healthy=health.get("healthy", False),
        initialized=health.get("initialized"),
        sealed=health.get("sealed"),
        version=health.get("version"),
        error=error,
    )
