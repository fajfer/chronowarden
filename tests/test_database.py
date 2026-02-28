# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for SQLite database operations."""

from collections.abc import Generator
from pathlib import Path

import pytest

from chronowarden.database import Database, EngineConfigRow, SecretMetadataCache


@pytest.fixture()
def db(tmp_path: Path) -> Generator[Database, None, None]:
    """Create a temporary database for testing."""
    database = Database(db_path=tmp_path / "test.db")
    database.connect()
    yield database
    database.close()


class TestSecretMetadataCache:
    """Tests for secret metadata cache operations."""

    def test_upsert_and_get(self, db: Database) -> None:
        entry = SecretMetadataCache(
            vault_name="vault-1",
            engine_id="apps",
            secret_path="secret-1",
            updated_time="2026-02-07T14:02:00Z",
            ttl="2027-02-07",
            severity="default",
            enabled=True,
        )
        db.upsert_secret_metadata(entry)

        result = db.get_secret_metadata("vault-1", "apps", "secret-1")
        assert result is not None
        assert result.vault_name == "vault-1"
        assert result.ttl == "2027-02-07"
        assert result.severity == "default"
        assert result.enabled is True

    def test_upsert_updates_existing(self, db: Database) -> None:
        entry = SecretMetadataCache(
            vault_name="vault-1",
            engine_id="apps",
            secret_path="secret-1",
            updated_time="2026-02-07T14:02:00Z",
            ttl="2027-02-07",
            severity="default",
        )
        db.upsert_secret_metadata(entry)

        entry.ttl = "2027-03-07"
        entry.severity = "critical"
        db.upsert_secret_metadata(entry)

        result = db.get_secret_metadata("vault-1", "apps", "secret-1")
        assert result is not None
        assert result.ttl == "2027-03-07"
        assert result.severity == "critical"

    def test_get_nonexistent(self, db: Database) -> None:
        result = db.get_secret_metadata("vault-1", "apps", "nonexistent")
        assert result is None

    def test_list_secrets_for_vault(self, db: Database) -> None:
        for i in range(3):
            db.upsert_secret_metadata(
                SecretMetadataCache(
                    vault_name="vault-1",
                    engine_id="apps",
                    secret_path=f"secret-{i}",
                    ttl=f"2027-0{i + 1}-07",
                    severity="default",
                )
            )
        db.upsert_secret_metadata(
            SecretMetadataCache(
                vault_name="vault-2",
                engine_id="apps",
                secret_path="other-secret",
                ttl="2027-01-01",
                severity="default",
            )
        )

        results = db.list_secrets_for_vault("vault-1")
        assert len(results) == 3
        secret_paths = {r.secret_path for r in results}
        assert secret_paths == {"secret-0", "secret-1", "secret-2"}
        for result in results:
            assert result.vault_name == "vault-1"
            assert result.engine_id == "apps"

        results_v2 = db.list_secrets_for_vault("vault-2")
        assert len(results_v2) == 1
        assert results_v2[0].secret_path == "other-secret"

    def test_list_secrets_for_vault_empty(self, db: Database) -> None:
        """Test listing secrets for a vault with no entries returns empty list."""
        results = db.list_secrets_for_vault("nonexistent")
        assert results == []

    def test_upsert_preserves_id(self, db: Database) -> None:
        """Test that upsert on the same key preserves the row (no duplicate)."""
        entry = SecretMetadataCache(
            vault_name="vault-1",
            engine_id="apps",
            secret_path="secret-1",
            ttl="2027-02-07",
            severity="default",
        )
        db.upsert_secret_metadata(entry)
        first = db.get_secret_metadata("vault-1", "apps", "secret-1")
        assert first is not None
        first_id = first.id

        entry.ttl = "2028-01-01"
        db.upsert_secret_metadata(entry)
        second = db.get_secret_metadata("vault-1", "apps", "secret-1")
        assert second is not None
        assert second.id == first_id
        assert second.ttl == "2028-01-01"

    def test_upsert_with_null_optional_fields(self, db: Database) -> None:
        """Test upserting a secret with all optional fields as None."""
        entry = SecretMetadataCache(
            vault_name="vault-1",
            engine_id="apps",
            secret_path="minimal",
        )
        db.upsert_secret_metadata(entry)
        result = db.get_secret_metadata("vault-1", "apps", "minimal")
        assert result is not None
        assert result.ttl is None
        assert result.severity is None
        assert result.updated_time is None
        assert result.last_synced is not None  # auto-populated by upsert_secret_metadata
        assert result.enabled is True

    def test_delete(self, db: Database) -> None:
        db.upsert_secret_metadata(
            SecretMetadataCache(
                vault_name="vault-1",
                engine_id="apps",
                secret_path="secret-1",
                ttl="2027-02-07",
                severity="default",
            )
        )

        db.delete_secret_metadata("vault-1", "apps", "secret-1")
        result = db.get_secret_metadata("vault-1", "apps", "secret-1")
        assert result is None

    def test_disabled_secret(self, db: Database) -> None:
        db.upsert_secret_metadata(
            SecretMetadataCache(
                vault_name="vault-1",
                engine_id="apps",
                secret_path="secret-1",
                enabled=False,
            )
        )

        result = db.get_secret_metadata("vault-1", "apps", "secret-1")
        assert result is not None
        assert result.enabled is False


