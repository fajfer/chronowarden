# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Secret model definitions for Chronowarden."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from chronowarden.models.engine import EngineType


class SecretBase(BaseModel):
    """Base class for secrets from all engines."""

    name: str
    description: Optional[str] = None
    is_public: bool = False
    expiry_time_alert: int = Field(default=30, description="Days before expiry to alert")
    expiry_time_interval: int = Field(default=7, description="Days between reminder alerts")
    owner_id: int
    routing_ids: list[int] = Field(default_factory=list)
    backend_id: int


class Secret(SecretBase):
    """Full secret model with database fields."""

    id: int
    created_at: datetime
    expiry_date: Optional[datetime] = None
    engine_type: EngineType


class SecretCreate(SecretBase):
    """Schema for creating a new secret."""

    expiry_date: Optional[datetime] = None
    engine_type: EngineType


class SecretUpdate(BaseModel):
    """Schema for updating a secret."""

    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    expiry_time_alert: Optional[int] = None
    expiry_time_interval: Optional[int] = None
    routing_ids: Optional[list[int]] = None
    expiry_date: Optional[datetime] = None


class SecretTemplate(SecretBase):
    """Predefined defaults for secrets."""

    id: int
    template_name: str
    default_expiry_days: int = 365


class AzureKeyVaultSecret(Secret):
    """Secret stored in Azure Key Vault."""

    subscription_id: str
    resource_group: str
    vault_name: str
    secret_name: str


class HashicorpVaultSecret(Secret):
    """Secret stored in HashiCorp Vault."""

    vault_path: str
    secret_key: str
