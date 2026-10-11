# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Ordered SQLite schema migrations, tracked in PRAGMA user_version (ADR-023)."""

import logging
import sqlite3
from typing import Callable, NamedTuple

logger = logging.getLogger("uvicorn.error")


class MigrationError(Exception):
    """A schema migration failed, or the database is newer than this release."""


class Migration(NamedTuple):
    """One schema step: after it runs, PRAGMA user_version equals `version`."""

    version: int
    description: str
    apply: Callable[[sqlite3.Connection], None]


def _baseline(conn: sqlite3.Connection) -> None:
    """Create the 0.6 schema; a 0.6 database already has it and is only marked as version 1."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS secret_metadata_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vault_name TEXT NOT NULL,
            engine_id TEXT NOT NULL,
            secret_path TEXT NOT NULL,
            updated_time TEXT,
            ttl TEXT,
            severity TEXT,
            last_synced TEXT,
            UNIQUE(vault_name, engine_id, secret_path)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS owners (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notification_routes (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
            type TEXT NOT NULL CHECK(type IN ('email', 'webhook')),
            address TEXT NOT NULL,
            message_template TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)


def _webhook_routes_only(conn: sqlite3.Connection) -> None:
    """Delete email routes and allow only webhooks (ADR-022); SQLite can't alter a CHECK, so rebuild the table."""
    deleted = conn.execute("DELETE FROM notification_routes WHERE type = 'email'").rowcount
    if deleted:
        logger.info("Deleted %d email notification route(s): email delivery isn't supported (ADR-022)", deleted)
    conn.execute("""
        CREATE TABLE notification_routes_new (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
            type TEXT NOT NULL CHECK(type = 'webhook'),
            address TEXT NOT NULL,
            message_template TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("INSERT INTO notification_routes_new SELECT * FROM notification_routes")
    conn.execute("DROP TABLE notification_routes")
    conn.execute("ALTER TABLE notification_routes_new RENAME TO notification_routes")


def _systems_and_owners(conn: sqlite3.Connection) -> None:
    """Add systems and the secret assignments, keyed by secret identity rather than cache row (ADR-017, #61)."""
    conn.execute("""
        CREATE TABLE systems (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            cmdb_uri TEXT,
            asset_number TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE system_owners (
            system_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            PRIMARY KEY (system_id, owner_id)
        )
    """)
    conn.execute("""
        CREATE TABLE secret_systems (
            vault_name TEXT NOT NULL,
            engine_id TEXT NOT NULL,
            secret_path TEXT NOT NULL,
            system_id TEXT NOT NULL,
            PRIMARY KEY (vault_name, engine_id, secret_path)
        )
    """)
    conn.execute("""
        CREATE TABLE secret_owners (
            vault_name TEXT NOT NULL,
            engine_id TEXT NOT NULL,
            secret_path TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            PRIMARY KEY (vault_name, engine_id, secret_path, owner_id)
        )
    """)


def _removed_at(conn: sqlite3.Connection) -> None:
    """Remember when sync last missed a secret in its backend, instead of keeping stale rows forever (#86)."""
    conn.execute("ALTER TABLE secret_metadata_cache ADD COLUMN removed_at TEXT")


def _audit_log(conn: sqlite3.Connection) -> None:
    """Add the append-only, hash-chained audit log (ADR-014); triggers refuse any UPDATE or DELETE."""
    conn.execute("""
        CREATE TABLE audit_events (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            actor TEXT,
            event_type TEXT NOT NULL,
            subject TEXT,
            vault_name TEXT,
            engine_id TEXT,
            secret_path TEXT,
            before TEXT,
            after TEXT,
            prev_hash TEXT NOT NULL,
            hash TEXT NOT NULL UNIQUE
        )
    """)
    conn.execute("CREATE INDEX audit_events_secret ON audit_events (vault_name, engine_id, secret_path)")
    for action in ("UPDATE", "DELETE"):
        conn.execute(f"""
            CREATE TRIGGER audit_events_no_{action.lower()} BEFORE {action} ON audit_events
            BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END
        """)
    conn.execute("CREATE TABLE audit_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")


def _observed_state(conn: sqlite3.Connection) -> None:
    """Remember each secret's backend state between syncs, so changes made in the backend can be recorded."""
    conn.execute("""
        CREATE TABLE observed_state (
            vault_name TEXT NOT NULL,
            engine_id TEXT NOT NULL,
            secret_path TEXT NOT NULL,
            state TEXT NOT NULL,
            PRIMARY KEY (vault_name, engine_id, secret_path)
        )
    """)


MIGRATIONS: list[Migration] = [
    Migration(1, "baseline 0.6 schema", _baseline),
    Migration(2, "webhook notification routes only", _webhook_routes_only),
    Migration(3, "systems and secret assignments", _systems_and_owners),
    Migration(4, "removed_at on cached secrets", _removed_at),
    Migration(5, "audit log", _audit_log),
    Migration(6, "observed backend state", _observed_state),
]


def schema_version(conn: sqlite3.Connection) -> int:
    """Return the database's schema version (0 for a database created before migrations)."""
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection, migrations: list[Migration] = MIGRATIONS) -> None:
    """
    Bring the database to the latest schema version, one transaction per step.

    Args:
        conn: Open connection to the Chronowarden database.
        migrations: Steps ordered by version, starting at 1.

    Raises:
        MigrationError: If a step fails (that step is rolled back) or the database is newer than this release.
    """
    latest = migrations[-1].version
    current = schema_version(conn)
    if current > latest:
        raise MigrationError(
            f"Database schema version {current} is newer than this release supports ({latest}); "
            "upgrade Chronowarden or restore a backup of chronowarden.db"
        )
    for migration in migrations:
        if migration.version <= current:
            continue
        logger.info("Migrating database to version %d: %s", migration.version, migration.description)
        try:
            conn.execute("BEGIN")
            migration.apply(conn)
            conn.execute(f"PRAGMA user_version = {int(migration.version)}")
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise MigrationError(f"Database migration to version {migration.version} failed: {exc}") from exc
