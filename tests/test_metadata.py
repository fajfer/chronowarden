# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for date parsing, TTL calculation, and metadata logic."""

from chronowarden.config import AppConfig
from chronowarden.metadata import (
    calculate_ttl,
    format_date,
    is_secret_enabled,
    parse_date,
)


class TestParseDate:
    """Tests for parse_date function."""

    def test_iso_8601_with_nanoseconds(self) -> None:
        dt = parse_date("2026-02-07T14:02:00.859376388Z")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 7

    def test_iso_8601_basic(self) -> None:
        dt = parse_date("2026-02-07T14:02:00Z")
        assert dt is not None
        assert dt.year == 2026

    def test_yyyy_mm_dd(self) -> None:
        dt = parse_date("2026-02-07")
        assert dt is not None
        assert dt.month == 2
        assert dt.day == 7

    def test_yyyy_dd_mm(self) -> None:
        dt = parse_date("2026-07-02", format_hint="YYYY-DD-MM")
        assert dt is not None
        assert dt.month == 2
        assert dt.day == 7

    def test_empty_string(self) -> None:
        assert parse_date("") is None

    def test_none_input(self) -> None:
        assert parse_date(None) is None

    def test_invalid_date(self) -> None:
        assert parse_date("not-a-date") is None

    def test_auto_detect_swapped_date(self) -> None:
        """If YYYY-MM-DD fails, try YYYY-DD-MM."""
        dt = parse_date("2026-31-01")
        assert dt is not None
        assert dt.month == 1
        assert dt.day == 31


class TestFormatDate:
    """Tests for format_date function."""

    def test_yyyy_mm_dd(self) -> None:
        dt = parse_date("2026-02-07T00:00:00Z")
        result = format_date(dt, "YYYY-MM-DD")
        assert result == "2026-02-07"

    def test_yyyy_dd_mm(self) -> None:
        dt = parse_date("2026-02-07T00:00:00Z")
        result = format_date(dt, "YYYY-DD-MM")
        assert result == "2026-07-02"


class TestCalculateTTL:
    """Tests for calculate_ttl function."""

    def test_default_profile(self) -> None:
        config = AppConfig()
        result = calculate_ttl("2026-02-07T14:02:00Z", "default", config)
        assert result == "2027-02-07"

    def test_critical_profile(self) -> None:
        config = AppConfig()
        result = calculate_ttl("2026-02-07T14:02:00Z", "critical", config)
        assert result == "2026-08-06"

    def test_pci_profile(self) -> None:
        config = AppConfig()
        result = calculate_ttl("2026-02-07T14:02:00Z", "pci-dss-4.0", config)
        assert result == "2026-05-08"

    def test_none_severity(self) -> None:
        config = AppConfig()
        result = calculate_ttl("2026-02-07T14:02:00Z", "none", config)
        assert result is None

    def test_invalid_updated_time(self) -> None:
        config = AppConfig()
        result = calculate_ttl("not-a-date", "default", config)
        assert result is None

    def test_vault_style_timestamp(self) -> None:
        config = AppConfig()
        result = calculate_ttl("2026-02-07T14:02:00.859376388Z", "default", config)
        assert result == "2027-02-07"


class TestIsSecretEnabled:
    """Tests for is_secret_enabled function."""

    def test_missing_field_defaults_true(self) -> None:
        assert is_secret_enabled({}) is True

    def test_true_string(self) -> None:
        assert is_secret_enabled({"chronowarden_enabled": "true"}) is True

    def test_false_string(self) -> None:
        assert is_secret_enabled({"chronowarden_enabled": "false"}) is False

    def test_bool_true(self) -> None:
        assert is_secret_enabled({"chronowarden_enabled": True}) is True

    def test_bool_false(self) -> None:
        assert is_secret_enabled({"chronowarden_enabled": False}) is False

    def test_zero_string(self) -> None:
        assert is_secret_enabled({"chronowarden_enabled": "0"}) is False

    def test_no_string(self) -> None:
        assert is_secret_enabled({"chronowarden_enabled": "no"}) is False

    def test_none_value(self) -> None:
        assert is_secret_enabled({"chronowarden_enabled": None}) is True


class TestResolveSeverity:
    """Tests for config.resolve_severity cascade."""

    def test_config_wins_over_metadata(self) -> None:
        """Config always wins, vault metadata is irrelevant."""
        from chronowarden.config import VaultConfig

        config = AppConfig(
            vaults=[
                VaultConfig(
                    name="vault",
                    address="http://localhost:8200",
                    token="test",
                    severity="critical",
                ),
            ],
        )
        result = config.resolve_severity("apps", "vault")
        assert result == "critical"

    def test_falls_through_to_engine(self) -> None:
        from chronowarden.config import EngineConfig

        config = AppConfig(engines=[EngineConfig(id="apps", default_severity="pci-dss-4.0")])
        result = config.resolve_severity("apps", "vault")
        assert result == "pci-dss-4.0"

    def test_falls_through_to_default(self) -> None:
        config = AppConfig()
        result = config.resolve_severity(None, None)
        assert result == "default"

    def test_none_severity_from_secret_config(self) -> None:
        """severity: none is resolved from config, not metadata."""
        from chronowarden.config import EngineConfigNested, SecretConfig, VaultConfig

        config = AppConfig(
            vaults=[
                VaultConfig(
                    name="vault",
                    address="http://localhost:8200",
                    token="test",
                    severity="critical",
                    engines=[
                        EngineConfigNested(
                            name="apps",
                            secrets=[SecretConfig(path="static", severity="none")],
                        ),
                    ],
                ),
            ],
        )
        result = config.resolve_severity("apps", "vault", secret_path="static")
        assert result == "none"

    def test_secret_config_wins_over_metadata(self) -> None:
        """Secret-specific config overrides vault metadata."""
        from chronowarden.config import EngineConfigNested, SecretConfig, VaultConfig

        config = AppConfig(
            vaults=[
                VaultConfig(
                    name="prod",
                    address="http://localhost:8200",
                    token="test",
                    severity="critical",
                    engines=[
                        EngineConfigNested(
                            name="certs",
                            severity="pci-dss-4.0",
                            secrets=[SecretConfig(path="root-ca", severity="none")],
                        ),
                    ],
                ),
            ],
        )
        result = config.resolve_severity("certs", "prod", secret_path="root-ca")
        assert result == "none"

    def test_engine_config_inherited(self) -> None:
        """Secrets inherit engine severity when not specifically overridden."""
        from chronowarden.config import EngineConfigNested, VaultConfig

        config = AppConfig(
            vaults=[
                VaultConfig(
                    name="prod",
                    address="http://localhost:8200",
                    token="test",
                    severity="default",
                    engines=[
                        EngineConfigNested(name="certs", severity="pci-dss-4.0"),
                    ],
                ),
            ],
        )
        result = config.resolve_severity("certs", "prod", secret_path="any-cert")
        assert result == "pci-dss-4.0"

    def test_vault_severity_inherited(self) -> None:
        """Secrets in unlisted engines inherit vault severity."""
        from chronowarden.config import VaultConfig

        config = AppConfig(
            vaults=[
                VaultConfig(
                    name="prod",
                    address="http://localhost:8200",
                    token="test",
                    severity="critical",
                ),
            ],
        )
        result = config.resolve_severity("any-engine", "prod", secret_path="any-secret")
        assert result == "critical"
