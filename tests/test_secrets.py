# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for secrets API and database methods."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from chronowarden.config import AppConfig
from chronowarden.database import Database, SecretMetadataCache


class TestSecretsDatabaseMethods:
    """Test new database methods for secrets."""

    def setup_method(self) -> None:
        """Set up test database."""
        self.db = Database(db_path=Path(":memory:"))
        self.db.connect()

    def teardown_method(self) -> None:
        """Clean up test database."""
        self.db.close()

    def _insert_secret(
        self,
        vault_name: str = "dev-vault",
        engine_id: str = "secret",
        secret_path: str = "my-app/api-key",
        ttl: str = "2026-06-01",
        severity: str = "default",
        enabled: bool = True,
    ) -> None:
        """Helper to insert a secret metadata entry."""
        self.db.upsert_secret_metadata(
            SecretMetadataCache(
                vault_name=vault_name,
                engine_id=engine_id,
                secret_path=secret_path,
                updated_time="2025-01-01T00:00:00Z",
                ttl=ttl,
                severity=severity,
                enabled=enabled,
                last_synced=datetime.now(tz=timezone.utc).isoformat(),
            )
        )

    def test_get_secret_by_id(self) -> None:
        """Test retrieving a secret by its database ID."""
        self._insert_secret()
        result = self.db.get_secret_by_id(1)
        assert result is not None
        assert result.vault_name == "dev-vault"
        assert result.engine_id == "secret"
        assert result.secret_path == "my-app/api-key"

    def test_get_secret_by_id_nonexistent(self) -> None:
        """Test retrieving a nonexistent secret returns None."""
        result = self.db.get_secret_by_id(999)
        assert result is None

    def test_list_all_secrets_no_filter(self) -> None:
        """Test listing all secrets without filters."""
        self._insert_secret(secret_path="key-1")
        self._insert_secret(secret_path="key-2")
        result = self.db.list_all_secrets()
        assert len(result) == 2

    def test_list_all_secrets_filter_vault(self) -> None:
        """Test listing secrets filtered by vault name."""
        self._insert_secret(vault_name="vault-a", secret_path="key-1")
        self._insert_secret(vault_name="vault-b", secret_path="key-2")
        result = self.db.list_all_secrets(vault_name="vault-a")
        assert len(result) == 1
        assert result[0].vault_name == "vault-a"

    def test_list_all_secrets_filter_engine(self) -> None:
        """Test listing secrets filtered by engine ID."""
        self._insert_secret(engine_id="apps", secret_path="key-1")
        self._insert_secret(engine_id="databases", secret_path="key-2")
        result = self.db.list_all_secrets(engine_id="apps")
        assert len(result) == 1
        assert result[0].engine_id == "apps"

    def test_list_all_secrets_filter_severity(self) -> None:
        """Test listing secrets filtered by severity."""
        self._insert_secret(severity="critical", secret_path="key-1")
        self._insert_secret(severity="default", secret_path="key-2")
        result = self.db.list_all_secrets(severity="critical")
        assert len(result) == 1
        assert result[0].severity == "critical"

    def test_list_all_secrets_filter_enabled(self) -> None:
        """Test listing secrets filtered by enabled status."""
        self._insert_secret(enabled=True, secret_path="key-1")
        self._insert_secret(enabled=False, secret_path="key-2")
        result = self.db.list_all_secrets(enabled=True)
        assert len(result) == 1
        assert result[0].enabled is True

    def test_list_all_secrets_multiple_filters(self) -> None:
        """Test listing secrets with multiple filters."""
        self._insert_secret(vault_name="v1", severity="critical", secret_path="key-1")
        self._insert_secret(vault_name="v1", severity="default", secret_path="key-2")
        self._insert_secret(vault_name="v2", severity="critical", secret_path="key-3")
        result = self.db.list_all_secrets(vault_name="v1", severity="critical")
        assert len(result) == 1
        assert result[0].secret_path == "key-1"

    def test_update_secret_metadata_fields_severity(self) -> None:
        """Test updating the severity field."""
        self._insert_secret()
        updated = self.db.update_secret_metadata_fields(1, severity="critical")
        assert updated is True
        entry = self.db.get_secret_by_id(1)
        assert entry is not None
        assert entry.severity == "critical"

    def test_update_secret_metadata_fields_enabled(self) -> None:
        """Test updating the enabled field."""
        self._insert_secret()
        updated = self.db.update_secret_metadata_fields(1, enabled=False)
        assert updated is True
        entry = self.db.get_secret_by_id(1)
        assert entry is not None
        assert entry.enabled is False

    def test_update_secret_metadata_fields_nonexistent(self) -> None:
        """Test updating a nonexistent secret returns False."""
        updated = self.db.update_secret_metadata_fields(999, severity="critical")
        assert updated is False

    def test_update_secret_metadata_fields_no_changes(self) -> None:
        """Test updating with no fields returns False."""
        self._insert_secret()
        updated = self.db.update_secret_metadata_fields(1)
        assert updated is False


