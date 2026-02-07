# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Owner model definitions for Chronowarden."""

from typing import Optional

from pydantic import BaseModel, Field


class NotificationRouteBase(BaseModel):
    """Base notification route model."""

    type: str = Field(description="Route type: 'email' or 'webhook'")
    address: str = Field(description="Email address or webhook URL")
    message_template: str = Field(
        default="Secret {secret_name} in {vault} expires in {days_until_expiry} days",
        description="Notification message template",
    )


class NotificationRoute(NotificationRouteBase):
    """Full notification route with ID."""

    id: str
    owner_id: str
    created_at: Optional[str] = None


class NotificationRouteCreate(NotificationRouteBase):
    """Schema for creating a notification route."""

    pass


class OwnerBase(BaseModel):
    """Base owner model."""

    name: str = Field(description="Owner display name")
    email: str = Field(description="Owner email address")


class Owner(OwnerBase):
    """Full owner model with all fields."""

    id: str
    notification_routes: list[NotificationRoute] = Field(default_factory=list)
    created_at: Optional[str] = None


class OwnerCreate(OwnerBase):
    """Schema for creating an owner."""

    pass


class OwnerUpdate(BaseModel):
    """Schema for updating an owner."""

    name: Optional[str] = None
    email: Optional[str] = None
