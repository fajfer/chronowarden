# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""SQLite database for Chronowarden internal state management."""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn.error")

DEFAULT_DB_PATH = Path("chronowarden.db")


class SecretMetadataCache(BaseModel):
    """Internal cache entry for a Vault secret's metadata."""

    id: Optional[int] = None
    vault_name: str
    engine_id: str
    secret_path: str
    updated_time: Optional[str] = None
    ttl: Optional[str] = None
    severity: Optional[str] = None
    enabled: bool = True
    last_synced: Optional[str] = None


class EngineConfigRow(BaseModel):
    """Per-engine severity override stored in SQLite."""

    id: Optional[int] = None
    vault_name: str
    engine_id: str = Field(description="Engine mount path (e.g. 'apps', 'databases')")
    default_severity: Optional[str] = None


class Database:
    """SQLite database manager for Chronowarden."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize the database connection.

        Args:
            db_path: Path to the SQLite database file. Defaults to 'chronowarden.db'.
        """
        self._db_path = db_path or DEFAULT_DB_PATH
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Open the database connection and create tables if needed."""
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        logger.info("Database connected at %s", self._db_path)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    def _create_tables(self) -> None:
        """Create required tables if they don't exist."""
        if self._conn is None:
            return

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS secret_metadata_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vault_name TEXT NOT NULL,
                engine_id TEXT NOT NULL,
                secret_path TEXT NOT NULL,
                updated_time TEXT,
                ttl TEXT,
                severity TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_synced TEXT,
                UNIQUE(vault_name, engine_id, secret_path)
            );

            CREATE TABLE IF NOT EXISTS engine_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vault_name TEXT NOT NULL,
                engine_id TEXT NOT NULL,
                default_severity TEXT,
                UNIQUE(vault_name, engine_id)
            );

            CREATE TABLE IF NOT EXISTS owners (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS notification_routes (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
                type TEXT NOT NULL CHECK(type IN ('email', 'webhook')),
                address TEXT NOT NULL,
                message_template TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        self._conn.commit()

    def upsert_secret_metadata(self, entry: SecretMetadataCache) -> None:
        """
        Insert or update a secret metadata cache entry.

        Args:
            entry: The metadata cache entry to upsert.
        """
        if self._conn is None:
            logger.error("Database not connected")
            return

        self._conn.execute(
            """
            INSERT INTO secret_metadata_cache
                (vault_name, engine_id, secret_path, updated_time, ttl, severity, enabled, last_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vault_name, engine_id, secret_path) DO UPDATE SET
                updated_time = excluded.updated_time,
                ttl = excluded.ttl,
                severity = excluded.severity,
                enabled = excluded.enabled,
                last_synced = excluded.last_synced
            """,
            (
                entry.vault_name,
                entry.engine_id,
                entry.secret_path,
                entry.updated_time,
                entry.ttl,
                entry.severity,
                1 if entry.enabled else 0,
                entry.last_synced or datetime.now(tz=timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def get_secret_metadata(
        self,
        vault_name: str,
        engine_id: str,
        secret_path: str,
    ) -> Optional[SecretMetadataCache]:
        """
        Retrieve a cached secret metadata entry.

        Args:
            vault_name: The vault instance name.
            engine_id: The engine mount path.
            secret_path: The secret path within the engine.

        Returns:
            The cached metadata entry, or None if not found.
        """
        if self._conn is None:
            logger.error("Database not connected")
            return None

        cursor = self._conn.execute(
            """
            SELECT id, vault_name, engine_id, secret_path, updated_time, ttl,
                   severity, enabled, last_synced
            FROM secret_metadata_cache
            WHERE vault_name = ? AND engine_id = ? AND secret_path = ?
            """,
            (vault_name, engine_id, secret_path),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return SecretMetadataCache(
            id=row["id"],
            vault_name=row["vault_name"],
            engine_id=row["engine_id"],
            secret_path=row["secret_path"],
            updated_time=row["updated_time"],
            ttl=row["ttl"],
            severity=row["severity"],
            enabled=bool(row["enabled"]),
            last_synced=row["last_synced"],
        )

    def list_secrets_for_vault(self, vault_name: str) -> list[SecretMetadataCache]:
        """
        List all cached secrets for a vault.

        Args:
            vault_name: The vault instance name.

        Returns:
            List of cached metadata entries.
        """
        if self._conn is None:
            logger.error("Database not connected")
            return []

        cursor = self._conn.execute(
            """
            SELECT id, vault_name, engine_id, secret_path, updated_time, ttl,
                   severity, enabled, last_synced
            FROM secret_metadata_cache
            WHERE vault_name = ?
            """,
            (vault_name,),
        )

        return [
            SecretMetadataCache(
                id=row["id"],
                vault_name=row["vault_name"],
                engine_id=row["engine_id"],
                secret_path=row["secret_path"],
                updated_time=row["updated_time"],
                ttl=row["ttl"],
                severity=row["severity"],
                enabled=bool(row["enabled"]),
                last_synced=row["last_synced"],
            )
            for row in cursor.fetchall()
        ]

    def get_secret_by_id(self, secret_id: int) -> Optional[SecretMetadataCache]:
        """
        Retrieve a cached secret metadata entry by its primary key.

        Args:
            secret_id: The database row ID.

        Returns:
            The cached metadata entry, or None if not found.
        """
        if self._conn is None:
            logger.error("Database not connected")
            return None

        cursor = self._conn.execute(
            """
            SELECT id, vault_name, engine_id, secret_path, updated_time, ttl,
                   severity, enabled, last_synced
            FROM secret_metadata_cache
            WHERE id = ?
            """,
            (secret_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return SecretMetadataCache(
            id=row["id"],
            vault_name=row["vault_name"],
            engine_id=row["engine_id"],
            secret_path=row["secret_path"],
            updated_time=row["updated_time"],
            ttl=row["ttl"],
            severity=row["severity"],
            enabled=bool(row["enabled"]),
            last_synced=row["last_synced"],
        )

    def list_all_secrets(
        self,
        vault_name: Optional[str] = None,
        engine_id: Optional[str] = None,
        severity: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> list[SecretMetadataCache]:
        """
        List all cached secrets with optional filtering.

        Args:
            vault_name: Filter by vault instance name.
            engine_id: Filter by engine mount path.
            severity: Filter by severity profile.
            enabled: Filter by monitoring enabled/disabled.

        Returns:
            List of cached metadata entries matching the filters.
        """
        if self._conn is None:
            logger.error("Database not connected")
            return []

        query = """
            SELECT id, vault_name, engine_id, secret_path, updated_time, ttl,
                   severity, enabled, last_synced
            FROM secret_metadata_cache
            WHERE 1=1
        """
        params: list = []

        if vault_name is not None:
            query += " AND vault_name = ?"
            params.append(vault_name)
        if engine_id is not None:
            query += " AND engine_id = ?"
            params.append(engine_id)
        if severity is not None:
            query += " AND severity = ?"
            params.append(severity)
        if enabled is not None:
            query += " AND enabled = ?"
            params.append(1 if enabled else 0)

        cursor = self._conn.execute(query, params)

        return [
            SecretMetadataCache(
                id=row["id"],
                vault_name=row["vault_name"],
                engine_id=row["engine_id"],
                secret_path=row["secret_path"],
                updated_time=row["updated_time"],
                ttl=row["ttl"],
                severity=row["severity"],
                enabled=bool(row["enabled"]),
                last_synced=row["last_synced"],
            )
            for row in cursor.fetchall()
        ]

    def update_secret_metadata_fields(
        self,
        secret_id: int,
        severity: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> bool:
        """
        Update specific Chronowarden metadata fields for a cached secret.

        Args:
            secret_id: The database row ID.
            severity: New severity override.
            enabled: New enabled flag.

        Returns:
            True if a row was updated, False otherwise.
        """
        if self._conn is None:
            logger.error("Database not connected")
            return False

        updates = []
        params: list = []

        if severity is not None:
            updates.append("severity = ?")
            params.append(severity)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)

        if not updates:
            return False

        params.append(secret_id)
        query = "UPDATE secret_metadata_cache SET " + ", ".join(updates) + " WHERE id = ?"
        cursor = self._conn.execute(query, params)
        self._conn.commit()
        return cursor.rowcount > 0

    def upsert_engine_config(self, entry: EngineConfigRow) -> None:
        """
        Insert or update an engine configuration entry.

        Args:
            entry: The engine config entry to upsert.
        """
        if self._conn is None:
            logger.error("Database not connected")
            return

        self._conn.execute(
            """
            INSERT INTO engine_config (vault_name, engine_id, default_severity)
            VALUES (?, ?, ?)
            ON CONFLICT(vault_name, engine_id) DO UPDATE SET
                default_severity = excluded.default_severity
            """,
            (entry.vault_name, entry.engine_id, entry.default_severity),
        )
        self._conn.commit()

    def get_engine_config(self, vault_name: str, engine_id: str) -> Optional[EngineConfigRow]:
        """
        Retrieve an engine configuration entry.

        Args:
            vault_name: The vault instance name.
            engine_id: The engine mount path.

        Returns:
            The engine config entry, or None if not found.
        """
        if self._conn is None:
            logger.error("Database not connected")
            return None

        cursor = self._conn.execute(
            """
            SELECT id, vault_name, engine_id, default_severity
            FROM engine_config
            WHERE vault_name = ? AND engine_id = ?
            """,
            (vault_name, engine_id),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return EngineConfigRow(
            id=row["id"],
            vault_name=row["vault_name"],
            engine_id=row["engine_id"],
            default_severity=row["default_severity"],
        )

    def delete_secret_metadata(self, vault_name: str, engine_id: str, secret_path: str) -> None:
        """
        Delete a cached secret metadata entry.

        Args:
            vault_name: The vault instance name.
            engine_id: The engine mount path.
            secret_path: The secret path within the engine.
        """
        if self._conn is None:
            logger.error("Database not connected")
            return

        self._conn.execute(
            """
            DELETE FROM secret_metadata_cache
            WHERE vault_name = ? AND engine_id = ? AND secret_path = ?
            """,
            (vault_name, engine_id, secret_path),
        )
        self._conn.commit()

    def create_owner(self, owner_id: str, name: str, email: str) -> None:
        """Create a new owner profile."""
        if self._conn is None:
            logger.error("Database not connected")
            return
        self._conn.execute(
            "INSERT INTO owners (id, name, email) VALUES (?, ?, ?)",
            (owner_id, name, email),
        )
        self._conn.commit()

    def get_owner(self, owner_id: str) -> Optional[dict]:
        """Get an owner by ID."""
        if self._conn is None:
            logger.error("Database not connected")
            return None
        cursor = self._conn.execute("SELECT id, name, email, created_at FROM owners WHERE id = ?", (owner_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def list_owners(self) -> list[dict]:
        """List all owners."""
        if self._conn is None:
            logger.error("Database not connected")
            return []
        cursor = self._conn.execute("SELECT id, name, email, created_at FROM owners ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def update_owner(self, owner_id: str, name: Optional[str] = None, email: Optional[str] = None) -> None:
        """Update an owner profile."""
        if self._conn is None:
            logger.error("Database not connected")
            return

        updates = []
        params: list = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if email is not None:
            updates.append("email = ?")
            params.append(email)

        if not updates:
            return
        params.append(owner_id)
        query = "UPDATE owners SET " + ", ".join(updates) + " WHERE id = ?"
        self._conn.execute(query, params)
        self._conn.commit()

    def delete_owner(self, owner_id: str) -> None:
        """Delete an owner and their notification routes."""
        if self._conn is None:
            logger.error("Database not connected")
            return
        self._conn.execute("DELETE FROM notification_routes WHERE owner_id = ?", (owner_id,))
        self._conn.execute("DELETE FROM owners WHERE id = ?", (owner_id,))
        self._conn.commit()

    def create_notification_route(
        self, route_id: str, owner_id: str, route_type: str, address: str, message_template: str
    ) -> None:
        """Create a notification route for an owner."""
        if self._conn is None:
            logger.error("Database not connected")
            return
        self._conn.execute(
            "INSERT INTO notification_routes (id, owner_id, type, address, message_template) VALUES (?, ?, ?, ?, ?)",
            (route_id, owner_id, route_type, address, message_template),
        )
        self._conn.commit()

    def list_notification_routes(self, owner_id: str) -> list[dict]:
        """List notification routes for an owner."""
        if self._conn is None:
            logger.error("Database not connected")
            return []
        cursor = self._conn.execute(
            "SELECT id, owner_id, type, address, message_template, created_at "
            "FROM notification_routes WHERE owner_id = ?",
            (owner_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def delete_notification_route(self, route_id: str) -> None:
        """Delete a notification route."""
        if self._conn is None:
            logger.error("Database not connected")
            return
        self._conn.execute("DELETE FROM notification_routes WHERE id = ?", (route_id,))
        self._conn.commit()