class TestSecretsAPI:
    """Test secrets API endpoints using FastAPI TestClient."""

    def setup_method(self) -> None:
        """Set up test database and app dependencies."""
        self.db = Database(db_path=Path(":memory:"))
        self.db.connect()
        self.config = AppConfig()
        self.vault_manager = MagicMock()

    def teardown_method(self) -> None:
        """Clean up test database."""
        self.db.close()

    def _get_client(self) -> TestClient:
        """Build a TestClient with patched app dependencies."""
        from fastapi import FastAPI

        from chronowarden.api.secrets import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            return TestClient(app)

    def _insert_secret(
        self,
        vault_name: str = "dev-vault",
        engine_id: str = "secret",
        secret_path: str = "my-app/api-key",
        ttl: str = "2027-06-01",
        severity: str = "default",
        enabled: bool = True,
    ) -> None:
        """Helper to insert a secret metadata entry."""
        self.db.upsert_secret_metadata(
            SecretMetadataCache(
                vault_name=vault_name,
                engine_id=engine_id,
                secret_path=secret_path,
                updated_time="2025-01-01T00:00:00Z",
                ttl=ttl,
                severity=severity,
                enabled=enabled,
                last_synced=datetime.now(tz=timezone.utc).isoformat(),
            )
        )

    def test_list_secrets_empty(self) -> None:
        """Test listing secrets when cache is empty."""
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.get("/api/v1/secrets/")
            assert response.status_code == 200
            assert response.json() == []

    def test_list_secrets_with_data(self) -> None:
        """Test listing secrets with data in cache."""
        self._insert_secret()
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.get("/api/v1/secrets/")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["vault_name"] == "dev-vault"
            assert data[0]["engine_id"] == "secret"
            assert data[0]["secret_path"] == "my-app/api-key"
            assert data[0]["full_path"] == "dev-vault/secret/my-app/api-key"
            assert data[0]["severity"] == "default"
            assert data[0]["enabled"] is True
            assert data[0]["status"] in ["ok", "warning", "expired", "no_ttl"]
            assert data[0]["rotation_period_days"] == 365

    def test_list_secrets_filter_vault(self) -> None:
        """Test listing secrets filtered by vault name."""
        self._insert_secret(vault_name="vault-a", secret_path="key-1")
        self._insert_secret(vault_name="vault-b", secret_path="key-2")
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.get("/api/v1/secrets/", params={"vault_name": "vault-a"})
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["vault_name"] == "vault-a"

    def test_get_secret_by_id(self) -> None:
        """Test getting a single secret by ID."""
        self._insert_secret()
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.get("/api/v1/secrets/1")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["full_path"] == "dev-vault/secret/my-app/api-key"

    def test_get_secret_not_found(self) -> None:
        """Test getting a nonexistent secret returns 404."""
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.get("/api/v1/secrets/999")
            assert response.status_code == 404

    def test_secret_status_ok(self) -> None:
        """Test that a secret far from expiry has OK status."""
        future_date = (datetime.now(tz=timezone.utc) + timedelta(days=100)).strftime("%Y-%m-%d")
        self._insert_secret(ttl=future_date)
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.get("/api/v1/secrets/1")
            data = response.json()
            assert data["status"] == "ok"
            assert data["days_remaining"] is not None
            assert data["days_remaining"] > 30

    def test_secret_status_warning(self) -> None:
        """Test that a secret close to expiry has WARNING status."""
        warning_date = (datetime.now(tz=timezone.utc) + timedelta(days=15)).strftime("%Y-%m-%d")
        self._insert_secret(ttl=warning_date)
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.get("/api/v1/secrets/1")
            data = response.json()
            assert data["status"] == "warning"

    def test_secret_status_expired(self) -> None:
        """Test that an expired secret has EXPIRED status."""
        past_date = (datetime.now(tz=timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
        self._insert_secret(ttl=past_date)
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.get("/api/v1/secrets/1")
            data = response.json()
            assert data["status"] == "expired"
            assert data["days_remaining"] is not None
            assert data["days_remaining"] < 0

    def test_secret_status_no_ttl(self) -> None:
        """Test that a secret with no TTL has NO_TTL status."""
        self.db.upsert_secret_metadata(
            SecretMetadataCache(
                vault_name="dev-vault",
                engine_id="secret",
                secret_path="my-app/no-ttl",
                updated_time="2025-01-01T00:00:00Z",
                ttl=None,
                severity="default",
                enabled=True,
                last_synced=datetime.now(tz=timezone.utc).isoformat(),
            )
        )
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.get("/api/v1/secrets/1")
            data = response.json()
            assert data["status"] == "no_ttl"
            assert data["days_remaining"] is None

    def test_removed_endpoints_post(self) -> None:
        """Test that POST /secrets/ no longer exists."""
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.post("/api/v1/secrets/", json={})
            assert response.status_code == 405

    def test_removed_endpoints_delete(self) -> None:
        """Test that DELETE /secrets/:id no longer exists."""
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.delete("/api/v1/secrets/1")
            assert response.status_code == 405

    def test_removed_endpoints_public(self) -> None:
        """Test that GET /secrets/public/ no longer exists (returns 422 since 'public' is not a valid int ID)."""
        with patch(
            "chronowarden.api.secrets._get_app_dependencies",
            return_value=(self.db, self.config, self.vault_manager),
        ):
            from fastapi import FastAPI

            from chronowarden.api.secrets import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)
            response = client.get("/api/v1/secrets/public/")
            assert response.status_code == 422
