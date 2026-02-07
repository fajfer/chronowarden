# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for secrets management."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from chronowarden.models import EngineType, Secret, SecretCreate, SecretUpdate

router = APIRouter(prefix="/secrets", tags=["secrets"])

# NOTE: In-memory storage for demo purposes only.
# In production, replace with persistent database (e.g., PostgreSQL, SQLite)
_secrets_db: dict[int, Secret] = {}
_next_id = 1


@router.get("/", response_model=list[Secret], summary="List all secrets")
async def list_secrets(
    engine_type: Optional[EngineType] = Query(None, description="Filter by engine type"),
    is_public: Optional[bool] = Query(None, description="Filter by public visibility"),
) -> list[Secret]:
    """
    List all secrets with optional filtering.

    Args:
        engine_type: Filter by secret engine type.
        is_public: Filter by public visibility status.

    Returns:
        List of secrets matching the filters.
    """
    secrets = list(_secrets_db.values())

    if engine_type is not None:
        secrets = [s for s in secrets if s.engine_type == engine_type]

    if is_public is not None:
        secrets = [s for s in secrets if s.is_public == is_public]

    return secrets


@router.post("/", response_model=Secret, status_code=status.HTTP_201_CREATED, summary="Create a new secret")
async def create_secret(secret_data: SecretCreate) -> Secret:
    """
    Create a new secret.

    Args:
        secret_data: Secret creation data.

    Returns:
        The created secret.
    """
    global _next_id

    secret = Secret(
        id=_next_id,
        created_at=datetime.now(),
        **secret_data.model_dump(),
    )
    _secrets_db[_next_id] = secret
    _next_id += 1

    return secret


@router.get("/{secret_id}", response_model=Secret, summary="Get a secret by ID")
async def get_secret(secret_id: int) -> Secret:
    """
    Retrieve a secret by its ID.

    Args:
        secret_id: The secret's unique identifier.

    Returns:
        The requested secret.

    Raises:
        HTTPException: If secret not found.
    """
    if secret_id not in _secrets_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with id {secret_id} not found",
        )

    return _secrets_db[secret_id]


@router.put("/{secret_id}", response_model=Secret, summary="Update a secret")
async def update_secret(secret_id: int, secret_update: SecretUpdate) -> Secret:
    """
    Update an existing secret.

    Args:
        secret_id: The secret's unique identifier.
        secret_update: Fields to update.

    Returns:
        The updated secret.

    Raises:
        HTTPException: If secret not found.
    """
    if secret_id not in _secrets_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with id {secret_id} not found",
        )

    existing = _secrets_db[secret_id]
    update_data = secret_update.model_dump(exclude_unset=True)

    updated_secret = existing.model_copy(update=update_data)
    _secrets_db[secret_id] = updated_secret

    return updated_secret


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a secret")
async def delete_secret(secret_id: int) -> None:
    """
    Delete a secret by its ID.

    Args:
        secret_id: The secret's unique identifier.

    Raises:
        HTTPException: If secret not found.
    """
    if secret_id not in _secrets_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with id {secret_id} not found",
        )

    del _secrets_db[secret_id]


@router.get("/public/", response_model=list[Secret], summary="List public secrets")
async def list_public_secrets() -> list[Secret]:
    """
    List all publicly visible secrets (no authentication required).

    Returns:
        List of public secrets.
    """
    return [s for s in _secrets_db.values() if s.is_public]
