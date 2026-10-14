# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Fixtures shared by the test modules."""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from chronowarden.api.cooldown import Cooldown
from chronowarden.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    """A migrated, empty database in a temporary file; modules that need seed data override it."""
    database = Database(tmp_path / "test.db")
    database.connect()
    yield database
    database.close()


@pytest.fixture(autouse=True)
def no_cooldowns(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn off the manual sync and snapshot cooldowns, except in tests marked `cooldowns`."""
    if request.node.get_closest_marker("cooldowns") is None:
        monkeypatch.setattr(Cooldown, "take", lambda self, key, seconds: 0)


class Receiver:
    """A local HTTP server that records requests and answers with the queued status codes (then 200)."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.answers: list[int] = []
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 (http.server's naming)
                body = self.rfile.read(int(self.headers["Content-Length"]))
                receiver.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                code = receiver.answers.pop(0) if receiver.answers else 200
                self.send_response(code)
                if code in (301, 302, 307):
                    self.send_header("Location", "http://127.0.0.1:1/elsewhere")
                self.end_headers()

            def log_message(self, *args: Any) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/hook/secret-token"
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()


@pytest.fixture
def receiver() -> Iterator[Receiver]:
    r = Receiver()
    yield r
    r.server.shutdown()
