# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for log timestamps and the quiet-paths access-log filter (#58)."""

import logging
import re
from collections.abc import Iterator

import pytest
from uvicorn.logging import AccessFormatter, DefaultFormatter

from chronowarden.logging_config import QuietPathsFilter, configure_logging


def _access_record(path: str, status: int) -> logging.LogRecord:
    """Build a record shaped like uvicorn's access-log record."""
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "GET", path, "1.1", status),
        None,
    )


class TestQuietPathsFilter:
    """Successful probes and scrapes are dropped; everything else is kept."""

    @pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/ready", "/api/v1/metrics", "/api/v1/health?x=1"])
    def test_successful_quiet_paths_are_dropped(self, path: str) -> None:
        """2xx responses on probe and metrics paths are filtered out."""
        assert QuietPathsFilter().filter(_access_record(path, 200)) is False

    def test_failing_probe_is_kept(self) -> None:
        """A failing health check stays in the log."""
        assert QuietPathsFilter().filter(_access_record("/api/v1/health", 503)) is True

    def test_other_paths_are_kept(self) -> None:
        """Normal API requests stay in the log."""
        assert QuietPathsFilter().filter(_access_record("/api/v1/secrets/", 200)) is True

    def test_unexpected_record_shape_is_kept(self) -> None:
        """Records that don't look like access records are never dropped."""
        record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 0, "plain message", None, None)
        assert QuietPathsFilter().filter(record) is True


@pytest.fixture()
def uvicorn_loggers() -> Iterator[tuple[logging.Handler, logging.Handler]]:
    """Attach handlers with uvicorn's default formatters, as uvicorn does at startup, and clean up afterwards."""
    default_handler = logging.StreamHandler()
    default_handler.setFormatter(DefaultFormatter(fmt="%(levelprefix)s %(message)s", use_colors=False))
    access_handler = logging.StreamHandler()
    access_handler.setFormatter(AccessFormatter(use_colors=False))
    uvicorn_logger = logging.getLogger("uvicorn")
    access_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addHandler(default_handler)
    access_logger.addHandler(access_handler)
    yield default_handler, access_handler
    uvicorn_logger.removeHandler(default_handler)
    access_logger.removeHandler(access_handler)
    access_logger.filters = [f for f in access_logger.filters if not isinstance(f, QuietPathsFilter)]


class TestConfigureLogging:
    """configure_logging adds timestamps and installs the filter once."""

    def test_lines_get_timestamps(self, uvicorn_loggers: tuple[logging.Handler, logging.Handler]) -> None:
        """Both the default and the access formatter start with a timestamp."""
        default_handler, access_handler = uvicorn_loggers
        configure_logging()

        default_line = default_handler.format(
            logging.LogRecord("uvicorn.error", logging.INFO, __file__, 0, "started", None, None)
        )
        access_line = access_handler.format(_access_record("/api/v1/secrets/", 200))

        timestamp = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} "
        assert re.match(timestamp + r"INFO: +started$", default_line)
        assert re.match(timestamp + r'INFO: +127\.0\.0\.1:5000 - "GET /api/v1/secrets/ HTTP/1\.1" 200', access_line)

    def test_filter_is_installed_once(self, uvicorn_loggers: tuple[logging.Handler, logging.Handler]) -> None:
        """Calling configure_logging twice (e.g. on reload) doesn't stack filters."""
        configure_logging()
        configure_logging()
        filters = [f for f in logging.getLogger("uvicorn.access").filters if isinstance(f, QuietPathsFilter)]
        assert len(filters) == 1
