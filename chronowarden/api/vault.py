# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for Vault integration."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel

from chronowarden.metrics import VAULT_OPERATIONS_TOTAL

router = APIRouter(prefix="/vault", tags=["vault"])


class VaultSecretRequest(BaseModel):
    """Request model for retrieving a Vault secret."""

    path: str
    key: Optional[str] = None
    mount_point: Optional[str] = None


class VaultInstanceHealth(BaseModel):
    """Health status of a single Vault instance."""

    name: str
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
        connected=connected,
        healthy=health.get("healthy", False),
        initialized=health.get("initialized"),
        sealed=health.get("sealed"),
        version=health.get("version"),
        error=error,
    )


@router.get("/{vault_name}/secrets/list", summary="List secrets in a Vault instance")
async def list_vault_secrets(
    vault_name: str = Path(description="Name of the vault instance"),
    path: str = "",
    mount_point: Optional[str] = None,
) -> dict[str, Any]:
    """
    List secrets at a given path in a specific Vault instance.

    Args:
        vault_name: Name of the vault instance.
        path: Path to list secrets from.
        mount_point: Override the default mount point.

    Returns:
        List of secret keys.

    Raises:
        HTTPException: If vault not found or not connected.
    """
    manager = _get_vault_manager()
    vault = manager.get(vault_name)

    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vault instance '{vault_name}' not found",
        )

    if not vault.is_connected():
        detail = f"Vault instance '{vault_name}' is not connected"
        if vault.last_error is not None:
            detail = f"{detail}: {vault.last_error}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )

    secrets = vault.list_secrets(path, mount_point)
    VAULT_OPERATIONS_TOTAL.labels(operation="list_secrets", status="success").inc()

    return {"vault": vault_name, "secrets": secrets}


@router.post("/{vault_name}/secrets/metadata", summary="Get secret metadata from a Vault instance")
async def get_vault_secret_metadata(
    request: VaultSecretRequest,
    vault_name: str = Path(description="Name of the vault instance"),
) -> dict[str, Any]:
    """
    Get metadata for a secret in a specific Vault instance.

    Args:
        request: Secret path.
        vault_name: Name of the vault instance.

    Returns:
        Secret metadata.

    Raises:
        HTTPException: If vault not found or metadata not found.
    """
    manager = _get_vault_manager()
    vault = manager.get(vault_name)

    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vault instance '{vault_name}' not found",
        )

    if not vault.is_connected():
        detail = f"Vault instance '{vault_name}' is not connected"
        if vault.last_error is not None:
            detail = f"{detail}: {vault.last_error}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )

    metadata = vault.get_secret_metadata(request.path, request.mount_point)

    if metadata is None:
        VAULT_OPERATIONS_TOTAL.labels(operation="get_metadata", status="not_found").inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata not found for path: {request.path}",
        )

    VAULT_OPERATIONS_TOTAL.labels(operation="get_metadata", status="success").inc()
    return {"vault": vault_name, "metadata": metadata}
