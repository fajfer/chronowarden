# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Sync every vault on a schedule, and once for the one-shot command (ADR-013, #74)."""

import asyncio
import logging
from typing import Any, Optional

from chronowarden.api.sync import sync_vault_now

logger = logging.getLogger("uvicorn.error")

# Lets the reconnect loop and the first requests settle before the first scheduled sync
STARTUP_DELAY_SECONDS = 10.0


async def sync_connected(manager: Any, config: Any, database: Any) -> dict[str, Optional[int]]:
    """
    Sync every connected vault through the same per-vault lock as the API.

    Returns:
        Secrets synced per vault, or None for a vault that is disconnected or whose sync failed.
    """
    results: dict[str, Optional[int]] = {}
    for name in manager.vault_names:
        vault = manager.get(name)
        if vault is None or not await asyncio.to_thread(vault.is_connected):
            results[name] = None
            continue
        try:
            results[name] = len(await sync_vault_now(manager, name, config, database))
        except Exception:  # top level of a background job: one vault's failure must not stop the others
            logger.exception("Sync of vault '%s' failed", name)
            results[name] = None
    return results


class SyncScheduler:
    """Syncs every connected vault shortly after startup, then every `polling_interval`."""

    def __init__(self, manager: Any, config: Any, database: Any, startup_delay: float = STARTUP_DELAY_SECONDS) -> None:
        self._manager = manager
        self._config = config
        self._database = database
        self._startup_delay = startup_delay
        self._task: Optional[asyncio.Task[None]] = None

    def start(self) -> None:
        """Start the schedule, unless `polling_interval` is `off`."""
        interval = self._config.polling_seconds
        if interval is None:
            logger.info("Scheduled sync is off (polling_interval: off)")
            return
        self._task = asyncio.create_task(self._run(interval))
        logger.info("Scheduled sync every %s", self._config.polling_interval)

    def stop(self) -> None:
        """Cancel the schedule."""
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self, interval: int) -> None:
        await asyncio.sleep(self._startup_delay)
        while True:
            results = await sync_connected(self._manager, self._config, self._database)
            synced = {name: count for name, count in results.items() if count is not None}
            skipped = sorted(name for name, count in results.items() if count is None)
            logger.info(
                "Scheduled sync: %d vault(s), %d secret(s)%s",
                len(synced),
                sum(synced.values()),
                f"; not synced: {', '.join(skipped)}" if skipped else "",
            )
            await asyncio.sleep(interval)
