# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Compliance evidence request and response models (#94)."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from chronowarden.config import ComplianceScope

Cadence = Literal["monthly", "quarterly", "half-yearly", "yearly"]


class SnapshotCreate(BaseModel):
    """Take an ad-hoc snapshot (label + scope) or close a reporting period (cadence + period)."""

    label: Optional[str] = Field(default=None, max_length=200, description="Free label of an ad-hoc snapshot")
    scope: Optional[ComplianceScope] = Field(default=None, description="Ad-hoc scope; periodic ones use the config")
    cadence: Optional[Cadence] = None
    period: Optional[str] = Field(default=None, description="e.g. 2026-09, 2026-Q3, 2026-H2, 2026")
    supersedes: Optional[int] = Field(default=None, description="The snapshot this one corrects")

    @model_validator(mode="after")
    def check_kind(self) -> "SnapshotCreate":
        """Exactly one kind: ad-hoc (label) or periodic (cadence and period, scope from config)."""
        periodic = self.cadence is not None or self.period is not None
        if periodic and (self.cadence is None or self.period is None):
            raise ValueError("a periodic snapshot needs both cadence and period")
        if periodic and (self.label is not None or self.scope is not None):
            raise ValueError("a periodic snapshot takes its scope from the config and has no label")
        if not periodic and not (self.label or "").strip():
            raise ValueError("an ad-hoc snapshot needs a label")
        return self


class SnapshotInfo(BaseModel):
    """A snapshot without its content."""

    id: int
    created_at: str
    label: Optional[str] = None
    cadence: Optional[str] = None
    period: Optional[str] = None
    supersedes: Optional[int] = None
    row_count: int
    sha256: str = Field(description="SHA-256 of the canonical JSON (GET .json returns exactly those bytes)")


class Snapshot(SnapshotInfo):
    """A snapshot with its parsed document."""

    document: dict[str, Any]


class GapEntry(BaseModel):
    """A secret with evidence gaps."""

    id: int
    full_path: str
    gaps: list[str]


class GapReport(BaseModel):
    """Evidence gaps in a scope, shown before taking a snapshot; snapshots don't record them."""

    scope: ComplianceScope
    total: int = Field(description="Secrets in scope")
    counts: dict[str, int] = Field(description="Secrets per gap type")
    secrets: list[GapEntry]


class PeriodStatus(BaseModel):
    """A reporting period and whether it was closed."""

    cadence: str
    period: str
    start: str
    end: str
    snapshot_id: Optional[int] = Field(default=None, description="The latest snapshot closing it, if any")
