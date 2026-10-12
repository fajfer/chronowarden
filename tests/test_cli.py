# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for `python -m chronowarden sync` (ADR-013)."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chronowarden.__main__ import main
from chronowarden.config import AppConfig


@pytest.fixture(autouse=True)
def no_logging_setup() -> Iterator[None]:
    """uvicorn's handlers would outlive the test and write to its closed capture stream."""
    with patch("chronowarden.__main__.setup_logging"):
        yield


@pytest.mark.parametrize(
    "results,code,line",
    [
        ({"prod": 3, "dev": 1}, 0, "prod: 3 secret(s) synced"),
        ({"prod": 3, "dev": None}, 1, "dev: not synced (unreachable or failed)"),
    ],
)
def test_sync_exit_codes(
    results: dict, code: int, line: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    with (
        patch("chronowarden.__main__.load_config", return_value=AppConfig()),
        patch("chronowarden.__main__.VaultManager", return_value=MagicMock()) as manager,
        patch("chronowarden.__main__.sync_connected", new=AsyncMock(return_value=results)),
    ):
        assert main(["sync"]) == code
    assert line in capsys.readouterr().out
    manager.return_value.disconnect_all.assert_called_once_with()
    assert (tmp_path / "chronowarden.db").exists(), "the database lives in the working directory, like the server's"


def test_config_error_is_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    assert main(["sync", "--config", str(tmp_path / "missing.yaml")]) == 2
    assert "Configuration error" in capsys.readouterr().err


def test_a_command_is_required() -> None:
    with pytest.raises(SystemExit):
        main([])
