# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Regression: Sentry events must never carry the Vault token (0.7.1)."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import hvac
import pytest
import sentry_sdk
from sentry_sdk.transport import Transport

from chronowarden.app import _configure_sentry
from chronowarden.config import AppConfig
from chronowarden.integrations.vault import VaultIntegration

TOKEN = "hvs.MUST-NOT-LEAVE-THE-PROCESS"


class _Forbidden(BaseHTTPRequestHandler):
    """A Vault that refuses everything with 403, like a policy gap."""

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self.send_response(403)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"errors":["permission denied"]}')

    do_LIST = do_GET  # noqa: N815 - Vault's LIST verb

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture
def vault_url() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), _Forbidden)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict]]:
    """Run _configure_sentry for real, but deliver events to a list instead of the network."""
    captured: list[dict] = []

    class Capture(Transport):
        def capture_envelope(self, envelope: Any) -> None:
            captured.extend(item.payload.json for item in envelope.items if item.payload.json)

    real_init = sentry_sdk.init
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: real_init(transport=Capture, **kw))
    yield captured
    sentry_sdk.init()  # disable again


def test_vault_error_event_has_no_token(vault_url: str, events: list[dict]) -> None:
    _configure_sentry(AppConfig(sentry_dsn="https://key@o0.ingest.example/1"))
    vault = VaultIntegration(address=vault_url, token=TOKEN)
    vault._client = hvac.Client(url=vault_url, token=TOKEN)
    assert vault.list_secrets("", mount_point="apps") == []
    sentry_sdk.flush()
    assert events, "the 403 is reported to Sentry"
    assert TOKEN not in json.dumps(events)
