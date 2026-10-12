# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Fixtures shared by the test modules."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from chronowarden.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    """A migrated, empty database in a temporary file; modules that need seed data override it."""
    database = Database(tmp_path / "test.db")
    database.connect()
    yield database
    database.close()
