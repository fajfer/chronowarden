# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""The one timestamp format Chronowarden stores and returns: ISO 8601 UTC with microseconds and a Z."""

from datetime import datetime, timezone
from typing import Optional


def utc_timestamp(moment: Optional[datetime] = None) -> str:
    """
    Format a moment (default: now) as e.g. 2026-10-12T09:10:35.296000Z.

    Args:
        moment: A timezone-aware datetime; None means now.

    Returns:
        The timestamp text, sortable as a string.
    """
    moment = moment or datetime.now(tz=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
