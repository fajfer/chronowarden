# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Logging setup: timestamps on uvicorn log lines and no access-log noise from probes and scrapes."""

import logging

from uvicorn.logging import AccessFormatter, DefaultFormatter

QUIET_PATHS = frozenset({"/api/v1/health", "/api/v1/ready", "/api/v1/metrics"})
DEFAULT_FORMAT = "%(asctime)s %(levelprefix)s %(message)s"
ACCESS_FORMAT = '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'


class QuietPathsFilter(logging.Filter):
    """Drop successful access-log records for health probes and metrics scrapes."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Decide whether an access-log record is emitted.

        Args:
            record: A uvicorn access record with args (client, method, path, http_version, status).

        Returns:
            False for 2xx responses on QUIET_PATHS, True otherwise.
        """
        if not isinstance(record.args, tuple) or len(record.args) != 5:
            return True
        path, status = record.args[2], record.args[4]
        if not isinstance(path, str) or not isinstance(status, int):
            return True
        return not (path.split("?", 1)[0] in QUIET_PATHS and 200 <= status < 300)


def _retimestamp_handlers(logger: logging.Logger, formatter_cls: type[DefaultFormatter], fmt: str) -> None:
    """Replace the formatter of each handler on a logger with a timestamped one, keeping its colour setting."""
    for handler in logger.handlers:
        use_colors = getattr(handler.formatter, "use_colors", None)
        handler.setFormatter(formatter_cls(fmt=fmt, use_colors=use_colors))


def configure_logging() -> None:
    """Add timestamps to uvicorn's log handlers and filter quiet paths from the access log (#58)."""
    _retimestamp_handlers(logging.getLogger("uvicorn"), DefaultFormatter, DEFAULT_FORMAT)
    _retimestamp_handlers(logging.getLogger("uvicorn.access"), AccessFormatter, ACCESS_FORMAT)
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, QuietPathsFilter) for f in access_logger.filters):
        access_logger.addFilter(QuietPathsFilter())