class TestEngineConfig:
    """Tests for engine configuration operations."""

    def test_upsert_and_get(self, db: Database) -> None:
        entry = EngineConfigRow(
            vault_name="vault-1",
            engine_id="apps",
            default_severity="critical",
        )
        db.upsert_engine_config(entry)

        result = db.get_engine_config("vault-1", "apps")
        assert result is not None
        assert result.default_severity == "critical"

    def test_upsert_updates(self, db: Database) -> None:
        entry = EngineConfigRow(
            vault_name="vault-1",
            engine_id="apps",
            default_severity="critical",
        )
        db.upsert_engine_config(entry)

        entry.default_severity = "pci-dss-4.0"
        db.upsert_engine_config(entry)

        result = db.get_engine_config("vault-1", "apps")
        assert result is not None
        assert result.default_severity == "pci-dss-4.0"

    def test_get_nonexistent(self, db: Database) -> None:
        result = db.get_engine_config("vault-1", "nonexistent")
        assert result is None


class TestDatabaseConnection:
    """Tests for database connection handling."""

    def test_operations_when_disconnected(self) -> None:
        """Test that read operations on a disconnected DB return safe defaults."""
        db = Database(db_path=Path("/tmp/unused.db"))
        # Should not raise, just log error
        assert db.get_secret_metadata("v", "e", "s") is None
        assert db.list_secrets_for_vault("v") == []
        assert db.get_engine_config("v", "e") is None

    def test_write_operations_when_disconnected(self) -> None:
        """Test that write operations on a disconnected DB do not raise."""
        db = Database(db_path=Path("/tmp/unused.db"))
        db.upsert_secret_metadata(
            SecretMetadataCache(
                vault_name="v",
                engine_id="e",
                secret_path="s",
            )
        )
        db.delete_secret_metadata("v", "e", "s")
        db.upsert_engine_config(EngineConfigRow(vault_name="v", engine_id="e", default_severity="default"))

    def test_owner_operations_when_disconnected(self) -> None:
        """Test that owner operations on a disconnected DB return safe defaults."""
        db = Database(db_path=Path("/tmp/unused.db"))
        assert db.get_owner("o") is None
        assert db.list_owners() == []
        assert db.list_notification_routes("o") == []
        # Write operations should not raise
        db.create_owner("o", "name", "email")
        db.update_owner("o", name="new")
        db.delete_owner("o")
        db.create_notification_route("r", "o", "email", "a@b.c", "t")
        db.delete_notification_route("r")

    def test_connect_and_close(self, tmp_path: Path) -> None:
        """Test that connect and close cycle works cleanly."""
        db = Database(db_path=tmp_path / "lifecycle.db")
        db.connect()
        db.upsert_secret_metadata(SecretMetadataCache(vault_name="v", engine_id="e", secret_path="s", ttl="2027-01-01"))
        result = db.get_secret_metadata("v", "e", "s")
        assert result is not None
        db.close()
        # After close, operations return safe defaults
        assert db.get_secret_metadata("v", "e", "s") is None

    def test_double_close(self, tmp_path: Path) -> None:
        """Test that closing an already-closed DB does not raise."""
        db = Database(db_path=tmp_path / "double_close.db")
        db.connect()
        db.close()
        db.close()
