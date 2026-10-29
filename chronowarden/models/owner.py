# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Owner model definitions for Chronowarden."""

from typing import Literal, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


class NotificationRouteBase(BaseModel):
    """Base notification route model."""

    type: Literal["webhook"] = Field(description="Route type; only 'webhook' (email was removed in 0.7, ADR-022)")
    address: str = Field(max_length=2000, description="Webhook URL")
    message_template: str = Field(
        default="Secret {secret_name} in {vault} expires in {days_until_expiry} days",
        max_length=2000,
        description="Notification message template",
    )


class NotificationRoute(NotificationRouteBase):
    """Full notification route with ID."""

    id: str
    owner_id: str
    created_at: Optional[str] = None
    signed: bool = Field(default=False, description="Deliveries carry a Standard Webhooks signature (ADR-025)")


class NotificationRouteCreate(NotificationRouteBase):
    """Schema for creating a notification route."""

    @field_validator("address")
    @classmethod
    def check_http(cls, value: str) -> str:
        """Webhooks are POSTed over HTTP(S) only (no file:, gopher: or other schemes) to a well-formed host."""
        value = value.strip()
        if any(character.isspace() or not character.isprintable() for character in value):
            raise ValueError("the webhook address must not contain whitespace or control characters")
        try:
            parts = urlsplit(value)
            _ = parts.port  # raises for a non-numeric or out-of-range port
        except ValueError as exc:
            raise ValueError(f"the webhook address is not a valid URL: {exc}") from exc
        if parts.scheme.lower() not in ("http", "https"):
            raise ValueError("the webhook address must be an http:// or https:// URL")
        if not parts.hostname:
            raise ValueError("the webhook address must name a host")
        return value


class SigningSecret(BaseModel):
    """A route's new signing secret, returned only by the request that creates it (ADR-025)."""

    route_id: str
    secret: str = Field(description="Standard Webhooks secret (whsec_...); store it in the receiver now")


class RouteTestResult(BaseModel):
    """The outcome of sending a test webhook to a route."""

    success: bool
    status_code: Optional[int] = None
    message: str


class OwnerBase(BaseModel):
    """Base owner model."""

    name: str = Field(max_length=200, description="Owner display name")
    email: str = Field(max_length=320, description="Owner email address; a user with this email acts for the owner")
    idp_group: Optional[str] = Field(
        default=None, max_length=256, description="IdP group whose members act for the owner (ADR-026)"
    )


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

    name: Optional[str] = Field(default=None, max_length=200)
    email: Optional[str] = Field(default=None, max_length=320)
    idp_group: Optional[str] = Field(default=None, max_length=256, description="An empty string clears it")
