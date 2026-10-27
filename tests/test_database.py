# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for SQLite database operations."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from chronowarden.database import Database, SecretMetadataCache


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
        )
        db.upsert_secret_metadata(entry)

        result = db.get_secret_metadata("vault-1", "apps", "secret-1")
        assert result is not None
        assert result.vault_name == "vault-1"
        assert result.ttl == "2027-02-07"
        assert result.severity == "default"

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

    def test_upsert_into_pre_0_6_table_with_enabled_column(self, tmp_path: Path) -> None:
        """A database created before 0.6 (with the old `enabled` column) still accepts upserts (#73)."""
        import sqlite3

        path = tmp_path / "old.db"
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE secret_metadata_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vault_name TEXT NOT NULL, engine_id TEXT NOT NULL, secret_path TEXT NOT NULL,
                updated_time TEXT, ttl TEXT, severity TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_synced TEXT,
                UNIQUE(vault_name, engine_id, secret_path)
            )
            """)
        conn.commit()
        conn.close()
        old_db = Database(db_path=path)
        old_db.connect()
        old_db.upsert_secret_metadata(SecretMetadataCache(vault_name="v", engine_id="e", secret_path="s"))
        assert old_db.get_secret_metadata("v", "e", "s") is not None
        old_db.close()

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


class TestDatabaseConnection:
    """Tests for database connection handling."""

    def test_operations_when_disconnected(self) -> None:
        """Test that read operations on a disconnected DB return safe defaults."""
        db = Database(db_path=Path("/tmp/unused.db"))
        # Should not raise, just log error
        assert db.get_secret_metadata("v", "e", "s") is None
        assert db.list_all_secrets(vault_name="v") == []

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


class TestDatabaseConcurrency:
    """Tests for concurrent database access with a shared connection."""

    def test_concurrent_upsert_and_read(self, tmp_path: Path) -> None:
        """Concurrent upserts and reads should stay consistent without SQLite threading errors."""
        db = Database(db_path=tmp_path / "concurrency.db")
        db.connect()
        try:
            total_entries = 100

            def worker(index: int) -> SecretMetadataCache | None:
                entry = SecretMetadataCache(
                    vault_name="vault-1",
                    engine_id="apps",
                    secret_path=f"secret-{index}",
                    ttl="2027-02-07",
                    severity="default",
                )
                db.upsert_secret_metadata(entry)
                return db.get_secret_metadata("vault-1", "apps", f"secret-{index}")

            with ThreadPoolExecutor(max_workers=12) as executor:
                results = list(executor.map(worker, range(total_entries)))

            assert all(result is not None for result in results)
            assert len(db.list_all_secrets(vault_name="vault-1")) == total_entries
        finally:
            db.close()


class TestAuthStorage:
    """Owners' IdP groups, sessions, pending OIDC logins and API tokens (migration 11, ADR-026)."""

    def test_owner_ids_for_email_and_groups(self, db: Database) -> None:
        db.create_owner("o1", "Alice", "Alice@Example.com")
        db.create_owner("o2", "Payments", "pay@example.com", idp_group="team-payments")
        db.create_owner("o3", "Blank", "")
        assert db.owner_ids_for("alice@example.com", []) == ["o1"]
        assert db.owner_ids_for("alice@example.com", ["team-payments", "other"]) == ["o1", "o2"]
        assert db.owner_ids_for(None, ["team-payments"]) == ["o2"]
        assert db.owner_ids_for(None, []) == [] and db.owner_ids_for("", ["nobody"]) == []

    def test_update_owner_sets_and_clears_idp_group(self, db: Database) -> None:
        db.create_owner("o1", "Alice", "alice@example.com")
        db.update_owner("o1", idp_group="team-a")
        assert db.get_owner("o1")["idp_group"] == "team-a"  # type: ignore[index]
        db.update_owner("o1", name="Alice B")
        assert db.get_owner("o1")["idp_group"] == "team-a"  # type: ignore[index]
        db.update_owner("o1", idp_group="")
        assert db.get_owner("o1")["idp_group"] is None  # type: ignore[index]

    def test_sessions_expire_and_end(self, db: Database) -> None:
        db.create_session("h1", "alice", "a@x", ["g"], "owner", "2026-10-27T10:00:00Z", "2026-10-27T22:00:00Z")
        session = db.get_session("h1", "2026-10-27T12:00:00Z")
        assert session is not None and session["groups"] == ["g"] and session["role"] == "owner"
        assert db.get_session("h1", "2026-10-27T22:00:00Z") is None
        assert db.get_session("other", "2026-10-27T12:00:00Z") is None
        db.delete_session("h1")
        assert db.get_session("h1", "2026-10-27T12:00:00Z") is None

    def test_delete_expired_logins(self, db: Database) -> None:
        db.create_session("old", "a", None, [], "viewer", "2026-10-26T00:00:00Z", "2026-10-26T12:00:00Z")
        db.create_session("new", "b", None, [], "viewer", "2026-10-27T00:00:00Z", "2026-10-28T00:00:00Z")
        db.add_oidc_pending("s-old", "v", "n", "/", "2026-10-27T09:00:00Z")
        db.add_oidc_pending("s-new", "v", "n", "/", "2026-10-27T09:55:00Z")
        db.delete_expired_logins("2026-10-27T10:00:00Z", "2026-10-27T09:50:00Z")
        assert db.get_session("old", "2026-10-26T01:00:00Z") is None
        assert db.get_session("new", "2026-10-27T10:00:00Z") is not None
        assert db.pop_oidc_pending("s-old", "2026-10-27T00:00:00Z") is None
        assert db.pop_oidc_pending("s-new", "2026-10-27T09:50:00Z") is not None

    def test_pending_login_is_used_once_and_only_while_fresh(self, db: Database) -> None:
        db.add_oidc_pending("s1", "verifier", "nonce", "/secrets", "2026-10-27T10:00:00Z")
        pending = db.pop_oidc_pending("s1", "2026-10-27T09:50:00Z")
        assert pending is not None and (pending["code_verifier"], pending["next_path"]) == ("verifier", "/secrets")
        assert db.pop_oidc_pending("s1", "2026-10-27T09:50:00Z") is None
        db.add_oidc_pending("s2", "v", "n", "/", "2026-10-27T09:00:00Z")
        assert db.pop_oidc_pending("s2", "2026-10-27T09:50:00Z") is None
        assert db.pop_oidc_pending("s2", "2026-10-27T00:00:00Z") is None, "a stale state is gone, not kept"

    def test_api_tokens(self, db: Database) -> None:
        db.create_api_token("t1", "ci", "hash1", "viewer", None, "2026-10-27T10:00:00Z", "2027-10-27T10:00:00Z")
        db.create_api_token("t2", "team", "hash2", "owner", "o1", "2026-10-27T11:00:00Z", "2026-11-27T10:00:00Z")
        assert [t["id"] for t in db.list_api_tokens()] == ["t2", "t1"]
        assert "token_hash" not in db.list_api_tokens()[0]
        token = db.get_api_token("hash2", "2026-10-28T00:00:00Z")
        assert token is not None and token["owner_id"] == "o1"
        assert db.get_api_token("hash2", "2026-11-27T10:00:00Z") is None, "expired"
        db.touch_api_token("t1", "2026-10-28T00:00:00Z")
        assert db.get_api_token("hash1", "2026-10-28T00:00:00Z")["last_used_at"] == "2026-10-28T00:00:00Z"  # type: ignore[index]
        revoked = db.revoke_api_token("t1", "2026-10-29T00:00:00Z")
        assert revoked is not None and revoked["revoked_at"] == "2026-10-29T00:00:00Z"
        assert db.get_api_token("hash1", "2026-10-29T01:00:00Z") is None
        assert db.revoke_api_token("t1", "2026-10-30T00:00:00Z") is None, "already revoked"

    def test_api_token_owner_binding_is_enforced(self, db: Database) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            db.create_api_token("t1", "x", "h", "owner", None, "2026-10-27T10:00:00Z", "2027-10-27T10:00:00Z")
        with pytest.raises(sqlite3.IntegrityError):
            db.create_api_token("t2", "y", "h2", "admin", "o1", "2026-10-27T10:00:00Z", "2027-10-27T10:00:00Z")
