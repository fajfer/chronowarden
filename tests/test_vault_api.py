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
        vault.address = "http://localhost:8201"
        vault.last_error = "AppRole authentication failed: invalid role_id or secret_id " "(mount point 'chronowarden')"
        manager.get.return_value = vault

        with patch("chronowarden.api.vault._get_vault_manager", return_value=manager):
            response = client.get("/api/v1/vault/dev-vault/health")

        assert response.status_code == 200
        assert response.json()["error"] == vault.last_error
        assert response.json()["address"] == "http://localhost:8201"

    def test_all_vault_health_includes_address(self) -> None:
        """The list health endpoint returns each vault's address (#19)."""
        client = _build_client()
        manager = MagicMock()
        manager.health.return_value = {
            "dev-vault": {"connected": True, "healthy": True, "address": "http://localhost:8201"},
        }

        with patch("chronowarden.api.vault._get_vault_manager", return_value=manager):
            response = client.get("/api/v1/vault/health")

        assert response.status_code == 200
        assert response.json()[0]["address"] == "http://localhost:8201"

    def test_secrets_passthrough_endpoints_are_removed(self) -> None:
        """The raw Vault passthrough endpoints are gone (removed in 0.6.2 for the path-injection flaw)."""
        client = _build_client()
        manager = MagicMock()
        manager.get.return_value = MagicMock()
        with patch("chronowarden.api.vault._get_vault_manager", return_value=manager):
            assert client.get("/api/v1/vault/dev-vault/secrets/list").status_code == 404
            assert client.post("/api/v1/vault/dev-vault/secrets/metadata", json={"path": "x"}).status_code == 404
