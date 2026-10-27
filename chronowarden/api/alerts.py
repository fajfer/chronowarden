# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""API routes for alerts and the webhook delivery log (#99, ADR-025)."""

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from chronowarden.auth import authenticated
from chronowarden.models.alert import Delivery, FiringAlert

router = APIRouter(tags=["alerts"], dependencies=[Depends(authenticated)])


def _get_db() -> Any:
    """Get the database from the app module."""
    from chronowarden.app import db

    return db


@router.get("/alerts", response_model=list[FiringAlert], summary="Alerts firing now")
async def list_alerts() -> list[FiringAlert]:
    """List the alerts that are firing, oldest first."""
    return [
        FiringAlert(
            fingerprint=state["fingerprint"],
            alertname=state["alertname"],
            labels=json.loads(state["labels"]),
            annotations=json.loads(state["annotations"]),
            starts_at=state["starts_at"],
            last_sent_at=state["last_sent_at"],
        )
        for state in _get_db().list_firing_alerts()
    ]


@router.get("/webhooks/deliveries", response_model=list[Delivery], summary="Webhook delivery log")
async def list_deliveries(
    limit: int = Query(default=100, ge=1, le=1000),
    before_id: Optional[int] = Query(default=None, description="Page backwards from this delivery id"),
) -> list[Delivery]:
    """List webhook deliveries, newest first, without payloads or URLs."""
    return [Delivery(**row) for row in _get_db().list_deliveries(limit=limit, before_id=before_id)]
