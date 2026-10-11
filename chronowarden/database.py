# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""SQLite database for Chronowarden internal state management."""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Optional

from pydantic import BaseModel

from chronowarden.migrations import migrate

logger = logging.getLogger("uvicorn.error")

DEFAULT_DB_PATH = Path("chronowarden.db")

# A secret's real identity (ADR-017): vault name, engine mount, path inside the engine
SecretIdentity = tuple[str, str, str]

_SYSTEM_COLUMNS = ("name", "description", "cmdb_uri", "asset_number")

# Columns of secret_metadata_cache in the order SecretMetadataCache expects them
_CACHE_COLUMNS = "id, vault_name, engine_id, secret_path, updated_time, ttl, severity, last_synced, removed_at"


class SecretMetadataCache(BaseModel):
    """Internal cache entry for a Vault secret's metadata."""

    id: Optional[int] = None
    vault_name: str
    engine_id: str
    secret_path: str
    updated_time: Optional[str] = None
    ttl: Optional[str] = None
    severity: Optional[str] = None
    last_synced: Optional[str] = None
    removed_at: Optional[str] = None


def _row_to_cache(row: sqlite3.Row) -> SecretMetadataCache:
    """Build a cache entry from a row selected with `_CACHE_COLUMNS`."""
    return SecretMetadataCache(**dict(row))


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
        self._conn_lock = RLock()

    def _require_connection(self) -> Optional[sqlite3.Connection]:
        """Return active database connection or log and return None."""
        if self._conn is None:
            logger.error("Database not connected")
            return None
        return self._conn

    def connect(self) -> None:
        """
        Open the database connection and migrate it to the current schema.

        Raises:
            MigrationError: If a migration fails or the database is newer than this release.
        """
        with self._conn_lock:
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            migrate(self._conn)
            logger.info("Database connected at %s", self._db_path)

    def close(self) -> None:
        """Close the database connection."""
        with self._conn_lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
                logger.info("Database connection closed")

    def upsert_secret_metadata(self, entry: SecretMetadataCache) -> None:
        """
        Insert or update a secret metadata cache entry.

        Args:
            entry: The metadata cache entry to upsert.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                """
                INSERT INTO secret_metadata_cache
                    (vault_name, engine_id, secret_path, updated_time, ttl, severity, last_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(vault_name, engine_id, secret_path) DO UPDATE SET
                    updated_time = excluded.updated_time,
                    ttl = excluded.ttl,
                    severity = excluded.severity,
                    last_synced = excluded.last_synced
                """,
                (
                    entry.vault_name,
                    entry.engine_id,
                    entry.secret_path,
                    entry.updated_time,
                    entry.ttl,
                    entry.severity,
                    entry.last_synced or datetime.now(tz=timezone.utc).isoformat(),
                ),
            )
            conn.commit()

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
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            cursor = conn.execute(
                f"""
                SELECT {_CACHE_COLUMNS}
                FROM secret_metadata_cache
                WHERE vault_name = ? AND engine_id = ? AND secret_path = ?
                """,
                (vault_name, engine_id, secret_path),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return _row_to_cache(row)

    def list_secrets_for_vault(self, vault_name: str) -> list[SecretMetadataCache]:
        """
        List all cached secrets for a vault.

        Args:
            vault_name: The vault instance name.

        Returns:
            List of cached metadata entries.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            cursor = conn.execute(
                f"""
                SELECT {_CACHE_COLUMNS}
                FROM secret_metadata_cache
                WHERE vault_name = ?
                """,
                (vault_name,),
            )
            return [_row_to_cache(row) for row in cursor.fetchall()]

    def get_secret_by_id(self, secret_id: int) -> Optional[SecretMetadataCache]:
        """
        Retrieve a cached secret metadata entry by its primary key.

        Args:
            secret_id: The database row ID.

        Returns:
            The cached metadata entry, or None if not found.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            cursor = conn.execute(
                f"""
                SELECT {_CACHE_COLUMNS}
                FROM secret_metadata_cache
                WHERE id = ?
                """,
                (secret_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return _row_to_cache(row)

    def list_all_secrets(
        self,
        vault_name: Optional[str] = None,
        engine_id: Optional[str] = None,
        severity: Optional[str] = None,
        include_removed: bool = False,
    ) -> list[SecretMetadataCache]:
        """
        List all cached secrets with optional filtering.

        Args:
            vault_name: Filter by vault instance name.
            engine_id: Filter by engine mount path.
            severity: Filter by severity profile.
            include_removed: Also return secrets that sync no longer finds in their backend.

        Returns:
            List of cached metadata entries matching the filters.
        """
        query = f"""
            SELECT {_CACHE_COLUMNS}
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
        if not include_removed:
            query += " AND removed_at IS NULL"

        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            cursor = conn.execute(query, params)
            return [_row_to_cache(row) for row in cursor.fetchall()]

    def delete_secret_metadata(self, vault_name: str, engine_id: str, secret_path: str) -> None:
        """
        Delete a cached secret metadata entry.

        Args:
            vault_name: The vault instance name.
            engine_id: The engine mount path.
            secret_path: The secret path within the engine.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                """
                DELETE FROM secret_metadata_cache
                WHERE vault_name = ? AND engine_id = ? AND secret_path = ?
                """,
                (vault_name, engine_id, secret_path),
            )
            conn.commit()

    def reconcile_engine(
        self, vault_name: str, engine_id: str, listed_paths: set[str], now: str
    ) -> tuple[list[str], list[str]]:
        """
        Mark cached secrets of an engine that the backend no longer lists, and unmark those listed again.

        Call it only after a complete listing of the engine; a partial one would mark existing secrets removed.

        Args:
            vault_name: The vault instance name.
            engine_id: The engine mount path.
            listed_paths: Every secret path the backend listed for the engine.
            now: Timestamp stored as `removed_at` (ISO 8601).

        Returns:
            (paths newly marked removed, paths that reappeared).
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return [], []
            rows = conn.execute(
                "SELECT secret_path, removed_at FROM secret_metadata_cache WHERE vault_name = ? AND engine_id = ?",
                (vault_name, engine_id),
            ).fetchall()
            removed = sorted(
                r["secret_path"] for r in rows if r["removed_at"] is None and r["secret_path"] not in listed_paths
            )
            reappeared = sorted(
                r["secret_path"] for r in rows if r["removed_at"] is not None and r["secret_path"] in listed_paths
            )
            where = "WHERE vault_name = ? AND engine_id = ? AND secret_path = ?"
            conn.executemany(
                f"UPDATE secret_metadata_cache SET removed_at = ? {where}",
                [(now, vault_name, engine_id, path) for path in removed],
            )
            conn.executemany(
                f"UPDATE secret_metadata_cache SET removed_at = NULL {where}",
                [(vault_name, engine_id, path) for path in reappeared],
            )
            conn.commit()
            return removed, reappeared

    def purge_removed(
        self, secret_id: Optional[int] = None, vault_name: Optional[str] = None, engine_id: Optional[str] = None
    ) -> list[SecretIdentity]:
        """
        Delete removed secrets from the cache together with their system and owner assignments.

        Only secrets with `removed_at` set are ever purged.

        Args:
            secret_id: Purge only this cache row.
            vault_name: Purge only removed secrets of this vault.
            engine_id: Purge only removed secrets of this engine.

        Returns:
            The identities purged.
        """
        query = "SELECT vault_name, engine_id, secret_path FROM secret_metadata_cache WHERE removed_at IS NOT NULL"
        params: list = []
        for column, value in (("id", secret_id), ("vault_name", vault_name), ("engine_id", engine_id)):
            if value is not None:
                query += f" AND {column} = ?"
                params.append(value)
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            identities = [(r["vault_name"], r["engine_id"], r["secret_path"]) for r in conn.execute(query, params)]
            where = "WHERE vault_name = ? AND engine_id = ? AND secret_path = ?"
            for table in ("secret_metadata_cache", "secret_systems", "secret_owners"):
                conn.executemany(f"DELETE FROM {table} {where}", identities)
            conn.commit()
            return identities

    def create_owner(self, owner_id: str, name: str, email: str) -> None:
        """Create a new owner profile."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT INTO owners (id, name, email) VALUES (?, ?, ?)",
                (owner_id, name, email),
            )
            conn.commit()

    def get_owner(self, owner_id: str) -> Optional[dict]:
        """Get an owner by ID."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            cursor = conn.execute("SELECT id, name, email, created_at FROM owners WHERE id = ?", (owner_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    def list_owners(self) -> list[dict]:
        """List all owners."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            cursor = conn.execute("SELECT id, name, email, created_at FROM owners ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    def update_owner(self, owner_id: str, name: Optional[str] = None, email: Optional[str] = None) -> None:
        """Update an owner profile."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
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
            conn.execute(query, params)
            conn.commit()

    def delete_owner(self, owner_id: str) -> None:
        """Delete an owner, their notification routes, and their assignments to secrets and systems."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute("DELETE FROM notification_routes WHERE owner_id = ?", (owner_id,))
            conn.execute("DELETE FROM secret_owners WHERE owner_id = ?", (owner_id,))
            conn.execute("DELETE FROM system_owners WHERE owner_id = ?", (owner_id,))
            conn.execute("DELETE FROM owners WHERE id = ?", (owner_id,))
            conn.commit()

    def create_notification_route(
        self, route_id: str, owner_id: str, route_type: str, address: str, message_template: str
    ) -> None:
        """Create a notification route for an owner."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT INTO notification_routes "
                "(id, owner_id, type, address, message_template) VALUES (?, ?, ?, ?, ?)",
                (route_id, owner_id, route_type, address, message_template),
            )
            conn.commit()

    def list_notification_routes(self, owner_id: str) -> list[dict]:
        """List notification routes for an owner."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            cursor = conn.execute(
                "SELECT id, owner_id, type, address, message_template, created_at "
                "FROM notification_routes WHERE owner_id = ?",
                (owner_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_notification_route(self, route_id: str) -> None:
        """Delete a notification route."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute("DELETE FROM notification_routes WHERE id = ?", (route_id,))
            conn.commit()

    def create_system(
        self, system_id: str, name: str, description: str, cmdb_uri: Optional[str], asset_number: Optional[str]
    ) -> None:
        """
        Create a system.

        Raises:
            sqlite3.IntegrityError: If a system with the same name exists.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT INTO systems (id, name, description, cmdb_uri, asset_number) VALUES (?, ?, ?, ?, ?)",
                (system_id, name, description, cmdb_uri, asset_number),
            )
            conn.commit()

    def get_system(self, system_id: str) -> Optional[dict]:
        """Get a system by ID, with its `owner_ids`."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute(
                "SELECT id, name, description, cmdb_uri, asset_number, created_at FROM systems WHERE id = ?",
                (system_id,),
            ).fetchone()
            if row is None:
                return None
            system = dict(row)
            system["owner_ids"] = self._system_owner_ids(conn, system_id)
            return system

    def list_systems(self) -> list[dict]:
        """List all systems by name, each with its `owner_ids`."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            rows = conn.execute(
                "SELECT id, name, description, cmdb_uri, asset_number, created_at FROM systems ORDER BY name"
            ).fetchall()
            return [{**dict(row), "owner_ids": self._system_owner_ids(conn, row["id"])} for row in rows]

    @staticmethod
    def _system_owner_ids(conn: sqlite3.Connection, system_id: str) -> list[str]:
        """Return the owner IDs of a system."""
        rows = conn.execute("SELECT owner_id FROM system_owners WHERE system_id = ? ORDER BY owner_id", (system_id,))
        return [row["owner_id"] for row in rows]

    def update_system(self, system_id: str, fields: dict[str, Optional[str]]) -> None:
        """
        Update a system's fields; only names in `_SYSTEM_COLUMNS` are used.

        Raises:
            sqlite3.IntegrityError: If the new name belongs to another system.
        """
        columns = [column for column in _SYSTEM_COLUMNS if column in fields]
        if not columns:
            return
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            query = "UPDATE systems SET " + ", ".join(f"{column} = ?" for column in columns) + " WHERE id = ?"
            conn.execute(query, [fields[column] for column in columns] + [system_id])
            conn.commit()

    def set_system_owners(self, system_id: str, owner_ids: list[str]) -> list[str]:
        """
        Replace a system's owners.

        Returns:
            The previous owner IDs.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            previous = self._system_owner_ids(conn, system_id)
            conn.execute("DELETE FROM system_owners WHERE system_id = ?", (system_id,))
            conn.executemany(
                "INSERT INTO system_owners (system_id, owner_id) VALUES (?, ?)",
                [(system_id, owner_id) for owner_id in sorted(set(owner_ids))],
            )
            conn.commit()
            return previous

    def delete_system(self, system_id: str) -> None:
        """Delete a system and its owner links; callers check that no secret is assigned to it first."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute("DELETE FROM system_owners WHERE system_id = ?", (system_id,))
            conn.execute("DELETE FROM systems WHERE id = ?", (system_id,))
            conn.commit()

    def list_secrets_of_system(self, system_id: str) -> list[SecretIdentity]:
        """Return the identities of the secrets assigned to a system."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            rows = conn.execute(
                "SELECT vault_name, engine_id, secret_path FROM secret_systems WHERE system_id = ? "
                "ORDER BY vault_name, engine_id, secret_path",
                (system_id,),
            )
            return [(row["vault_name"], row["engine_id"], row["secret_path"]) for row in rows]

    def set_secret_system(self, identity: SecretIdentity, system_id: Optional[str]) -> Optional[str]:
        """
        Assign a secret to a system, or unassign it with None.

        Returns:
            The previous system ID, or None.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute(
                "SELECT system_id FROM secret_systems WHERE vault_name = ? AND engine_id = ? AND secret_path = ?",
                identity,
            ).fetchone()
            conn.execute(
                "DELETE FROM secret_systems WHERE vault_name = ? AND engine_id = ? AND secret_path = ?", identity
            )
            if system_id is not None:
                conn.execute(
                    "INSERT INTO secret_systems (vault_name, engine_id, secret_path, system_id) VALUES (?, ?, ?, ?)",
                    (*identity, system_id),
                )
            conn.commit()
            return row["system_id"] if row else None

    def set_secret_owners(self, identity: SecretIdentity, owner_ids: list[str]) -> list[str]:
        """
        Replace the owners assigned to a secret.

        Returns:
            The previous owner IDs.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            where = "WHERE vault_name = ? AND engine_id = ? AND secret_path = ?"
            previous = [
                row["owner_id"]
                for row in conn.execute(f"SELECT owner_id FROM secret_owners {where} ORDER BY owner_id", identity)
            ]
            conn.execute(f"DELETE FROM secret_owners {where}", identity)
            conn.executemany(
                "INSERT INTO secret_owners (vault_name, engine_id, secret_path, owner_id) VALUES (?, ?, ?, ?)",
                [(*identity, owner_id) for owner_id in sorted(set(owner_ids))],
            )
            conn.commit()
            return previous

    def get_assignments(self) -> tuple[dict[SecretIdentity, str], dict[SecretIdentity, list[str]]]:
        """
        Return every secret assignment, keyed by secret identity.

        Returns:
            (system ID per secret, owner IDs per secret).
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return {}, {}
            systems = {
                (row["vault_name"], row["engine_id"], row["secret_path"]): row["system_id"]
                for row in conn.execute("SELECT vault_name, engine_id, secret_path, system_id FROM secret_systems")
            }
            owners: dict[SecretIdentity, list[str]] = {}
            for row in conn.execute(
                "SELECT vault_name, engine_id, secret_path, owner_id FROM secret_owners ORDER BY owner_id"
            ):
                owners.setdefault((row["vault_name"], row["engine_id"], row["secret_path"]), []).append(row["owner_id"])
            return systems, owners
