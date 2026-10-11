# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Audit log response models (ADR-014)."""

import json
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """One audit log event; before/after are the parsed values."""

    id: int
    timestamp: str
    source: str = Field(description="sync, ui, api or config")
    actor: Optional[str] = Field(default=None, description="Who made the change; null until authentication (0.9)")
    event_type: str
    subject: Optional[str] = Field(default=None, description="e.g. system:<id>, owner:<id> or config")
    vault_name: Optional[str] = None
    engine_id: Optional[str] = None
    secret_path: Optional[str] = None
    before: Any = None
    after: Any = None
    prev_hash: str
    hash: str

    @classmethod
    def from_stored(cls, row: dict) -> "AuditEvent":
        """Build from a stored row, parsing the before/after JSON text."""
        values = dict(row)
        for key in ("before", "after"):
            values[key] = None if values[key] is None else json.loads(values[key])
        return cls(**values)


class AuditChainStatus(BaseModel):
    """Result of verifying the hash chain."""

    valid: bool
    events: int
    head_hash: str = Field(description="Hash of the newest event; record it to detect later truncation")
    first_invalid_id: Optional[int] = None
    reason: Optional[str] = None
