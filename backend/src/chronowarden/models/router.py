# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Router model definitions for Chronowarden."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class RouterType(str, Enum):
    """Types of notification routers."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"


class Router(BaseModel):
    """Base class for notification routing."""

    id: int
    name: str
    router_type: RouterType
    enabled: bool = True
    owner_id: int


class EmailRouter(Router):
    """Email notification router."""

    router_type: RouterType = RouterType.EMAIL
    email_address: str
    smtp_server: Optional[str] = None


class WebhookRouter(Router):
    """Webhook notification router."""

    router_type: RouterType = RouterType.WEBHOOK
    webhook_url: str
    headers: dict[str, str] = {}
