# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the manual sync and snapshot cooldowns."""

import pytest
from pydantic import ValidationError

from chronowarden.api.cooldown import Cooldown
from chronowarden.config import AppConfig

pytestmark = pytest.mark.cooldowns


def test_cooldown_per_key_and_reopens_after_the_interval() -> None:
    now = [100.0]
    cooldown = Cooldown(clock=lambda: now[0])
    assert cooldown.take("a", 30) == 0
    now[0] = 110.5
    assert cooldown.take("a", 30) == 20
    assert cooldown.take("b", 30) == 0
    now[0] = 130.0
    assert cooldown.take("a", 30) == 0


def test_zero_turns_the_cooldown_off() -> None:
    cooldown = Cooldown(clock=lambda: 0.0)
    assert [cooldown.take("a", 0) for _ in range(3)] == [0, 0, 0]


def test_config_defaults_and_bounds() -> None:
    config = AppConfig()
    assert (config.manual_sync_cooldown, config.snapshot_min_interval) == (30, 60)
    assert AppConfig(manual_sync_cooldown=0, snapshot_min_interval=0).snapshot_min_interval == 0
    with pytest.raises(ValidationError):
        AppConfig(manual_sync_cooldown=-1)
