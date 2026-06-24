# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for sync API reconnect loop behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.api.sync import router


def _build_client() -> TestClient:
    """Build a TestClient for the sync API router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


class TestSyncApiReconnectLoop:
    """Tests for restarting reconnect loop on manual sync attempts."""

    def test_sync_restarts_reconnect_loop_for_disconnected_vault(self) -> None:
        """Manual sync should restart reconnect loop even when vault is currently disconnected."""
        client = _build_client()
        manager = MagicMock()
        vault = MagicMock()
        vault.is_connected.return_value = False
        manager.get.return_value = vault

        with patch(
            "chronowarden.api.sync._get_app_dependencies",
            return_value=(manager, MagicMock(), MagicMock()),
        ):
            response = client.post("/api/v1/sync/vault/dev-vault")

        assert response.status_code == 503
        manager.restart_reconnect_loop.assert_called_once_with()

    def test_sync_restarts_reconnect_loop_for_connected_vault(self) -> None:
        """Manual sync should restart reconnect loop and still return sync results on success."""
        client = _build_client()
        manager = MagicMock()
        vault = MagicMock()
        vault.is_connected.return_value = True
        manager.get.return_value = vault
        synced = [
            SimpleNamespace(
                engine_id="secret",
                secret_path="path/to/secret",
                ttl="365d",
                severity="default",
                enabled=True,
            )
        ]

        with patch(
            "chronowarden.api.sync._get_app_dependencies",
            return_value=(manager, MagicMock(), MagicMock()),
        ), patch("chronowarden.metadata.detect_changes", return_value=synced):
            response = client.post("/api/v1/sync/vault/dev-vault")

        assert response.status_code == 200
        assert response.json()["vault"] == "dev-vault"
        assert response.json()["secrets_synced"] == 1
        manager.restart_reconnect_loop.assert_called_once_with()
