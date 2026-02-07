# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""SQLite database for Chronowarden internal state management."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

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
        self._conn = sqlite3.connect(str(self._db_path))
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
                entry.last_synced or datetime.utcnow().isoformat(),
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
