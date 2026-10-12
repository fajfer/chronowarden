# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the Prometheus metrics (#71, ADR-022)."""

from datetime import UTC, datetime
from typing import Optional

from prometheus_client import REGISTRY

from chronowarden.config import AppConfig
from chronowarden.database import Database, SecretMetadataCache
from chronowarden.metrics.refresh import refresh_secret_metrics

ENABLED = AppConfig.model_validate({"metrics": {"enabled": True}})


def _sample(name: str, **labels: str) -> Optional[float]:
    return REGISTRY.get_sample_value(name, labels)


def _cache(db: Database, path: str, ttl: Optional[str], updated: Optional[str] = None) -> None:
    db.upsert_secret_metadata(
        SecretMetadataCache(
            vault_name="prod", engine_id="apps", secret_path=path, ttl=ttl, updated_time=updated, severity="default"
        )
    )


class TestSecretMetrics:
    def test_values_after_a_sync(self, db: Database) -> None:
        _cache(db, "db", "2030-01-01", "2026-01-01T00:00:00Z")
        _cache(db, "old", "2020-01-01")
        _cache(db, "none", None)
        refresh_secret_metrics(db, ENABLED)
        labels = {"vault": "prod", "engine": "apps", "secret_path": "db", "severity": "default"}
        assert (
            _sample("chronowarden_secret_expiry_timestamp_seconds", **labels)
            == datetime(2030, 1, 1, tzinfo=UTC).timestamp()
        )
        assert (
            _sample("chronowarden_secret_last_rotation_timestamp_seconds", **labels)
            == datetime(2026, 1, 1, tzinfo=UTC).timestamp()
        )
        assert _sample("chronowarden_secret_confirmation_overdue", **labels) == 0
        no_ttl = {**labels, "secret_path": "none"}
        assert _sample("chronowarden_secret_expiry_timestamp_seconds", **no_ttl) is None, "no TTL, no series"
        assert _sample("chronowarden_secrets", vault="prod", status="ok") == 1
        assert _sample("chronowarden_secrets", vault="prod", status="expired") == 1
        assert _sample("chronowarden_secrets", vault="prod", status="no_ttl") == 1

    def test_removed_secrets_lose_their_series(self, db: Database) -> None:
        _cache(db, "db", "2030-01-01")
        refresh_secret_metrics(db, ENABLED)
        labels = {"vault": "prod", "engine": "apps", "secret_path": "db", "severity": "default"}
        assert _sample("chronowarden_secret_expiry_timestamp_seconds", **labels) is not None
        db.reconcile_engine("prod", "apps", set(), "2026-10-12T00:00:00+00:00")
        refresh_secret_metrics(db, ENABLED)
        assert _sample("chronowarden_secret_expiry_timestamp_seconds", **labels) is None
        assert _sample("chronowarden_secrets", vault="prod", status="ok") is None

    def test_disabled_metrics_skip_the_work(self, db: Database) -> None:
        _cache(db, "fresh", "2031-01-01")
        refresh_secret_metrics(db, AppConfig())
        labels = {"vault": "prod", "engine": "apps", "secret_path": "fresh", "severity": "default"}
        assert _sample("chronowarden_secret_expiry_timestamp_seconds", **labels) is None
