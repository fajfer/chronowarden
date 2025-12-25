# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for Vault integration."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from chronowarden.integrations import VaultIntegration
from chronowarden.metrics import INTEGRATION_HEALTH, VAULT_CONNECTIONS_TOTAL, VAULT_OPERATIONS_TOTAL

router = APIRouter(prefix="/vault", tags=["vault"])

# Global vault client (would be properly managed via dependency injection in production)
_vault_client: Optional[VaultIntegration] = None


class VaultConnectionRequest(BaseModel):
    """Request model for Vault connection."""

    address: str
    token: str
    namespace: Optional[str] = None
    mount_path: str = "secret"
    verify_ssl: bool = True


class VaultSecretRequest(BaseModel):
    """Request model for retrieving a Vault secret."""

    path: str
    key: Optional[str] = None


class VaultHealthResponse(BaseModel):
    """Response model for Vault health check."""

    connected: bool
    healthy: bool
    initialized: Optional[bool] = None
    sealed: Optional[bool] = None
    version: Optional[str] = None
    error: Optional[str] = None


@router.post("/connect", summary="Connect to Vault")
async def connect_to_vault(connection: VaultConnectionRequest) -> dict[str, str]:
    """
    Establish connection to HashiCorp Vault.

    Args:
        connection: Vault connection parameters.

    Returns:
        Success message.

    Raises:
        HTTPException: If connection fails.
    """
    global _vault_client

    _vault_client = VaultIntegration(
        address=connection.address,
        token=connection.token,
        namespace=connection.namespace,
        mount_path=connection.mount_path,
        verify_ssl=connection.verify_ssl,
    )

    if _vault_client.connect():
        VAULT_CONNECTIONS_TOTAL.labels(status="success").inc()
        INTEGRATION_HEALTH.labels(integration="vault").set(1)
        return {"message": "Successfully connected to Vault"}

    VAULT_CONNECTIONS_TOTAL.labels(status="failure").inc()
    INTEGRATION_HEALTH.labels(integration="vault").set(0)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to connect to Vault",
    )


@router.post("/disconnect", summary="Disconnect from Vault")
async def disconnect_from_vault() -> dict[str, str]:
    """
    Close connection to HashiCorp Vault.

    Returns:
        Success message.
    """
    global _vault_client

    if _vault_client:
        _vault_client.disconnect()
        _vault_client = None
        INTEGRATION_HEALTH.labels(integration="vault").set(0)

    return {"message": "Disconnected from Vault"}


@router.get("/health", response_model=VaultHealthResponse, summary="Check Vault health")
async def vault_health() -> VaultHealthResponse:
    """
    Check Vault connection and health status.

    Returns:
        Vault health status.
    """
    if not _vault_client:
        return VaultHealthResponse(
            connected=False,
            healthy=False,
            error="Not connected to Vault",
        )

    health = _vault_client.check_health()

    return VaultHealthResponse(
        connected=_vault_client.is_connected(),
        healthy=health.get("healthy", False),
        initialized=health.get("initialized"),
        sealed=health.get("sealed"),
        version=health.get("version"),
        error=health.get("error"),
    )


@router.post("/secrets/get", summary="Get secret from Vault")
async def get_vault_secret(request: VaultSecretRequest) -> dict[str, Any]:
    """
    Retrieve a secret from Vault.

    Args:
        request: Secret path and optional key.

    Returns:
        The secret data.

    Raises:
        HTTPException: If not connected or secret not found.
    """
    if not _vault_client or not _vault_client.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Not connected to Vault",
        )

    secret = _vault_client.get_secret(request.path, request.key)

    if secret is None:
        VAULT_OPERATIONS_TOTAL.labels(operation="get_secret", status="not_found").inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret not found at path: {request.path}",
        )

    VAULT_OPERATIONS_TOTAL.labels(operation="get_secret", status="success").inc()
    return {"data": secret}


@router.get("/secrets/list", summary="List secrets in Vault")
async def list_vault_secrets(path: str = "") -> dict[str, list[str]]:
    """
    List secrets at a given path in Vault.

    Args:
        path: Path to list secrets from.

    Returns:
        List of secret keys.

    Raises:
        HTTPException: If not connected to Vault.
    """
    if not _vault_client or not _vault_client.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Not connected to Vault",
        )

    secrets = _vault_client.list_secrets(path)
    VAULT_OPERATIONS_TOTAL.labels(operation="list_secrets", status="success").inc()

    return {"secrets": secrets}


@router.post("/secrets/metadata", summary="Get secret metadata from Vault")
async def get_vault_secret_metadata(request: VaultSecretRequest) -> dict[str, Any]:
    """
    Get metadata for a secret in Vault.

    Args:
        request: Secret path.

    Returns:
        Secret metadata.

    Raises:
        HTTPException: If not connected or metadata not found.
    """
    if not _vault_client or not _vault_client.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Not connected to Vault",
        )

    metadata = _vault_client.get_secret_metadata(request.path)

    if metadata is None:
        VAULT_OPERATIONS_TOTAL.labels(operation="get_metadata", status="not_found").inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata not found for path: {request.path}",
        )

    VAULT_OPERATIONS_TOTAL.labels(operation="get_metadata", status="success").inc()
    return {"metadata": metadata}
