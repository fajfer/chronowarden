# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Command line: `python -m chronowarden sync` syncs every vault once and exits, e.g. in a CronJob (ADR-013)."""

import argparse
import asyncio
import logging.config
import sys
from pathlib import Path
from typing import Optional

from uvicorn.config import LOGGING_CONFIG

from chronowarden.audit.config_events import record_config_change
from chronowarden.config import ConfigError, load_config
from chronowarden.database import Database
from chronowarden.integrations import VaultManager
from chronowarden.logging_config import configure_logging
from chronowarden.scheduler import sync_connected

EXIT_OK = 0
EXIT_NOT_ALL_SYNCED = 1
EXIT_CONFIG_ERROR = 2

# The server keeps its database in the working directory too (app.py)
DB_PATH = Path("chronowarden.db")


async def sync_once(config_path: Optional[str]) -> int:
    """
    Sync every vault once, the way the server's schedule does.

    Returns:
        0 if every vault synced, 1 if any was unreachable or failed, 2 for a configuration error.
    """
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    manager = VaultManager()
    manager.connect_all(config)
    database = Database(DB_PATH)
    database.connect()
    try:
        record_config_change(database, config)
        results = await sync_connected(manager, config, database)
    finally:
        database.close()
        manager.disconnect_all()
    for name, count in sorted(results.items()):
        print(f"{name}: {'not synced (unreachable or failed)' if count is None else f'{count} secret(s) synced'}")
    return EXIT_OK if all(count is not None for count in results.values()) else EXIT_NOT_ALL_SYNCED


def setup_logging() -> None:
    """Log like the server: uvicorn's handlers with timestamps."""
    logging.config.dictConfig(LOGGING_CONFIG)
    configure_logging()


def main(argv: Optional[list[str]] = None) -> int:
    """Parse the command line and run the command."""
    parser = argparse.ArgumentParser(prog="chronowarden", description="Secret rotation monitoring for Vault/OpenBao")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync", help="sync every vault once and exit (for a Kubernetes CronJob)")
    sync.add_argument("--config", help="config file (default: $CHRONOWARDEN_CONFIG, then the usual paths)")
    args = parser.parse_args(argv)
    setup_logging()
    return asyncio.run(sync_once(args.config))


if __name__ == "__main__":
    sys.exit(main())
