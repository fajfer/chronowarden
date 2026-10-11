# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Secret metadata response models for Chronowarden."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from chronowarden.models.system import OwnerRef, SystemRef


class SecretStatus(str, Enum):
    """Computed status of a secret based on TTL and days remaining."""

    EXPIRED = "expired"
    WARNING = "warning"
    OK = "ok"
    NO_TTL = "no_ttl"


class SecretMetadataResponse(BaseModel):
    """Response model for secret metadata from the cache."""

    id: int
    vault_name: str
    engine_id: str
    secret_path: str
    full_path: str = Field(description="Computed: vault_name/engine_id/secret_path")
    ttl: Optional[str] = None
    updated_time: Optional[str] = Field(default=None, description="Backend's last update (rotation) of the secret")
    ttl_date: Optional[datetime] = None
    days_remaining: Optional[int] = None
    severity: str = "default"
    rotation_period_days: int = 365
    alert_threshold_days: int = 30
    last_synced: Optional[datetime] = None
    status: SecretStatus = SecretStatus.NO_TTL
    system: Optional[SystemRef] = Field(default=None, description="Assigned system, or null when unassigned")
    owners: list[OwnerRef] = Field(default_factory=list, description="Owners assigned to the secret itself")
    privileged: bool = Field(default=False, description='chronowarden_privileged is "true" in the backend (#93)')
    confirmation_required: bool = Field(default=False, description="Rotations must be confirmed as applied (ADR-021)")
    awaiting_confirmation: bool = Field(default=False, description="The newest version isn't confirmed yet")
    confirmation_overdue: bool = Field(default=False, description="Awaiting longer than the grace period")
    last_confirmation: Optional["Confirmation"] = None
    removed_at: Optional[datetime] = Field(
        default=None, description="When sync stopped finding the secret in its backend; null while it exists"
    )
    effective_owners: list[OwnerRef] = Field(
        default_factory=list, description="The secret's own owners, or else its system's owners (ADR-010)"
    )


class PurgeResult(BaseModel):
    """Result of purging removed secrets."""

    purged: int = Field(description="Number of removed secrets deleted with their assignments")
    secrets: list[str] = Field(description="Full paths of the purged secrets")


class Confirmation(BaseModel):
    """A confirmation that a secret's version was applied where it is used."""

    id: int
    version: int
    applied_at: str
    confirmed_by: Optional[str] = None
    recorded_at: str


class ConfirmationCreate(BaseModel):
    """Request body confirming the newest version of a secret."""

    applied_at: datetime = Field(description="When it was applied; may be in the past, never before the version")
    confirmed_by: Optional[str] = Field(
        default=None, max_length=200, description="Who or what confirmed it, e.g. a pipeline name"
    )


class PrivilegedUpdate(BaseModel):
    """Request body setting the privileged flag."""

    privileged: bool


SecretMetadataResponse.model_rebuild()
