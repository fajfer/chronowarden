# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Secret metadata response models for Chronowarden."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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
    ttl_date: Optional[datetime] = None
    days_remaining: Optional[int] = None
    severity: str = "default"
    rotation_period_days: int = 365
    alert_threshold_days: int = 30
    last_synced: Optional[datetime] = None
    status: SecretStatus = SecretStatus.NO_TTL
