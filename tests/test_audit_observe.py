# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for recording changes made in the backend (#24, audit spec task 2)."""

import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Optional

import pytest

from chronowarden.config import AppConfig
from chronowarden.database import Database
from chronowarden.metadata import sync_secret_metadata

IDENTITY = ("prod", "apps", "db")


class FakeVault:
    """One secret's KV v2 metadata, editable between syncs; writes merge like the real integration."""

    def __init__(self) -> None:
        self.metadata: dict[str, Any] = {
            "custom_metadata": {"owner_team": "payments"},
            "delete_version_after": "720h",
            "max_versions": 10,
            "cas_required": False,
            "current_version": 1,
            "updated_time": "2026-10-01T10:00:00.000000Z",
            "versions": {"1": {"created_time": "2026-10-01T10:00:00.000000Z"}},
        }
        self.writes = 0

    def get_secret_metadata(self, path: str, mount_point: Optional[str] = None) -> dict[str, Any]:
        return copy.deepcopy(self.metadata)

    def write_secret_metadata(self, path: str, fields: dict[str, str], mount_point: Optional[str] = None) -> bool:
        self.writes += 1
        self.metadata["custom_metadata"].update(fields)
        return True

    def rotate(self, created: str) -> None:
        version = self.metadata["current_version"] + 1
        self.metadata["current_version"] = version
        self.metadata["updated_time"] = created
        self.metadata["versions"][str(version)] = {"created_time": created}


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "test.db")
    database.connect()
    yield database
    database.close()


def _sync(vault: FakeVault, db: Database) -> None:
    sync_secret_metadata(vault, *IDENTITY, AppConfig(), db)  # type: ignore[arg-type]


def _events(db: Database) -> list[tuple[str, Any, Any]]:
    rows = reversed(db.list_audit_events(limit=1000))
    return [
        (e["event_type"], e["before"] and json.loads(e["before"]), e["after"] and json.loads(e["after"])) for e in rows
    ]


class TestObservedChanges:
    def test_first_sync_is_a_baseline_then_config_applied(self, db: Database) -> None:
        vault = FakeVault()
        _sync(vault, db)
        events = _events(db)
        assert [e[0] for e in events] == ["secret.baseline", "secret.config_applied"]
        assert events[0][2]["custom_metadata"] == {"owner_team": "payments"}
        assert events[0][2]["settings"]["delete_version_after"] == "720h"
        assert events[1][1] == {"chronowarden_severity": None, "chronowarden_ttl": None}
        assert events[1][2]["chronowarden_severity"] == "default"

    def test_unchanged_secret_records_nothing(self, db: Database) -> None:
        """Chronowarden's own write is remembered, so the next sync doesn't report it as a backend change."""
        vault = FakeVault()
        _sync(vault, db)
        _sync(vault, db)
        assert len(_events(db)) == 2 and vault.writes == 1

    def test_other_teams_keys_added_changed_removed(self, db: Database) -> None:
        vault = FakeVault()
        _sync(vault, db)
        vault.metadata["custom_metadata"]["ticket"] = "OPS-1"
        vault.metadata["custom_metadata"]["owner_team"] = "platform"
        _sync(vault, db)
        del vault.metadata["custom_metadata"]["ticket"]
        _sync(vault, db)
        changes = [e for e in _events(db) if e[0] == "secret.metadata"]
        assert changes == [
            (
                "secret.metadata",
                {"owner_team": "payments", "ticket": None},
                {"owner_team": "platform", "ticket": "OPS-1"},
            ),
            ("secret.metadata", {"ticket": "OPS-1"}, {"ticket": None}),
        ]

    def test_settings_change(self, db: Database) -> None:
        vault = FakeVault()
        _sync(vault, db)
        vault.metadata["delete_version_after"] = "0s"
        _sync(vault, db)
        assert _events(db)[-1] == ("secret.settings", {"delete_version_after": "720h"}, {"delete_version_after": "0s"})

    def test_new_version_is_a_rotation(self, db: Database) -> None:
        vault = FakeVault()
        _sync(vault, db)
        vault.rotate("2026-10-11T09:00:00.000000Z")
        _sync(vault, db)
        version = [e for e in _events(db) if e[0] == "secret.version"]
        assert version == [
            (
                "secret.version",
                {"current": 1, "created_time": "2026-10-01T10:00:00.000000Z"},
                {"current": 2, "created_time": "2026-10-11T09:00:00.000000Z"},
            )
        ]
        # The rotation also moves the TTL, which Chronowarden applies and records
        assert _events(db)[-1][0] == "secret.config_applied"

    def test_backend_edit_of_a_chronowarden_key_is_recorded_then_reapplied(self, db: Database) -> None:
        vault = FakeVault()
        _sync(vault, db)
        vault.metadata["custom_metadata"]["chronowarden_severity"] = "critical"
        _sync(vault, db)
        assert [e[0] for e in _events(db)][-2:] == ["secret.metadata", "secret.config_applied"]
        assert vault.metadata["custom_metadata"]["chronowarden_severity"] == "default"

    def test_values_are_never_read(self, db: Database) -> None:
        """The observed state holds metadata only; there is no field a secret value could land in."""
        vault = FakeVault()
        _sync(vault, db)
        state = db.get_observed_state(IDENTITY)
        assert state is not None and set(state) == {"custom_metadata", "settings", "version"}

    def test_purge_forgets_the_observed_state(self, db: Database) -> None:
        vault = FakeVault()
        _sync(vault, db)
        db.reconcile_engine("prod", "apps", set(), "2026-10-11T00:00:00+00:00")
        db.purge_removed()
        assert db.get_observed_state(IDENTITY) is None
