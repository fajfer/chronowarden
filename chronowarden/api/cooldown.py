# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Minimum intervals between expensive requests (manual sync, snapshots), kept in memory per process."""

import math
import threading
import time
from collections.abc import Callable

from fastapi import HTTPException, status


class Cooldown:
    """Allows an action once per key every N seconds."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def take(self, key: str, seconds: int) -> int:
        """
        Start the action for a key if its cooldown has passed.

        Returns:
            0 if the action may run (and the cooldown restarts), else the seconds left to wait.
        """
        if seconds <= 0:
            return 0
        with self._lock:
            now = self._clock()
            last = self._last.get(key)
            if last is not None and now - last < seconds:
                return math.ceil(seconds - (now - last))
            self._last[key] = now
            return 0


def enforce(cooldown: Cooldown, key: str, seconds: int, what: str) -> None:
    """
    Start the action, or refuse it while its cooldown runs.

    Raises:
        HTTPException: 429 with `Retry-After` while the cooldown runs.
    """
    wait = cooldown.take(key, seconds)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"{what} ran less than {seconds}s ago; try again in {wait}s",
            headers={"Retry-After": str(wait)},
        )
