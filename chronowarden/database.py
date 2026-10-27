# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""SQLite database for Chronowarden internal state management."""

import json
import logging
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Optional

from pydantic import BaseModel

from chronowarden.audit.chain import GENESIS_HASH, canonical_json, event_hash
from chronowarden.migrations import migrate
from chronowarden.timestamps import utc_timestamp

logger = logging.getLogger("uvicorn.error")

DEFAULT_DB_PATH = Path("chronowarden.db")

# A secret's real identity (ADR-017): vault name, engine mount, path inside the engine
SecretIdentity = tuple[str, str, str]

_SYSTEM_COLUMNS = ("name", "description", "cmdb_uri", "asset_number")

_AUDIT_COLUMNS = (
    "id, timestamp, source, actor, event_type, subject, vault_name, engine_id, secret_path, before, after, "
    "prev_hash, hash"
)
# Filters of list_audit_events and the column each compares
_AUDIT_FILTERS = {
    "vault_name": "vault_name = ?",
    "engine_id": "engine_id = ?",
    "secret_path": "secret_path = ?",
    "event_type": "event_type = ?",
    "subject": "subject = ?",
    "since": "timestamp >= ?",
    "until": "timestamp <= ?",
    "before_id": "id < ?",
}

# Columns of secret_metadata_cache in the order SecretMetadataCache expects them
_CACHE_COLUMNS = (
    "id, vault_name, engine_id, secret_path, updated_time, ttl, severity, last_synced, removed_at, privileged"
)


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
    privileged: bool = False


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
                    (vault_name, engine_id, secret_path, updated_time, ttl, severity, last_synced, privileged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(vault_name, engine_id, secret_path) DO UPDATE SET
                    updated_time = excluded.updated_time,
                    ttl = excluded.ttl,
                    severity = excluded.severity,
                    last_synced = excluded.last_synced,
                    privileged = excluded.privileged
                """,
                (
                    entry.vault_name,
                    entry.engine_id,
                    entry.secret_path,
                    entry.updated_time,
                    entry.ttl,
                    entry.severity,
                    entry.last_synced or datetime.now(tz=timezone.utc).isoformat(),
                    int(entry.privileged),
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
        privileged: Optional[bool] = None,
    ) -> list[SecretMetadataCache]:
        """
        List all cached secrets with optional filtering.

        Args:
            vault_name: Filter by vault instance name.
            engine_id: Filter by engine mount path.
            severity: Filter by severity profile.
            include_removed: Also return secrets that sync no longer finds in their backend.
            privileged: Filter by the privileged flag.

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
        if privileged is not None:
            query += " AND privileged = ?"
            params.append(int(privileged))

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
            for table in (
                "secret_metadata_cache",
                "secret_systems",
                "secret_owners",
                "observed_state",
                "rotation_confirmations",
            ):
                conn.executemany(f"DELETE FROM {table} {where}", identities)
            conn.commit()
            return identities

    def create_owner(self, owner_id: str, name: str, email: str, idp_group: Optional[str] = None) -> None:
        """Create a new owner profile; members of `idp_group` act for the owner (ADR-026)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT INTO owners (id, name, email, idp_group) VALUES (?, ?, ?, ?)",
                (owner_id, name, email, idp_group),
            )
            conn.commit()

    def get_owner(self, owner_id: str) -> Optional[dict]:
        """Get an owner by ID."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            cursor = conn.execute("SELECT id, name, email, idp_group, created_at FROM owners WHERE id = ?", (owner_id,))
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
            cursor = conn.execute("SELECT id, name, email, idp_group, created_at FROM owners ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    def update_owner(
        self, owner_id: str, name: Optional[str] = None, email: Optional[str] = None, idp_group: Optional[str] = None
    ) -> None:
        """Update an owner profile; None leaves a field as it is, an empty `idp_group` clears it."""
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
            if idp_group is not None:
                updates.append("idp_group = NULLIF(?, '')")
                params.append(idp_group)
            if not updates:
                return
            params.append(owner_id)
            query = "UPDATE owners SET " + ", ".join(updates) + " WHERE id = ?"
            conn.execute(query, params)
            conn.commit()

    def owner_ids_for(self, email: Optional[str], groups: list[str]) -> list[str]:
        """
        The owners a user acts for: their email matches (case-insensitive) or `idp_group` is one of their groups.

        Args:
            email: The user's verified email, if any.
            groups: The user's IdP groups.

        Returns:
            Owner IDs, sorted.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            clauses, params = [], []
            if email:
                clauses.append("lower(email) = lower(?)")
                params.append(email)
            if groups:
                clauses.append(f"idp_group IN ({', '.join('?' for _ in groups)})")
                params.extend(groups)
            if not clauses:
                return []
            rows = conn.execute(f"SELECT id FROM owners WHERE {' OR '.join(clauses)} ORDER BY id", params)
            return [row["id"] for row in rows]

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
                "SELECT id, owner_id, type, address, message_template, created_at, "
                "signing_secret IS NOT NULL AS signed FROM notification_routes WHERE owner_id = ?",
                (owner_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_all_notification_routes(self) -> list[dict]:
        """List every owner's notification routes (one query, for listing owners)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            cursor = conn.execute(
                "SELECT id, owner_id, type, address, message_template, created_at, "
                "signing_secret IS NOT NULL AS signed FROM notification_routes"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_route_target(self, route_id: str) -> Optional[dict]:
        """A route's address and signing secret, for delivery only; listings never include the secret (ADR-025)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute(
                "SELECT id, owner_id, address, signing_secret FROM notification_routes WHERE id = ?", (route_id,)
            ).fetchone()
            return dict(row) if row else None

    def set_route_signing_secret(self, route_id: str, secret: Optional[str]) -> None:
        """Turn signing on (a new secret) or off (None) for a route."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute("UPDATE notification_routes SET signing_secret = ? WHERE id = ?", (secret, route_id))
            conn.commit()

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
            owners: dict[str, list[str]] = {}
            for link in conn.execute("SELECT system_id, owner_id FROM system_owners ORDER BY owner_id"):
                owners.setdefault(link["system_id"], []).append(link["owner_id"])
            return [{**dict(row), "owner_ids": owners.get(row["id"], [])} for row in rows]

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

    def append_audit_event(
        self,
        event_type: str,
        source: str,
        identity: Optional[SecretIdentity] = None,
        subject: Optional[str] = None,
        before: object = None,
        after: object = None,
        actor: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Append an event to the hash-chained audit log (ADR-014).

        The head is read and the event inserted under the connection lock, so concurrent writers can't fork the chain.

        Args:
            event_type: What happened, e.g. `secret.system`.
            source: Where the change came from: `sync`, `ui`, `api` or `config`.
            identity: The secret it concerns, if any.
            subject: What else it concerns, e.g. `system:<id>`, `owner:<id>` or `config`.
            before: The previous value (JSON-serializable), or None.
            after: The new value (JSON-serializable), or None.
            actor: Who made the change; None until authentication (0.9).

        Returns:
            The stored event, or None when the database isn't connected.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            head = conn.execute("SELECT id, hash FROM audit_events ORDER BY id DESC LIMIT 1").fetchone()
            vault_name, engine_id, secret_path = identity if identity is not None else (None, None, None)
            event = {
                "id": head["id"] + 1 if head else 1,
                "timestamp": utc_timestamp(),
                "source": source,
                "actor": actor,
                "event_type": event_type,
                "subject": subject,
                "vault_name": vault_name,
                "engine_id": engine_id,
                "secret_path": secret_path,
                "before": None if before is None else canonical_json(before),
                "after": None if after is None else canonical_json(after),
                "prev_hash": head["hash"] if head else GENESIS_HASH,
            }
            event["hash"] = event_hash(event)
            columns = ", ".join(event)
            conn.execute(
                f"INSERT INTO audit_events ({columns}) VALUES ({', '.join('?' * len(event))})", list(event.values())
            )
            conn.commit()
            return event

    def list_audit_events(self, limit: int = 200, **filters: Optional[object]) -> list[dict]:
        """
        List audit events, newest first.

        Args:
            limit: Maximum number of events.
            **filters: Any of `_AUDIT_FILTERS`; None values are ignored. `before_id` pages backwards.

        Returns:
            Stored events (before/after as stored JSON text).
        """
        clauses = [_AUDIT_FILTERS[name] for name, value in filters.items() if value is not None]
        params = [value for value in filters.values() if value is not None]
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            rows = conn.execute(
                f"SELECT {_AUDIT_COLUMNS} FROM audit_events {where} ORDER BY id DESC LIMIT ?", [*params, limit]
            )
            return [dict(row) for row in rows]

    def iter_audit_events(self, batch: int = 1000) -> Iterator[dict]:
        """
        Yield every audit event in id order, as stored (for verifying and exporting the chain).

        Reads in batches and takes the lock per batch, so a long log neither fills memory nor blocks other requests
        while a slow client downloads the export (0.7.1).
        """
        last_id = 0
        while True:
            with self._conn_lock:
                conn = self._require_connection()
                if conn is None:
                    return
                rows = [
                    dict(row)
                    for row in conn.execute(
                        f"SELECT {_AUDIT_COLUMNS} FROM audit_events WHERE id > ? ORDER BY id LIMIT ?", (last_id, batch)
                    )
                ]
            yield from rows
            if len(rows) < batch:
                return
            last_id = rows[-1]["id"]

    def get_audit_state(self, key: str) -> Optional[str]:
        """Return a value the audit log remembers between runs (e.g. the last config fingerprint)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute("SELECT value FROM audit_state WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def set_audit_state(self, key: str, value: str) -> None:
        """Remember a value between runs."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT INTO audit_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            conn.commit()

    def get_observed_state(self, identity: SecretIdentity) -> Optional[dict]:
        """Return a secret's backend state from the last sync, or None if it was never seen."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute(
                "SELECT state FROM observed_state WHERE vault_name = ? AND engine_id = ? AND secret_path = ?", identity
            ).fetchone()
            return json.loads(row["state"]) if row else None

    def set_observed_state(self, identity: SecretIdentity, state: dict) -> None:
        """Remember a secret's backend state for the next sync."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT INTO observed_state (vault_name, engine_id, secret_path, state) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(vault_name, engine_id, secret_path) DO UPDATE SET state = excluded.state",
                (*identity, canonical_json(state)),
            )
            conn.commit()

    def get_audit_event(self, event_id: int) -> Optional[dict]:
        """Return one stored audit event, or None."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute(f"SELECT {_AUDIT_COLUMNS} FROM audit_events WHERE id = ?", (event_id,)).fetchone()
            return dict(row) if row else None

    def add_confirmation(
        self, identity: SecretIdentity, version: int, applied_at: str, confirmed_by: Optional[str]
    ) -> Optional[dict]:
        """
        Record that a secret's version was applied where it is used (ADR-021).

        Returns:
            The stored confirmation.
        """
        recorded_at = utc_timestamp()
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            cursor = conn.execute(
                "INSERT INTO rotation_confirmations "
                "(vault_name, engine_id, secret_path, version, applied_at, confirmed_by, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (*identity, version, applied_at, confirmed_by, recorded_at),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM rotation_confirmations WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)

    def latest_confirmation(self, identity: SecretIdentity) -> Optional[dict]:
        """Return a secret's newest confirmation that wasn't revoked, or None."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute(
                "SELECT * FROM rotation_confirmations WHERE vault_name = ? AND engine_id = ? AND secret_path = ? "
                "AND revoked_at IS NULL ORDER BY id DESC LIMIT 1",
                identity,
            ).fetchone()
            return dict(row) if row else None

    def revoke_confirmation(self, confirmation_id: int) -> None:
        """Mark a confirmation revoked (the row stays, for the record)."""
        revoked_at = utc_timestamp()
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "UPDATE rotation_confirmations SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (revoked_at, confirmation_id),
            )
            conn.commit()

    def audit_events_after(self, event_id: int, event_types: tuple[str, ...]) -> list[dict]:
        """Audit events of the given types with an id above `event_id`, oldest first (alerting reads them)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            marks = ", ".join("?" for _ in event_types)
            rows = conn.execute(
                f"SELECT * FROM audit_events WHERE id > ? AND event_type IN ({marks}) ORDER BY id",
                (event_id, *event_types),
            )
            return [dict(row) for row in rows]

    def latest_audit_event_id(self) -> int:
        """The id of the newest audit event (0 for an empty log)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return 0
            row = conn.execute("SELECT max(id) FROM audit_events").fetchone()
            return row[0] or 0

    def get_alert_states(self, alertnames: tuple[str, ...]) -> dict[str, dict]:
        """Stored alerts of the given names by fingerprint (ADR-025)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return {}
            marks = ", ".join("?" for _ in alertnames)
            rows = conn.execute(f"SELECT * FROM alert_state WHERE alertname IN ({marks})", alertnames)
            return {row["fingerprint"]: dict(row) for row in rows}

    def list_firing_alerts(self) -> list[dict]:
        """Alerts firing now, oldest first."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            rows = conn.execute("SELECT * FROM alert_state WHERE status = 'firing' ORDER BY starts_at")
            return [dict(row) for row in rows]

    def save_alert_state(self, state: dict) -> None:
        """Insert or replace one alert's state (keys as in the alert_state table)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT OR REPLACE INTO alert_state "
                "(fingerprint, alertname, labels, annotations, owner_ids, status, starts_at, ends_at, last_sent_at) "
                "VALUES (:fingerprint, :alertname, :labels, :annotations, :owner_ids, :status, :starts_at, :ends_at, "
                ":last_sent_at)",
                state,
            )
            conn.commit()

    def enqueue_delivery(
        self,
        created_at: str,
        receiver: str,
        route_id: Optional[str],
        default_route: Optional[str],
        alertname: str,
        fingerprint: Optional[str],
        payload: str,
    ) -> None:
        """Queue one webhook for delivery, due now."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT INTO webhook_deliveries (created_at, receiver, route_id, default_route, alertname, "
                "fingerprint, status, next_attempt_at, payload) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                (created_at, receiver, route_id, default_route, alertname, fingerprint, created_at, payload),
            )
            conn.commit()

    def due_deliveries(self, now: str, limit: int = 50) -> list[dict]:
        """Pending deliveries whose next attempt is due, oldest first."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            rows = conn.execute(
                "SELECT * FROM webhook_deliveries WHERE status = 'pending' AND next_attempt_at <= ? "
                "ORDER BY id LIMIT ?",
                (now, limit),
            )
            return [dict(row) for row in rows]

    def record_delivery_attempt(
        self,
        delivery_id: int,
        status: str,
        attempted_at: str,
        next_attempt_at: Optional[str],
        status_code: Optional[int],
        error: Optional[str],
    ) -> None:
        """Record an attempt: `delivered`, `failed` (given up) or still `pending` with its next attempt."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "UPDATE webhook_deliveries SET status = ?, attempts = attempts + 1, last_attempt_at = ?, "
                "next_attempt_at = ?, last_status_code = ?, last_error = ? WHERE id = ?",
                (status, attempted_at, next_attempt_at, status_code, error, delivery_id),
            )
            conn.commit()

    def list_deliveries(self, limit: int = 100, before_id: Optional[int] = None) -> list[dict]:
        """The delivery log, newest first, without payloads."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            where = "WHERE id < ?" if before_id is not None else ""
            params = (before_id, limit) if before_id is not None else (limit,)
            rows = conn.execute(
                "SELECT id, created_at, receiver, route_id, default_route, alertname, fingerprint, status, attempts, "
                f"next_attempt_at, last_attempt_at, last_status_code, last_error FROM webhook_deliveries {where} "
                "ORDER BY id DESC LIMIT ?",
                params,
            )
            return [dict(row) for row in rows]

    def add_snapshot(
        self,
        created_at: str,
        content: str,
        sha256: str,
        row_count: int,
        label: Optional[str],
        cadence: Optional[str],
        period: Optional[str],
        supersedes: Optional[int],
    ) -> Optional[int]:
        """Store a frozen compliance snapshot; snapshots are never updated or deleted (#94)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            cursor = conn.execute(
                "INSERT INTO compliance_snapshots "
                "(created_at, label, cadence, period, supersedes, row_count, content, sha256) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (created_at, label, cadence, period, supersedes, row_count, content, sha256),
            )
            conn.commit()
            return cursor.lastrowid

    def list_snapshots(self) -> list[dict]:
        """List snapshots, newest first, without their content."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            rows = conn.execute(
                "SELECT id, created_at, label, cadence, period, supersedes, row_count, sha256 "
                "FROM compliance_snapshots ORDER BY id DESC"
            )
            return [dict(row) for row in rows]

    def snapshot_policy_results(self, policy_id: str) -> list[dict]:
        """
        One policy's frozen results across snapshots, oldest first, read inside SQLite (no full documents).

        Returns:
            Snapshot id, created_at, label, period and the policy's result (JSON text) for each snapshot that has it.
        """
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            rows = conn.execute(
                "SELECT s.id, s.created_at, s.label, s.period, p.value AS result "
                "FROM compliance_snapshots s, json_each(s.content, '$.policies') p "
                "WHERE json_extract(p.value, '$.id') = ? ORDER BY s.id",
                (policy_id,),
            )
            return [dict(row) for row in rows]

    def get_snapshot(self, snapshot_id: int) -> Optional[dict]:
        """Return one snapshot with its content."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute("SELECT * FROM compliance_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
            return dict(row) if row else None

    def audit_head(self) -> dict:
        """The newest audit event's id and hash, which snapshots record to anchor the chain."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return {"events": 0, "head_hash": GENESIS_HASH}
            row = conn.execute("SELECT id, hash FROM audit_events ORDER BY id DESC LIMIT 1").fetchone()
            return {"events": row["id"], "head_hash": row["hash"]} if row else {"events": 0, "head_hash": GENESIS_HASH}

    def first_audit_timestamp(self) -> Optional[str]:
        """When the audit log started (reporting periods before it can't be closed)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute("SELECT timestamp FROM audit_events ORDER BY id LIMIT 1").fetchone()
            return row["timestamp"] if row else None

    def latest_confirmations(self) -> dict[SecretIdentity, dict]:
        """Every secret's newest confirmation that wasn't revoked (one query, for listing secrets)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return {}
            rows = conn.execute("SELECT * FROM rotation_confirmations WHERE revoked_at IS NULL ORDER BY id")
            return {(row["vault_name"], row["engine_id"], row["secret_path"]): dict(row) for row in rows}

    def observed_versions(self) -> dict[SecretIdentity, dict]:
        """Every secret's newest observed version (`current`, `created_time`), without the rest of its state."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return {}
            rows = conn.execute(
                "SELECT vault_name, engine_id, secret_path, json_extract(state, '$.version') AS version "
                "FROM observed_state"
            )
            return {
                (row["vault_name"], row["engine_id"], row["secret_path"]): json.loads(row["version"])
                for row in rows
                if row["version"] is not None
            }

    def create_session(
        self,
        id_hash: str,
        name: str,
        email: Optional[str],
        groups: list[str],
        role: str,
        created_at: str,
        expires_at: str,
    ) -> None:
        """Store a login; the cookie holds the session ID, the table only its hash (ADR-026)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT INTO sessions (id_hash, name, email, groups, role, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (id_hash, name, email, json.dumps(groups), role, created_at, expires_at),
            )
            conn.commit()

    def get_session(self, id_hash: str, now: str) -> Optional[dict]:
        """A session that hasn't expired, with `groups` parsed; None otherwise."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute("SELECT * FROM sessions WHERE id_hash = ? AND expires_at > ?", (id_hash, now)).fetchone()
            return {**dict(row), "groups": json.loads(row["groups"])} if row else None

    def delete_session(self, id_hash: str) -> None:
        """End a session (logout)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute("DELETE FROM sessions WHERE id_hash = ?", (id_hash,))
            conn.commit()

    def delete_expired_logins(self, now: str, pending_before: str) -> None:
        """Drop expired sessions and OIDC logins started before `pending_before`."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            conn.execute("DELETE FROM oidc_pending WHERE created_at < ?", (pending_before,))
            conn.commit()

    def add_oidc_pending(self, state: str, code_verifier: str, nonce: str, next_path: str, created_at: str) -> None:
        """Remember a login sent to the IdP until its callback."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT INTO oidc_pending (state, code_verifier, nonce, next_path, created_at) VALUES (?, ?, ?, ?, ?)",
                (state, code_verifier, nonce, next_path, created_at),
            )
            conn.commit()

    def pop_oidc_pending(self, state: str, not_before: str) -> Optional[dict]:
        """Take a pending login out (each state is used once); None if unknown or started before `not_before`."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute("DELETE FROM oidc_pending WHERE state = ? RETURNING *", (state,)).fetchone()
            conn.commit()
            return dict(row) if row and row["created_at"] >= not_before else None

    def create_api_token(
        self,
        token_id: str,
        name: str,
        token_hash: str,
        role: str,
        owner_id: Optional[str],
        created_at: str,
        expires_at: str,
    ) -> None:
        """Store an API token by its hash (ADR-026)."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute(
                "INSERT INTO api_tokens (id, name, token_hash, role, owner_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (token_id, name, token_hash, role, owner_id, created_at, expires_at),
            )
            conn.commit()

    def list_api_tokens(self) -> list[dict]:
        """Every API token, newest first, without hashes."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return []
            rows = conn.execute(
                "SELECT id, name, role, owner_id, created_at, expires_at, last_used_at, revoked_at "
                "FROM api_tokens ORDER BY created_at DESC"
            )
            return [dict(row) for row in rows]

    def get_api_token(self, token_hash: str, now: str) -> Optional[dict]:
        """A token that is neither expired nor revoked, by hash; None otherwise."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute(
                "SELECT id, name, role, owner_id, created_at, expires_at, last_used_at, revoked_at FROM api_tokens "
                "WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?",
                (token_hash, now),
            ).fetchone()
            return dict(row) if row else None

    def touch_api_token(self, token_id: str, used_at: str) -> None:
        """Record when a token was last used."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return
            conn.execute("UPDATE api_tokens SET last_used_at = ? WHERE id = ?", (used_at, token_id))
            conn.commit()

    def revoke_api_token(self, token_id: str, revoked_at: str) -> Optional[dict]:
        """Revoke a token; returns it, or None if unknown or already revoked."""
        with self._conn_lock:
            conn = self._require_connection()
            if conn is None:
                return None
            row = conn.execute(
                "UPDATE api_tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL "
                "RETURNING id, name, role, owner_id, created_at, expires_at, last_used_at, revoked_at",
                (revoked_at, token_id),
            ).fetchone()
            conn.commit()
            return dict(row) if row else None
