# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for Chronowarden models."""

from datetime import datetime

from chronowarden.models import (
    EngineType,
    HashicorpVaultEngine,
    PermissionLevel,
    RouterType,
    Secret,
    SecretCreate,
    SecretUpdate,
    User,
)


class TestSecretModels:
    """Tests for secret models."""

    def test_secret_create_minimal(self) -> None:
        """Test creating a secret with minimal fields."""
        secret = SecretCreate(
            name="test-secret",
            owner_id=1,
            backend_id=1,
            engine_type=EngineType.MANUAL,
        )
        assert secret.name == "test-secret"
        assert secret.is_public is False
        assert secret.expiry_time_alert == 30
        assert secret.expiry_time_interval == 7

    def test_secret_create_full(self) -> None:
        """Test creating a secret with all fields."""
        secret = SecretCreate(
            name="full-secret",
            description="A test secret",
            is_public=True,
            expiry_date=datetime(2025, 12, 31),
            expiry_time_alert=60,
            expiry_time_interval=14,
            owner_id=1,
            routing_ids=[1, 2],
            backend_id=1,
            engine_type=EngineType.HASHICORP_VAULT,
        )
        assert secret.name == "full-secret"
        assert secret.is_public is True
        assert secret.expiry_time_alert == 60
        assert secret.routing_ids == [1, 2]

    def test_secret_update_partial(self) -> None:
        """Test partial secret update."""
        update = SecretUpdate(name="updated-name")
        assert update.name == "updated-name"
        assert update.description is None
        assert update.is_public is None

    def test_secret_full(self) -> None:
        """Test full secret model."""
        secret = Secret(
            id=1,
            name="test",
            description=None,
            is_public=False,
            created_at=datetime.now(),
            expiry_date=None,
            expiry_time_alert=30,
            expiry_time_interval=7,
            owner_id=1,
            routing_ids=[],
            backend_id=1,
            engine_type=EngineType.MANUAL,
        )
        assert secret.id == 1
        assert secret.engine_type == EngineType.MANUAL


class TestEntityModels:
    """Tests for entity models."""

    def test_user_creation(self) -> None:
        """Test user model creation."""
        user = User(
            id=1,
            name="Test User",
            email="test@example.com",
        )
        assert user.id == 1
        assert user.name == "Test User"
        assert user.permission_level == PermissionLevel.READ_ONLY

    def test_permission_levels(self) -> None:
        """Test permission level values."""
        assert PermissionLevel.READ_ONLY.value == "read-only"
        assert PermissionLevel.READ_WRITE.value == "read-write"
        assert PermissionLevel.ADMIN.value == "admin"


class TestEngineModels:
    """Tests for engine models."""

    def test_hashicorp_vault_engine(self) -> None:
        """Test HashiCorp Vault engine model."""
        engine = HashicorpVaultEngine(
            id=1,
            name="Production Vault",
            owner_id=1,
            vault_address="https://vault.example.com:8200",
            mount_path="secret",
        )
        assert engine.engine_type == EngineType.HASHICORP_VAULT
        assert engine.vault_address == "https://vault.example.com:8200"
        assert engine.mount_path == "secret"

    def test_engine_types(self) -> None:
        """Test engine type values."""
        assert EngineType.MANUAL.value == "manual"
        assert EngineType.HASHICORP_VAULT.value == "hashicorp_vault"
        assert EngineType.AZURE_KEYVAULT.value == "azure_keyvault"
        assert EngineType.X509.value == "x509"


class TestRouterModels:
    """Tests for router models."""

    def test_router_types(self) -> None:
        """Test router type values."""
        assert RouterType.EMAIL.value == "email"
        assert RouterType.WEBHOOK.value == "webhook"
        assert RouterType.SLACK.value == "slack"
