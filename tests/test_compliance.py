# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for compliance evidence: config, periods, gaps, summaries and snapshots (#94)."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from chronowarden.api.compliance import router as compliance_router
from chronowarden.compliance.evidence import build_document
from chronowarden.compliance.periods import ended_periods, period_by_id, period_containing
from chronowarden.config import AppConfig, ComplianceScope
from chronowarden.database import Database, SecretMetadataCache

UTC = timezone.utc
VAULT = {"name": "prod", "address": "http://v:8200", "token_env": "T"}


def _config(**compliance: Any) -> AppConfig:
    return AppConfig.model_validate({"vaults": [VAULT], "compliance": compliance})


class TestConfig:
    def test_cadences_with_scope(self) -> None:
        config = _config(
            reporting={
                "cadences": [
                    {"period": "quarterly", "scope": {"systems": ["Billing"], "privileged_only": True}},
                    {"period": "yearly"},
                ]
            }
        )
        cadences = config.compliance.reporting.cadences
        assert [c.period for c in cadences] == ["quarterly", "yearly"]
        assert cadences[0].scope.privileged_only and cadences[1].scope == ComplianceScope()

    @pytest.mark.parametrize(
        "reporting,message",
        [
            ({"cadences": [{"period": "weekly"}]}, "period"),
            ({"cadences": [{"period": "yearly"}, {"period": "yearly"}]}, "duplicate"),
            ({"cadences": [{"period": "yearly", "scope": {"vaults": ["ghost"]}}]}, "unknown vault"),
            ({"cadences": [{"period": "yearly", "scope": {"owners": ["x"]}}]}, "owners"),
        ],
    )
    def test_invalid(self, reporting: dict, message: str) -> None:
        with pytest.raises(ValidationError, match=message):
            _config(reporting=reporting)

    def test_not_opted_in_by_default(self) -> None:
        assert AppConfig().compliance.reporting.cadences == []


class TestPeriods:
    @pytest.mark.parametrize(
        "cadence,period_id,start,end",
        [
            ("monthly", "2026-12", datetime(2026, 12, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)),
            ("quarterly", "2026-Q4", datetime(2026, 10, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)),
            ("half-yearly", "2026-H2", datetime(2026, 7, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)),
            ("yearly", "2026", datetime(2026, 1, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)),
        ],
    )
    def test_ids_and_bounds(self, cadence: str, period_id: str, start: datetime, end: datetime) -> None:
        period = period_containing(cadence, datetime(2026, 12, 31, 23, 59, tzinfo=UTC))
        assert (period.id, period.start, period.end) == (period_id, start, end)
        assert period_by_id(cadence, period_id) == period

    @pytest.mark.parametrize(
        "cadence,period_id", [("quarterly", "2026-Q5"), ("monthly", "2026-13"), ("yearly", "2026-Q1")]
    )
    def test_bad_ids(self, cadence: str, period_id: str) -> None:
        with pytest.raises(ValueError):
            period_by_id(cadence, period_id)

    def test_ended_periods_since(self) -> None:
        now = datetime(2026, 10, 11, tzinfo=UTC)
        assert [p.id for p in ended_periods("quarterly", datetime(2026, 2, 1, tzinfo=UTC), now)] == [
            "2026-Q1",
            "2026-Q2",
            "2026-Q3",
        ]
        assert ended_periods("yearly", datetime(2026, 2, 1, tzinfo=UTC), now) == []


def test_document_hash_is_deterministic() -> None:
    rows = [
        {"vault": "prod", "engine": "apps", "path": "b", "owners": []},
        {"vault": "prod", "engine": "apps", "path": "a", "owners": []},
    ]
    head = {"events": 3, "head_hash": "f" * 64}
    first = build_document(rows, "2026-10-11T00:00:00.000000Z", ComplianceScope(), head, label="x")
    second = build_document(list(reversed(rows)), "2026-10-11T00:00:00.000000Z", ComplianceScope(), head, label="x")
    assert first == second
    assert hashlib.sha256(first[0].encode("utf-8")).hexdigest() == first[1]


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    """Three secrets: a privileged one assigned to Billing with an owner, a plain one, and one removed last month."""
    database = Database(tmp_path / "test.db")
    database.connect()
    for path, privileged in (("billing/db", True), ("plain", False), ("gone", False)):
        database.upsert_secret_metadata(
            SecretMetadataCache(
                vault_name="prod",
                engine_id="apps",
                secret_path=path,
                ttl="2030-01-01",
                severity="default",
                updated_time="2026-01-01T00:00:00Z",
                privileged=privileged,
            )
        )
    database.create_owner("alice", "Alice", "alice@example.com")
    database.create_system("sys-billing", "Billing", "", "https://cmdb/ci/1", "AS-1")
    database.set_secret_system(("prod", "apps", "billing/db"), "sys-billing")
    database.set_secret_owners(("prod", "apps", "billing/db"), ["alice"])
    last_month = period_containing("monthly", datetime.now(tz=UTC)).start - timedelta(days=10)
    database.reconcile_engine("prod", "apps", {"billing/db", "plain"}, last_month.isoformat())
    yield database
    database.close()


