# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Listing endpoints run a fixed number of queries, not one or two per row (code audit after 0.7.0)."""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.api.owners import router as owners_router
from chronowarden.api.secrets import router as secrets_router
from chronowarden.config import AppConfig
from chronowarden.database import Database, SecretMetadataCache


def _seed(db: Database, count: int) -> None:
    db.create_system("sys", "Billing", "", None, None)
    for i in range(count):
        identity = ("prod", "apps", f"s{i}")
        db.upsert_secret_metadata(SecretMetadataCache(vault_name="prod", engine_id="apps", secret_path=f"s{i}"))
        db.set_observed_state(identity, {"custom_metadata": {}, "settings": {}, "version": {"current": 1}})
        db.add_confirmation(identity, 1, "2026-01-01T00:00:00Z", None)
        db.create_owner(f"o{i}", f"Owner {i}", "x@example.com")
        db.create_notification_route(f"r{i}", f"o{i}", "webhook", "https://hooks.example.com", "t")
        db.set_secret_system(identity, "sys")


def _queries(db: Database, url: str) -> int:
    statements: list[str] = []
    assert db._conn is not None
    db._conn.set_trace_callback(statements.append)
    app = FastAPI()
    app.include_router(secrets_router, prefix="/api/v1")
    app.include_router(owners_router, prefix="/api/v1")
    with (
        patch("chronowarden.api.secrets._get_app_dependencies", return_value=(db, AppConfig(), MagicMock())),
        patch("chronowarden.api.owners._get_db", return_value=db),
    ):
        assert TestClient(app).get(url).status_code == 200
    db._conn.set_trace_callback(None)
    return len(statements)


def test_listing_doesnt_query_per_row(tmp_path) -> None:  # type: ignore[no-untyped-def]
    counts = {}
    for size in (3, 30):
        db = Database(tmp_path / f"{size}.db")
        db.connect()
        _seed(db, size)
        counts[size] = (_queries(db, "/api/v1/secrets/"), _queries(db, "/api/v1/owners/"))
        db.close()
    assert counts[3] == counts[30], counts
