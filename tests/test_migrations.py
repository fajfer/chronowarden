# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the SQLite schema migrations."""

import sqlite3
from pathlib import Path

import pytest

from chronowarden.database import Database
from chronowarden.migrations import MIGRATIONS, Migration, MigrationError, migrate, schema_version

LATEST = MIGRATIONS[-1].version

# The schema every release up to 0.6.3 created, with user_version left at 0
SCHEMA_0_6 = """
    CREATE TABLE secret_metadata_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT, vault_name TEXT NOT NULL, engine_id TEXT NOT NULL,
        secret_path TEXT NOT NULL, updated_time TEXT, ttl TEXT, severity TEXT, last_synced TEXT,
        UNIQUE(vault_name, engine_id, secret_path)
    );
    CREATE TABLE owners (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')));
    CREATE TABLE notification_routes (
        id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
        type TEXT NOT NULL CHECK(type IN ('email', 'webhook')), address TEXT NOT NULL, message_template TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
"""


@pytest.fixture
def db_0_6(tmp_path: Path) -> Path:
    """A chronowarden.db as 0.6.3 left it: one cached secret, one owner, an email and a webhook route."""
    path = tmp_path / "chronowarden.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_0_6)
    conn.execute(
        "INSERT INTO secret_metadata_cache (vault_name, engine_id, secret_path, ttl, severity) "
        "VALUES ('prod', 'secret', 'app/db', '2027-01-01', 'critical')"
    )
    conn.execute("INSERT INTO owners (id, name, email) VALUES ('o1', 'Payments', 'pay@example.com')")
    conn.execute("INSERT INTO notification_routes (id, owner_id, type, address) VALUES ('r1', 'o1', 'email', 'a@b.c')")
    conn.execute(
        "INSERT INTO notification_routes (id, owner_id, type, address, message_template) "
        "VALUES ('r2', 'o1', 'webhook', 'https://hooks.example.com', 'tpl')"
    )
    conn.commit()
    conn.close()
    return path


class TestMigrate:
    """Tests for migrate()."""

    def test_versions_are_consecutive_from_one(self) -> None:
        assert [m.version for m in MIGRATIONS] == list(range(1, LATEST + 1))

    def test_fresh_database_reaches_latest(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "new.db")
        db.connect()
        try:
            assert db._conn is not None
            assert schema_version(db._conn) == LATEST
            tables = {r[0] for r in db._conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            assert {"secret_metadata_cache", "owners", "notification_routes"} <= tables
        finally:
            db.close()

    def test_upgrade_from_0_6_keeps_data_and_drops_email_routes(self, db_0_6: Path) -> None:
        db = Database(db_0_6)
        db.connect()
        try:
            assert db._conn is not None
            assert schema_version(db._conn) == LATEST
            secret = db.get_secret_metadata("prod", "secret", "app/db")
            assert secret is not None and secret.ttl == "2027-01-01" and secret.severity == "critical"
            assert db.get_owner("o1") is not None
            routes = db.list_notification_routes("o1")
            assert [(r["id"], r["type"], r["message_template"]) for r in routes] == [("r2", "webhook", "tpl")]
            with pytest.raises(sqlite3.IntegrityError):
                db.create_notification_route("r3", "o1", "email", "a@b.c", "x")
        finally:
            db.close()

    def test_second_run_changes_nothing(self, db_0_6: Path) -> None:
        for _ in range(2):
            db = Database(db_0_6)
            db.connect()
            db.close()
        conn = sqlite3.connect(db_0_6)
        assert schema_version(conn) == LATEST
        assert conn.execute("SELECT count(*) FROM notification_routes").fetchone()[0] == 1
        conn.close()

    def test_failed_step_is_rolled_back(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(tmp_path / "x.db")

        def broken(c: sqlite3.Connection) -> None:
            c.execute("CREATE TABLE half_done (id INTEGER)")
            c.execute("INSERT INTO missing_table VALUES (1)")

        with pytest.raises(MigrationError, match="version 2 failed"):
            migrate(conn, [MIGRATIONS[0], Migration(2, "broken", broken)])
        assert schema_version(conn) == 1
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "half_done" not in tables
        conn.close()

    def test_newer_database_is_refused(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(tmp_path / "future.db")
        conn.execute(f"PRAGMA user_version = {LATEST + 1}")
        with pytest.raises(MigrationError, match="newer than this release"):
            migrate(conn)
        conn.close()
