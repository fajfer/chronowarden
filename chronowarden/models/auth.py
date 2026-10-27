# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Models for the caller's identity and API tokens (ADR-026)."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from chronowarden.config import AuthMode, Role


class Me(BaseModel):
    """The caller, as the UI needs it to show and hide controls (the server re-checks every request)."""

    auth_mode: AuthMode
    name: str
    email: Optional[str] = None
    role: Role
    kind: Literal["session", "token", "proxy", "anonymous"]
    owner_ids: list[str] = Field(default_factory=list, description="Owners the caller acts for")


class LogoutResult(BaseModel):
    """Where the browser goes after logging out."""

    logout_url: Optional[str] = Field(default=None, description="The proxy's sign-out URL, when there is one")


class ApiTokenCreate(BaseModel):
    """Request body for a new API token."""

    name: str = Field(min_length=1, max_length=100, description="Unique; recorded as token:<name> in the audit log")
    role: Role
    owner_id: Optional[str] = Field(default=None, description="Required for the owner role: the owner it acts for")
    expires_in_days: int = Field(ge=1, description="Days until it expires; at most auth.token_max_lifetime")


class ApiToken(BaseModel):
    """An API token as listed; the token itself is never shown again."""

    id: str
    name: str
    role: Role
    owner_id: Optional[str] = None
    created_at: str
    expires_at: str
    last_used_at: Optional[str] = None
    revoked_at: Optional[str] = None


class NewApiToken(ApiToken):
    """A token just created, with its secret value, returned only by that request."""

    token: str = Field(description="Send as 'Authorization: Bearer <token>'; store it now, it can't be shown again")
