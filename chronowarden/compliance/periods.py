# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Reporting periods: IDs like 2026-Q3 and their UTC bounds."""

from datetime import datetime, timedelta, timezone
from typing import NamedTuple

# Months per period kind
_MONTHS = {"monthly": 1, "quarterly": 3, "half-yearly": 6, "yearly": 12}


class Period(NamedTuple):
    """One reporting period: [start, end) in UTC."""

    cadence: str
    id: str
    start: datetime
    end: datetime


def _period_id(cadence: str, start: datetime) -> str:
    """Name a period: 2026-09, 2026-Q3, 2026-H2 or 2026."""
    index = (start.month - 1) // _MONTHS[cadence] + 1
    return {
        "monthly": f"{start.year}-{start.month:02d}",
        "quarterly": f"{start.year}-Q{index}",
        "half-yearly": f"{start.year}-H{index}",
        "yearly": f"{start.year}",
    }[cadence]


def period_containing(cadence: str, moment: datetime) -> Period:
    """
    Return the period of a cadence that contains a moment.

    Args:
        cadence: monthly, quarterly, half-yearly or yearly.
        moment: Any timezone-aware datetime.

    Returns:
        The period.
    """
    moment = moment.astimezone(timezone.utc)
    months = _MONTHS[cadence]
    first_month = (moment.month - 1) // months * months + 1
    start = datetime(moment.year, first_month, 1, tzinfo=timezone.utc)
    end_month = first_month + months
    end = datetime(moment.year + (end_month - 1) // 12, (end_month - 1) % 12 + 1, 1, tzinfo=timezone.utc)
    return Period(cadence, _period_id(cadence, start), start, end)


def ended_periods(cadence: str, since: datetime, now: datetime) -> list[Period]:
    """
    List the periods of a cadence that ended after `since` and before `now`, oldest first.

    Args:
        cadence: monthly, quarterly, half-yearly or yearly.
        since: Only periods that end after this (e.g. when Chronowarden started recording).
        now: The current time.

    Returns:
        The ended periods.
    """
    periods: list[Period] = []
    period = period_containing(cadence, now)
    while True:
        period = period_containing(cadence, period.start - timedelta(seconds=1))
        if period.end <= since:
            break
        periods.append(period)
    return list(reversed(periods))


def period_by_id(cadence: str, period_id: str) -> Period:
    """
    Parse a period ID of a cadence.

    Raises:
        ValueError: If the ID doesn't belong to the cadence.
    """
    try:
        year = int(period_id[:4])
        if cadence == "yearly" and len(period_id) == 4:
            month = 1
        elif cadence == "monthly" and period_id[4] == "-" and len(period_id) == 7:
            month = int(period_id[5:7])
        elif cadence == "quarterly" and period_id[4:6] == "-Q" and len(period_id) == 7:
            month = (int(period_id[6]) - 1) * 3 + 1
        elif cadence == "half-yearly" and period_id[4:6] == "-H" and len(period_id) == 7:
            month = (int(period_id[6]) - 1) * 6 + 1
        else:
            raise ValueError
        period = period_containing(cadence, datetime(year, month, 1, tzinfo=timezone.utc))
    except (ValueError, IndexError):
        raise ValueError(f"'{period_id}' isn't a {cadence} period (e.g. 2026-09, 2026-Q3, 2026-H2, 2026)") from None
    if period.id != period_id:
        raise ValueError(f"'{period_id}' isn't a {cadence} period")
    return period
