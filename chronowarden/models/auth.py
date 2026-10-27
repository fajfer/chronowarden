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
