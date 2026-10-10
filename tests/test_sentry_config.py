# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for Sentry initialization defaults (#security review 0.6.2)."""

from unittest.mock import patch

from chronowarden.app import _configure_sentry
from chronowarden.config import AppConfig


def test_sentry_skipped_without_dsn() -> None:
    """Without a DSN, sentry_sdk.init is never called."""
    with patch("chronowarden.app.sentry_sdk.init") as init:
        _configure_sentry(AppConfig())
    init.assert_not_called()


def test_sentry_defaults_are_privacy_safe() -> None:
    """With a DSN, PII is off and sampling is off by default."""
    config = AppConfig(sentry_dsn="https://key@o0.sentry.example.com/0")
    with patch("chronowarden.app.sentry_sdk.init") as init:
        _configure_sentry(config)
    kwargs = init.call_args.kwargs
    assert kwargs["send_default_pii"] is False
    assert kwargs["traces_sample_rate"] == 0.0
    assert kwargs["profile_session_sample_rate"] == 0.0


def test_sentry_sample_rates_are_configurable() -> None:
    """Configured sample rates are passed through to Sentry."""
    config = AppConfig(
        sentry_dsn="https://key@o0.sentry.example.com/0",
        sentry_traces_sample_rate=0.25,
        sentry_profiles_sample_rate=0.1,
    )
    with patch("chronowarden.app.sentry_sdk.init") as init:
        _configure_sentry(config)
    kwargs = init.call_args.kwargs
    assert kwargs["traces_sample_rate"] == 0.25
    assert kwargs["profile_session_sample_rate"] == 0.1