def _client(db: Database, config: AppConfig) -> TestClient:
    app = FastAPI()
    app.include_router(compliance_router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture
def config() -> AppConfig:
    return _config(reporting={"cadences": [{"period": "monthly", "scope": {"systems": []}}]})


@pytest.fixture
def client(db: Database, config: AppConfig) -> Iterator[TestClient]:
    with (
        patch("chronowarden.api.compliance._get_app_dependencies", return_value=(db, config)),
        patch("chronowarden.api.secrets._get_app_dependencies", return_value=(db, config, None)),
    ):
        yield _client(db, config)


def _last_month() -> str:
    return period_containing("monthly", period_containing("monthly", datetime.now(tz=UTC)).start - timedelta(days=1)).id


class TestSummaryAndGaps:
    def test_summary_counts_existing_secrets(self, client: TestClient) -> None:
        data = client.get("/api/v1/compliance/summary").json()
        assert data["by_vault"] == [{"vault": "prod", "total": 2, "privileged": 1}]
        assert {(g["system"], g["total"], g["privileged"]) for g in data["by_system"]} == {
            ("Billing", 1, 1),
            (None, 1, 0),
        }

    def test_gaps(self, client: TestClient) -> None:
        report = client.get("/api/v1/compliance/gaps").json()
        assert report["total"] == 2
        assert {s["full_path"]: s["gaps"] for s in report["secrets"]} == {"prod/apps/plain": ["no_owner", "no_system"]}
        assert report["counts"]["no_owner"] == 1 and report["counts"]["privileged_without_owner"] == 0

    def test_gaps_scope_from_query(self, client: TestClient) -> None:
        report = client.get("/api/v1/compliance/gaps?privileged_only=true").json()
        assert report["total"] == 1 and report["secrets"] == []


class TestSnapshots:
    def test_adhoc_snapshot_and_exports(self, client: TestClient, db: Database) -> None:
        response = client.post(
            "/api/v1/compliance/snapshots", json={"label": "Audit prep", "scope": {"systems": ["Billing"]}}
        )
        assert response.status_code == 201, response.text
        info = response.json()
        assert info["row_count"] == 1
        exported = client.get(f"/api/v1/compliance/snapshots/{info['id']}.json")
        assert hashlib.sha256(exported.content).hexdigest() == info["sha256"] == exported.headers["x-content-sha256"]
        document = json.loads(exported.content)
        row = document["rows"][0]
        assert row["system"] == {"name": "Billing", "cmdb_uri": "https://cmdb/ci/1", "asset_number": "AS-1"}
        assert (
            row["owners"] == ["Alice"] and row["privileged"] is True and row["last_rotation"] == "2026-01-01T00:00:00Z"
        )
        assert document["audit"]["events"] == len(db.iter_audit_events()) - 1, "head before the snapshot's own event"
        csv_text = client.get(f"/api/v1/compliance/snapshots/{info['id']}.csv").text
        assert csv_text.splitlines()[0].startswith("vault,engine,path") and "Alice" in csv_text
        assert db.list_audit_events(event_type="compliance.snapshot")[0]["subject"] == f"snapshot:{info['id']}"

    def test_adhoc_needs_a_label(self, client: TestClient) -> None:
        assert client.post("/api/v1/compliance/snapshots", json={"scope": {}}).status_code == 422

    def test_periodic_close_includes_removed_in_period_and_needs_supersedes_to_redo(self, client: TestClient) -> None:
        period = _last_month()
        first = client.post("/api/v1/compliance/snapshots", json={"cadence": "monthly", "period": period})
        assert first.status_code == 201, first.text
        rows = client.get(f"/api/v1/compliance/snapshots/{first.json()['id']}").json()["document"]["rows"]
        assert {r["path"]: r["removed_at"] is not None for r in rows} == {
            "billing/db": False,
            "plain": False,
            "gone": True,
        }
        again = client.post("/api/v1/compliance/snapshots", json={"cadence": "monthly", "period": period})
        assert again.status_code == 409
        corrected = client.post(
            "/api/v1/compliance/snapshots",
            json={"cadence": "monthly", "period": period, "supersedes": first.json()["id"]},
        )
        assert corrected.status_code == 201 and corrected.json()["supersedes"] == first.json()["id"]

    def test_unfinished_or_unconfigured_period_is_422(self, client: TestClient) -> None:
        current = period_containing("monthly", datetime.now(tz=UTC)).id
        assert (
            client.post("/api/v1/compliance/snapshots", json={"cadence": "monthly", "period": current}).status_code
            == 422
        )
        assert (
            client.post("/api/v1/compliance/snapshots", json={"cadence": "yearly", "period": "2025"}).status_code == 422
        )

    def test_periods_show_what_needs_closing(self, client: TestClient, db: Database) -> None:
        db.append_audit_event("config.baseline", "config", subject="config", after={})  # startup always records this
        later = datetime.now(tz=UTC) + timedelta(days=40)
        with patch("chronowarden.api.compliance._now", return_value=later):
            periods = client.get("/api/v1/compliance/periods").json()
            assert periods and periods[-1]["snapshot_id"] is None
            closed = client.post(
                "/api/v1/compliance/snapshots", json={"cadence": "monthly", "period": periods[-1]["period"]}
            ).json()
            periods = client.get("/api/v1/compliance/periods").json()
        assert periods[-1]["snapshot_id"] == closed["id"]

    def test_snapshots_cant_be_changed_or_deleted(self, client: TestClient, db: Database) -> None:
        client.post("/api/v1/compliance/snapshots", json={"label": "x"})
        assert db._conn is not None
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db._conn.execute("UPDATE compliance_snapshots SET label = 'y'")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db._conn.execute("DELETE FROM compliance_snapshots")

    def test_unknown_snapshot_is_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/compliance/snapshots/9").status_code == 404
        assert client.get("/api/v1/compliance/snapshots/9.json").status_code == 404
