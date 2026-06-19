# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for Vault API error reporting."""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.api.vault import router


def _build_client() -> TestClient:
    """Build a TestClient for the Vault API router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


class TestVaultApiErrors:
    """Tests for surfacing Vault connection failures through API responses."""

    def test_vault_health_includes_last_auth_error(self) -> None:
        """Per-vault health endpoint reports the latest auth error when disconnected."""
        client = _build_client()
        manager = MagicMock()
        vault = MagicMock()
        vault.check_health.return_value = {"healthy": True}
        vault.is_connected.return_value = False
        vault.last_error = (
            "AppRole authentication failed: invalid role_id or secret_id "
            "(mount point 'chronowarden')"
        )
        manager.get.return_value = vault

        with patch("chronowarden.api.vault._get_vault_manager", return_value=manager):
            response = client.get("/api/v1/vault/dev-vault/health")

        assert response.status_code == 200
        assert response.json()["error"] == vault.last_error

    def test_list_secrets_returns_reason_when_vault_not_connected(self) -> None:
        """List endpoint includes connection failure reason in 503 response details."""
        client = _build_client()
        manager = MagicMock()
        vault = MagicMock()
        vault.is_connected.return_value = False
        vault.last_error = (
            "AppRole authentication failed: invalid role_id or secret_id "
            "(mount point 'chronowarden')"
        )
        manager.get.return_value = vault

        with patch("chronowarden.api.vault._get_vault_manager", return_value=manager):
            response = client.get("/api/v1/vault/dev-vault/secrets/list")

        assert response.status_code == 503
        assert "invalid role_id or secret_id" in response.json()["detail"]
