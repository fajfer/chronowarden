# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for Chronowarden API endpoints."""

import pytest
from fastapi.testclient import TestClient

from chronowarden.app import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Chronowarden API"
        assert "version" in data
        assert data["docs"] == "/docs"

    def test_health_endpoint(self, client: TestClient) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_ready_endpoint(self, client: TestClient) -> None:
        """Test readiness endpoint."""
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_metrics_endpoint(self, client: TestClient) -> None:
        """Test Prometheus metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "chronowarden" in response.text


class TestSecretsAPI:
    """Tests for secrets API endpoints."""

    def test_list_secrets_empty(self, client: TestClient) -> None:
        """Test listing secrets when empty."""
        response = client.get("/api/v1/secrets/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_secret(self, client: TestClient) -> None:
        """Test creating a secret."""
        secret_data = {
            "name": "test-secret",
            "description": "A test secret",
            "owner_id": 1,
            "backend_id": 1,
            "engine_type": "manual",
        }
        response = client.post("/api/v1/secrets/", json=secret_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-secret"
        assert data["description"] == "A test secret"
        assert "id" in data
        assert "created_at" in data

    def test_get_secret(self, client: TestClient) -> None:
        """Test retrieving a secret by ID."""
        # First create a secret
        secret_data = {
            "name": "get-test-secret",
            "owner_id": 1,
            "backend_id": 1,
            "engine_type": "manual",
        }
        create_response = client.post("/api/v1/secrets/", json=secret_data)
        secret_id = create_response.json()["id"]

        # Then get it
        response = client.get(f"/api/v1/secrets/{secret_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "get-test-secret"

    def test_get_secret_not_found(self, client: TestClient) -> None:
        """Test getting non-existent secret."""
        response = client.get("/api/v1/secrets/99999")
        assert response.status_code == 404

    def test_update_secret(self, client: TestClient) -> None:
        """Test updating a secret."""
        # First create a secret
        secret_data = {
            "name": "update-test-secret",
            "owner_id": 1,
            "backend_id": 1,
            "engine_type": "manual",
        }
        create_response = client.post("/api/v1/secrets/", json=secret_data)
        secret_id = create_response.json()["id"]

        # Update it
        update_data = {"name": "updated-secret", "description": "Updated description"}
        response = client.put(f"/api/v1/secrets/{secret_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["name"] == "updated-secret"
        assert response.json()["description"] == "Updated description"

    def test_delete_secret(self, client: TestClient) -> None:
        """Test deleting a secret."""
        # First create a secret
        secret_data = {
            "name": "delete-test-secret",
            "owner_id": 1,
            "backend_id": 1,
            "engine_type": "manual",
        }
        create_response = client.post("/api/v1/secrets/", json=secret_data)
        secret_id = create_response.json()["id"]

        # Delete it
        response = client.delete(f"/api/v1/secrets/{secret_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/v1/secrets/{secret_id}")
        assert get_response.status_code == 404

    def test_list_public_secrets(self, client: TestClient) -> None:
        """Test listing public secrets."""
        # Create a public secret
        secret_data = {
            "name": "public-secret",
            "is_public": True,
            "owner_id": 1,
            "backend_id": 1,
            "engine_type": "manual",
        }
        client.post("/api/v1/secrets/", json=secret_data)

        response = client.get("/api/v1/secrets/public/")
        assert response.status_code == 200
        secrets = response.json()
        assert all(s["is_public"] for s in secrets)


class TestVaultAPI:
    """Tests for Vault API endpoints."""

    def test_vault_health_disconnected(self, client: TestClient) -> None:
        """Test Vault health when not connected."""
        response = client.get("/api/v1/vault/health")
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["healthy"] is False

    def test_vault_disconnect(self, client: TestClient) -> None:
        """Test Vault disconnect endpoint."""
        response = client.post("/api/v1/vault/disconnect")
        assert response.status_code == 200
        assert "Disconnected" in response.json()["message"]

    def test_vault_get_secret_not_connected(self, client: TestClient) -> None:
        """Test getting Vault secret when not connected."""
        response = client.post(
            "/api/v1/vault/secrets/get",
            json={"path": "test/path"},
        )
        assert response.status_code == 503

    def test_vault_list_secrets_not_connected(self, client: TestClient) -> None:
        """Test listing Vault secrets when not connected."""
        response = client.get("/api/v1/vault/secrets/list")
        assert response.status_code == 503
