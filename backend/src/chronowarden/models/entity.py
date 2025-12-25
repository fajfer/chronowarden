# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Base model definitions for Chronowarden."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PermissionLevel(str, Enum):
    """Permission levels for users."""

    READ_ONLY = "read-only"
    READ_WRITE = "read-write"
    ADMIN = "admin"


class Entity(BaseModel):
    """Base class for users, technical users, and groups."""

    id: int
    name: str
    description: Optional[str] = None
    permission_level: PermissionLevel = PermissionLevel.READ_ONLY


class User(Entity):
    """A human user of the system."""

    email: Optional[str] = None


class TechnicalUser(Entity):
    """A technical/service account user."""

    service_name: str


class Group(Entity):
    """A group of users."""

    members: list[int] = Field(default_factory=list)
