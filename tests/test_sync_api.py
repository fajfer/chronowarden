# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the sync API: reconnect loop, reconnect-first sync and locking."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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

    def test_sync_starts_reconnect_loop_for_connected_vault(self) -> None:
        """Manual sync should start reconnect loop and still return sync results on success."""
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
            )
        ]

        with (
            patch(
                "chronowarden.api.sync._get_app_dependencies",
                return_value=(manager, MagicMock(), MagicMock()),
            ),
            patch("chronowarden.metadata.detect_changes", return_value=synced),
        ):
            response = client.post("/api/v1/sync/vault/dev-vault")

        assert response.status_code == 200
        assert response.json()["vault"] == "dev-vault"
        assert response.json()["secrets_synced"] == 1
        manager.start_reconnect_loop.assert_called_once_with()


def _disconnected_vault(reconnect_ok: bool, error_kind: str = "offline") -> tuple[MagicMock, MagicMock]:
    """Build a manager with one disconnected vault whose reconnect succeeds or fails."""
    manager = MagicMock()
    vault = MagicMock()
    vault.is_connected.return_value = False
    vault.last_error_kind = None if reconnect_ok else error_kind
    vault.last_error = None if reconnect_ok else f"{error_kind} failure"
    manager.get.return_value = vault
    manager.reconnect.return_value = reconnect_ok
    return manager, vault


class TestSyncReconnectFirst:
    """Sync on a disconnected vault reconnects first, then syncs or reports why not (#59)."""

    def test_reconnect_then_sync(self) -> None:
        """A successful reconnect is followed by a normal sync."""
        manager, _ = _disconnected_vault(reconnect_ok=True)
        synced = [SimpleNamespace(engine_id="apps", secret_path="s", ttl=None, severity="default")]
        with (
            patch("chronowarden.api.sync._get_app_dependencies", return_value=(manager, MagicMock(), MagicMock())),
            patch("chronowarden.metadata.detect_changes", return_value=synced),
        ):
            response = _build_client().post("/api/v1/sync/vault/dev-vault")

        assert response.status_code == 200
        assert response.json()["secrets_synced"] == 1
        manager.reconnect.assert_called_once_with("dev-vault")

    def test_offline_vault_reports_scheduled_retry(self) -> None:
        """An offline vault returns 503 with the reason and a scheduled background retry."""
        manager, _ = _disconnected_vault(reconnect_ok=False, error_kind="offline")
        with patch("chronowarden.api.sync._get_app_dependencies", return_value=(manager, MagicMock(), MagicMock())):
            response = _build_client().post("/api/v1/sync/vault/dev-vault")

        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["reason"] == "offline"
        assert detail["retry_scheduled"] is True
        assert detail["error"] == "offline failure"
        manager.start_reconnect_loop.assert_called_once_with()

    def test_auth_failure_is_not_retried(self) -> None:
        """An authentication failure returns 503 without a scheduled retry."""
        manager, _ = _disconnected_vault(reconnect_ok=False, error_kind="auth")
        with patch("chronowarden.api.sync._get_app_dependencies", return_value=(manager, MagicMock(), MagicMock())):
            response = _build_client().post("/api/v1/sync/vault/dev-vault")

        assert response.status_code == 503
        assert response.json()["detail"]["reason"] == "auth"
        assert response.json()["detail"]["retry_scheduled"] is False

    def test_unknown_vault_returns_404(self) -> None:
        """An unknown vault name returns 404 without a reconnect attempt."""
        manager = MagicMock()
        manager.get.return_value = None
        with patch("chronowarden.api.sync._get_app_dependencies", return_value=(manager, MagicMock(), MagicMock())):
            response = _build_client().post("/api/v1/sync/vault/missing")

        assert response.status_code == 404
        manager.reconnect.assert_not_called()

    def test_sync_holds_the_vault_lock(self) -> None:
        """sync_vault_now runs detect_changes while holding the vault's sync lock."""
        from chronowarden.api.sync import sync_vault_now
        from chronowarden.integrations.manager import VaultManager

        manager = VaultManager()
        manager._vaults["v"] = MagicMock()
        seen_locked: list[bool] = []

        def _detect(*_args: object) -> list:
            seen_locked.append(manager.sync_lock("v").locked())
            return []

        with patch("chronowarden.metadata.detect_changes", side_effect=_detect):
            asyncio.run(sync_vault_now(manager, "v", MagicMock(), MagicMock()))

        assert seen_locked == [True]
        assert not manager.sync_lock("v").locked()
