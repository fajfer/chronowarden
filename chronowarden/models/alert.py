# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Alert and webhook delivery response models (#99, ADR-025)."""

from typing import Optional

from pydantic import BaseModel, Field


class FiringAlert(BaseModel):
    """An alert that is firing now."""

    fingerprint: str
    alertname: str
    labels: dict[str, str]
    annotations: dict[str, str]
    starts_at: str
    last_sent_at: Optional[str] = None


class Delivery(BaseModel):
    """One webhook in the delivery log (no payload, no URL)."""

    id: int
    created_at: str
    receiver: str = Field(description="owner:<id> or default:<name>")
    route_id: Optional[str] = None
    default_route: Optional[str] = None
    alertname: str
    fingerprint: Optional[str] = None
    status: str = Field(description="pending, delivered or failed")
    attempts: int
    next_attempt_at: Optional[str] = None
    last_attempt_at: Optional[str] = None
    last_status_code: Optional[int] = None
    last_error: Optional[str] = None
