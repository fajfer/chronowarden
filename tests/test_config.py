# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for configuration loading, expiry profiles, and cascade logic."""

import pytest

from chronowarden.config import (
    AppConfig,
    EngineConfig,
    ExpiryProfile,
    VaultConfig,
    parse_duration_to_days,
)


class TestParseDurationToDays:
    """Tests for parse_duration_to_days function."""

    def test_days(self) -> None:
        assert parse_duration_to_days("365d") == 365

    def test_days_short(self) -> None:
        assert parse_duration_to_days("90d") == 90

    def test_months(self) -> None:
        assert parse_duration_to_days("6m") == 180

    def test_years(self) -> None:
        assert parse_duration_to_days("1y") == 365

    def test_uppercase(self) -> None:
        assert parse_duration_to_days("365D") == 365

    def test_whitespace(self) -> None:
        assert parse_duration_to_days(" 90d ") == 90

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration_to_days("P365D")

    def test_no_unit(self) -> None:
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration_to_days("365")

    def test_empty(self) -> None:
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration_to_days("")


class TestExpiryProfile:
    """Tests for ExpiryProfile model."""

    def test_valid_profile(self) -> None:
        profile = ExpiryProfile(rotation_period="365d")
        assert profile.rotation_days == 365

    def test_invalid_rotation_period(self) -> None:
        with pytest.raises(ValueError):
            ExpiryProfile(rotation_period="invalid")


class TestAppConfigDefaults:
    """Tests for default AppConfig values."""

    def test_default_profiles(self) -> None:
        config = AppConfig()
        assert "default" in config.expiry_profiles
        assert "critical" in config.expiry_profiles
        assert "pci-dss-4.0" in config.expiry_profiles

    def test_default_rotation_periods(self) -> None:
        config = AppConfig()
        assert config.expiry_profiles["default"].rotation_days == 365
        assert config.expiry_profiles["critical"].rotation_days == 180
        assert config.expiry_profiles["pci-dss-4.0"].rotation_days == 90

    def test_default_date_format(self) -> None:
        config = AppConfig()
        assert config.date_format == "YYYY-MM-DD"

    def test_default_polling_interval(self) -> None:
        config = AppConfig()
        assert config.polling_interval == "6h"


class TestConfigCascade:
    """Tests for the configuration cascade (secret → engine → vault → global)."""

    @pytest.fixture()
    def config(self) -> AppConfig:
        """Create a config with multiple levels for cascade testing."""
        return AppConfig(
            vaults=[
                VaultConfig(
                    name="prod",
                    address="http://localhost:8200",
                    token="test",
                    default_severity="critical",
                ),
                VaultConfig(
                    name="dev",
                    address="http://localhost:8201",
                    token="test",
                    date_format="YYYY-DD-MM",
                ),
            ],
            engines=[
                EngineConfig(id="apps", default_severity="pci-dss-4.0"),
            ],
        )

    def test_secret_severity_wins(self, config: AppConfig) -> None:
        """Secret-level severity overrides all."""
        assert config.resolve_severity("pci-dss-4.0", "apps", "prod") == "pci-dss-4.0"

    def test_engine_cascade(self, config: AppConfig) -> None:
        """Engine severity used when secret has none."""
        assert config.resolve_severity(None, "apps", "prod") == "pci-dss-4.0"

    def test_vault_cascade(self, config: AppConfig) -> None:
        """Vault severity used when secret and engine have none."""
        assert config.resolve_severity(None, "unknown-engine", "prod") == "critical"

    def test_global_cascade(self, config: AppConfig) -> None:
        """Global default used when nothing else matches."""
        assert config.resolve_severity(None, "unknown-engine", "dev") == "default"

    def test_invalid_severity_falls_through(self, config: AppConfig) -> None:
        """Invalid severity falls through cascade."""
        assert config.resolve_severity("invalid-value", None, None) == "default"

    def test_none_severity_disabled(self, config: AppConfig) -> None:
        """Severity 'none' is a valid value."""
        assert config.resolve_severity("none", "apps", "prod") == "none"

    def test_date_format_vault_override(self, config: AppConfig) -> None:
        """Vault-level date format overrides global."""
        assert config.resolve_date_format("dev") == "YYYY-DD-MM"

    def test_date_format_global_default(self, config: AppConfig) -> None:
        """Global date format used when vault has no override."""
        assert config.resolve_date_format("prod") == "YYYY-MM-DD"

    def test_date_format_no_vault(self, config: AppConfig) -> None:
        """Global date format used when no vault specified."""
        assert config.resolve_date_format(None) == "YYYY-MM-DD"


class TestGetRotationDays:
    """Tests for AppConfig.get_rotation_days."""

    def test_default_profile(self) -> None:
        config = AppConfig()
        assert config.get_rotation_days("default") == 365

    def test_critical_profile(self) -> None:
        config = AppConfig()
        assert config.get_rotation_days("critical") == 180

    def test_pci_profile(self) -> None:
        config = AppConfig()
        assert config.get_rotation_days("pci-dss-4.0") == 90

    def test_unknown_profile_uses_default(self) -> None:
        config = AppConfig()
        assert config.get_rotation_days("nonexistent") == 365


class TestVaultConfigExtensions:
    """Tests for VaultConfig new fields."""

    def test_vault_with_date_format(self) -> None:
        vc = VaultConfig(name="test", address="http://localhost", token="t", date_format="YYYY-DD-MM")
        assert vc.date_format == "YYYY-DD-MM"

    def test_vault_with_default_severity(self) -> None:
        vc = VaultConfig(name="test", address="http://localhost", token="t", default_severity="critical")
        assert vc.default_severity == "critical"

    def test_vault_optional_fields_default_none(self) -> None:
        vc = VaultConfig(name="test", address="http://localhost", token="t")
        assert vc.date_format is None
        assert vc.default_severity is None
