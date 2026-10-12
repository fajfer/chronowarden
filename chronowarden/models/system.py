# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""System model definitions for Chronowarden (ADR-010)."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class OwnerRef(BaseModel):
    """An owner as referenced from a system or a secret."""

    id: str
    name: str


class SystemRef(BaseModel):
    """A system as referenced from a secret."""

    id: str
    name: str


def _check_link(value: Optional[str]) -> Optional[str]:
    """Allow only http(s) CMDB links; the UI renders them as links (no javascript: or data: URLs)."""
    if value is None or not value.strip():
        return None
    value = value.strip()
    if not value.lower().startswith(("http://", "https://")):
        raise ValueError("cmdb_uri must be an http:// or https:// URL")
    return value


def _strip_name(value: Optional[str]) -> Optional[str]:
    """Trim a system name and reject a blank one."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("name must not be blank")
    return value


class SystemBase(BaseModel):
    """Fields shared by system responses and create requests."""

    name: str = Field(max_length=200, description="Unique system name")
    description: str = Field(default="", max_length=2000, description="What the system is")
    cmdb_uri: Optional[str] = Field(default=None, max_length=2000, description="Link to the system in a CMDB")
    asset_number: Optional[str] = Field(default=None, max_length=200, description="System or asset identifier")

    _name = field_validator("name")(_strip_name)
    _cmdb_uri = field_validator("cmdb_uri")(_check_link)


class System(SystemBase):
    """A system with its owners."""

    id: str
    owners: list[OwnerRef] = Field(default_factory=list)
    created_at: Optional[str] = None


class SystemCreate(SystemBase):
    """Request body for creating a system."""

    owner_ids: list[str] = Field(default_factory=list, description="Owners of the system")


class SystemUpdate(BaseModel):
    """Request body for updating a system; omitted fields stay unchanged."""

    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    cmdb_uri: Optional[str] = Field(default=None, max_length=2000)
    asset_number: Optional[str] = Field(default=None, max_length=200)

    _name = field_validator("name")(_strip_name)
    _cmdb_uri = field_validator("cmdb_uri")(_check_link)


class OwnerIds(BaseModel):
    """Request body replacing a list of owners."""

    owner_ids: list[str] = Field(description="The complete new list of owner IDs; [] removes all")


class SystemAssignment(BaseModel):
    """Request body assigning a secret to a system."""

    system_id: Optional[str] = Field(description="System ID, or null to unassign")
