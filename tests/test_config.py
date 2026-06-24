# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for configuration loading, expiry profiles, and cascade logic."""

import logging
import pathlib

import pytest

from chronowarden.config import (
    AppConfig,
    EngineConfig,
    EngineConfigNested,
    ExpiryProfile,
    SecretConfig,
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

    def test_default_vault_reconnect_interval(self) -> None:
        config = AppConfig()
        assert config.vault_reconnect_interval == 120

    def test_default_vault_reconnect_max_attempts(self) -> None:
        config = AppConfig()
        assert config.vault_reconnect_max_attempts == 5

    def test_custom_vault_reconnect_max_attempts(self) -> None:
        config = AppConfig(vault_reconnect_max_attempts=12)
        assert config.vault_reconnect_max_attempts == 12

    def test_vault_reconnect_max_attempts_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            AppConfig(vault_reconnect_max_attempts=0)

    def test_default_sentry_dsn(self) -> None:
        config = AppConfig()
        assert config.sentry_dsn is None

    def test_custom_sentry_dsn(self) -> None:
        config = AppConfig(sentry_dsn="https://key@o0.sentry.example.com/0")
        assert config.sentry_dsn == "https://key@o0.sentry.example.com/0"


class TestConfigCascade:
    """Tests for the configuration cascade (secret config → engine → vault → global)."""

    @pytest.fixture()
    def config(self) -> AppConfig:
        """Create a config with multiple levels for cascade testing."""
        return AppConfig(
            vaults=[
                VaultConfig(
                    name="prod",
                    address="http://localhost:8200",
                    token="test",
                    severity="critical",
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

    def test_engine_cascade(self, config: AppConfig) -> None:
        """Legacy engine severity used for matching engine."""
        assert config.resolve_severity("apps", "prod") == "pci-dss-4.0"

    def test_engine_cascade_no_secret(self, config: AppConfig) -> None:
        """Engine severity used when no secret path provided."""
        assert config.resolve_severity("apps", "prod") == "pci-dss-4.0"

    def test_vault_cascade(self, config: AppConfig) -> None:
        """Vault severity used when engine has no override."""
        assert config.resolve_severity("unknown-engine", "prod") == "critical"

    def test_global_cascade(self, config: AppConfig) -> None:
        """Global default used when nothing else matches."""
        assert config.resolve_severity("unknown-engine", "dev") == "default"

    def test_global_cascade_no_vault(self, config: AppConfig) -> None:
        """Global default used when vault is unknown."""
        assert config.resolve_severity(None, None) == "default"

    def test_date_format_vault_override(self, config: AppConfig) -> None:
        """Vault-level date format overrides global."""
        assert config.resolve_date_format("dev") == "YYYY-DD-MM"

    def test_date_format_global_default(self, config: AppConfig) -> None:
        """Global date format used when vault has no override."""
        assert config.resolve_date_format("prod") == "YYYY-MM-DD"

    def test_date_format_no_vault(self, config: AppConfig) -> None:
        """Global date format used when no vault specified."""
        assert config.resolve_date_format(None) == "YYYY-MM-DD"


class TestNestedConfigCascade:
    """Tests for the new nested configuration cascade."""

    @pytest.fixture()
    def config(self) -> AppConfig:
        """Create a config with nested engines and secret overrides."""
        return AppConfig(
            vaults=[
                VaultConfig(
                    name="prod",
                    address="http://localhost:8200",
                    token="test",
                    severity="critical",
                    engines=[
                        EngineConfigNested(
                            name="certificates",
                            severity="pci-dss-4.0",
                            secrets=[
                                SecretConfig(path="root-ca-key", severity="none"),
                                SecretConfig(path="test-cert", severity="default"),
                            ],
                        ),
                        EngineConfigNested(
                            name="temporary-tokens",
                            severity="default",
                        ),
                    ],
                ),
                VaultConfig(
                    name="dev",
                    address="http://localhost:8201",
                    token="test",
                    severity="default",
                ),
            ],
        )

    def test_secret_config_wins(self, config: AppConfig) -> None:
        """Secret-specific config overrides everything."""
        result = config.resolve_severity("certificates", "prod", secret_path="root-ca-key")
        assert result == "none"

    def test_secret_config_overrides_vault_metadata(self, config: AppConfig) -> None:
        """Secret config wins regardless of what vault metadata says."""
        result = config.resolve_severity("certificates", "prod", secret_path="root-ca-key")
        assert result == "none"

    def test_engine_severity_override(self, config: AppConfig) -> None:
        """Engine severity overrides vault severity."""
        result = config.resolve_severity("certificates", "prod")
        assert result == "pci-dss-4.0"

    def test_vault_severity_for_unlisted_engine(self, config: AppConfig) -> None:
        """Unlisted engines inherit vault severity."""
        result = config.resolve_severity("databases", "prod")
        assert result == "critical"

    def test_dev_vault_default(self, config: AppConfig) -> None:
        """Dev vault with no engines listed uses vault severity."""
        result = config.resolve_severity("any-engine", "dev")
        assert result == "default"

    def test_secret_config_test_cert(self, config: AppConfig) -> None:
        """Another secret override works."""
        result = config.resolve_severity("certificates", "prod", secret_path="test-cert")
        assert result == "default"

    def test_unlisted_secret_inherits_engine(self, config: AppConfig) -> None:
        """A secret not listed in config inherits engine severity."""
        result = config.resolve_severity("certificates", "prod", secret_path="other-cert")
        assert result == "pci-dss-4.0"

    def test_temporary_tokens_engine_override(self, config: AppConfig) -> None:
        """Temporary tokens engine has its own severity."""
        result = config.resolve_severity("temporary-tokens", "prod")
        assert result == "default"


class TestResolveSeveritySource:
    """Tests for resolve_severity_source method."""

    @pytest.fixture()
    def config(self) -> AppConfig:
        """Create a config for source resolution testing."""
        return AppConfig(
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
                            secrets=[
                                SecretConfig(path="root-ca", severity="none"),
                            ],
                        ),
                    ],
                ),
            ],
        )

    def test_source_secret_config(self, config: AppConfig) -> None:
        severity, source = config.resolve_severity_source("certs", "prod", secret_path="root-ca")
        assert severity == "none"
        assert source == "secret_config"

    def test_source_engine_config(self, config: AppConfig) -> None:
        severity, source = config.resolve_severity_source("certs", "prod")
        assert severity == "pci-dss-4.0"
        assert source == "engine_config"

    def test_source_vault_config(self, config: AppConfig) -> None:
        severity, source = config.resolve_severity_source("unknown", "prod")
        assert severity == "critical"
        assert source == "vault_config"

    def test_source_global_default(self, config: AppConfig) -> None:
        severity, source = config.resolve_severity_source("unknown", "unknown")
        assert severity == "default"
        assert source == "global_default"


class TestBackwardCompatibility:
    """Tests for backward compatibility with old config format."""

    def test_default_severity_migrated_to_severity(self) -> None:
        """Old default_severity field is migrated to severity."""
        vc = VaultConfig(name="test", address="http://localhost", token="t", default_severity="critical")
        assert vc.severity == "critical"

    def test_severity_wins_over_default_severity(self) -> None:
        """New severity field takes precedence over deprecated default_severity."""
        vc = VaultConfig(
            name="test", address="http://localhost", token="t", severity="pci-dss-4.0", default_severity="critical"
        )
        assert vc.severity == "pci-dss-4.0"

    def test_legacy_top_level_engines(self) -> None:
        """Old top-level engines array still works."""
        config = AppConfig(
            vaults=[
                VaultConfig(name="v1", address="http://localhost", token="t", severity="critical"),
            ],
            engines=[
                EngineConfig(id="apps", default_severity="pci-dss-4.0"),
            ],
        )
        result = config.resolve_severity("apps", "v1")
        assert result == "pci-dss-4.0"

    def test_nested_engine_wins_over_legacy(self) -> None:
        """Nested engine config takes precedence over legacy top-level config."""
        config = AppConfig(
            vaults=[
                VaultConfig(
                    name="v1",
                    address="http://localhost",
                    token="t",
                    severity="default",
                    engines=[
                        EngineConfigNested(name="apps", severity="critical"),
                    ],
                ),
            ],
            engines=[
                EngineConfig(id="apps", default_severity="pci-dss-4.0"),
            ],
        )
        result = config.resolve_severity("apps", "v1")
        assert result == "critical"


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

    def test_vault_with_severity(self) -> None:
        vc = VaultConfig(name="test", address="http://localhost", token="t", severity="critical")
        assert vc.severity == "critical"

    def test_vault_optional_fields_default_none(self) -> None:
        vc = VaultConfig(name="test", address="http://localhost", token="t")
        assert vc.date_format is None
        assert vc.severity is None

    def test_vault_with_nested_engines(self) -> None:
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            token="t",
            engines=[
                EngineConfigNested(name="apps", severity="critical"),
            ],
        )
        assert len(vc.engines) == 1
        assert vc.engines[0].name == "apps"
        assert vc.engines[0].severity == "critical"

    def test_vault_get_engine_config(self) -> None:
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            token="t",
            engines=[
                EngineConfigNested(name="apps", severity="critical"),
            ],
        )
        engine = vc.get_engine_config("apps")
        assert engine is not None
        assert engine.severity == "critical"
        assert vc.get_engine_config("nonexistent") is None

    def test_vault_get_secret_config(self) -> None:
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            token="t",
            engines=[
                EngineConfigNested(
                    name="certs",
                    severity="critical",
                    secrets=[SecretConfig(path="root-ca", severity="none")],
                ),
            ],
        )
        secret = vc.get_secret_config("certs", "root-ca")
        assert secret is not None
        assert secret.severity == "none"
        assert vc.get_secret_config("certs", "other") is None
        assert vc.get_secret_config("nonexistent", "root-ca") is None


class TestSecretConfig:
    """Tests for SecretConfig model."""

    def test_valid_secret_config(self) -> None:
        sc = SecretConfig(path="my-secret", severity="critical")
        assert sc.path == "my-secret"
        assert sc.severity == "critical"

    def test_none_severity(self) -> None:
        sc = SecretConfig(path="static-data", severity="none")
        assert sc.severity == "none"


class TestEngineConfigNested:
    """Tests for EngineConfigNested model."""

    def test_engine_with_severity(self) -> None:
        ec = EngineConfigNested(name="apps", severity="critical")
        assert ec.name == "apps"
        assert ec.severity == "critical"
        assert ec.secrets == []

    def test_engine_with_secrets(self) -> None:
        ec = EngineConfigNested(
            name="certs",
            severity="pci-dss-4.0",
            secrets=[
                SecretConfig(path="root-ca", severity="none"),
            ],
        )
        assert len(ec.secrets) == 1
        assert ec.secrets[0].path == "root-ca"

    def test_engine_no_severity(self) -> None:
        ec = EngineConfigNested(name="apps")
        assert ec.severity is None


class TestSeverityValidation:
    """Tests for severity validation against configured expiry profiles."""

    def test_custom_profile_allowed(self, caplog: pytest.LogCaptureFixture) -> None:
        """Custom severity profile should not produce invalid severity warnings."""
        with caplog.at_level(logging.WARNING):
            config = AppConfig(
                expiry_profiles={
                    "default": ExpiryProfile(rotation_period="365d"),
                    "custom-policy": ExpiryProfile(rotation_period="45d"),
                },
                vaults=[
                    VaultConfig(
                        name="test",
                        address="http://localhost",
                        token="test",
                        severity="custom-policy",
                    )
                ],
            )
        assert config.resolve_severity("any-engine", "test") == "custom-policy"
        assert config.get_rotation_days("custom-policy") == 45
        assert config.get_rotation_days(config.resolve_severity("any-engine", "test")) == 45
        assert "Invalid severity value" not in caplog.text

    def test_invalid_profile_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown severity values should log warning for cascade fallback."""
        with caplog.at_level(logging.WARNING):
            AppConfig(
                vaults=[
                    VaultConfig(
                        name="test",
                        address="http://localhost",
                        token="test",
                        engines=[
                            EngineConfigNested(
                                name="apps",
                                secrets=[SecretConfig(path="api-key", severity="unknown-severity")],
                            )
                        ],
                    )
                ]
            )
        assert "Invalid severity value 'unknown-severity'" in caplog.text


class TestAppRoleConfig:
    """Tests for AppRole authentication configuration."""

    def test_approle_auth_method_valid(self) -> None:
        """AppRole auth_method accepted with valid credentials."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="test-role-id",
            secret_id="test-secret-id",
        )
        assert vc.auth_method == "approle"
        assert vc.role_id == "test-role-id"
        assert vc.secret_id == "test-secret-id"

    def test_approle_missing_role_id(self) -> None:
        """Validation fails when role_id is missing for approle auth."""
        with pytest.raises(ValueError, match="role_id"):
            VaultConfig(
                name="test",
                address="http://localhost",
                auth_method="approle",
                secret_id="test-secret-id",
            )

    def test_approle_missing_secret_id(self) -> None:
        """Validation fails when secret_id is missing for approle auth."""
        with pytest.raises(ValueError, match="secret_id"):
            VaultConfig(
                name="test",
                address="http://localhost",
                auth_method="approle",
                role_id="test-role-id",
            )

    def test_approle_with_env_vars(self) -> None:
        """AppRole config with environment variable sources is valid."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id_env="VAULT_ROLE_ID",
            secret_id_env="VAULT_SECRET_ID",
        )
        assert vc.role_id_env == "VAULT_ROLE_ID"
        assert vc.secret_id_env == "VAULT_SECRET_ID"

    def test_approle_with_file_paths(self) -> None:
        """AppRole config with file path sources is valid."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id_file="/run/secrets/role-id",
            secret_id_file="/run/secrets/secret-id",
        )
        assert vc.role_id_file == "/run/secrets/role-id"
        assert vc.secret_id_file == "/run/secrets/secret-id"

    def test_invalid_auth_method(self) -> None:
        """Validation fails for unknown auth_method."""
        with pytest.raises(ValueError, match="auth_method must be 'token' or 'approle'"):
            VaultConfig(
                name="test",
                address="http://localhost",
                auth_method="ldap",
                token="t",
            )

    def test_token_auth_still_requires_token(self) -> None:
        """Token auth still requires at least one token source."""
        with pytest.raises(ValueError, match="token, token_env, or token_file"):
            VaultConfig(name="test", address="http://localhost", auth_method="token")

    def test_approle_no_token_required(self) -> None:
        """AppRole auth does not require token fields."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="rid",
            secret_id="sid",
        )
        assert vc.token is None

    def test_resolve_role_id_literal(self) -> None:
        """resolve_role_id returns literal role_id."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="literal-role-id",
            secret_id="sid",
        )
        assert vc.resolve_role_id() == "literal-role-id"

    def test_resolve_secret_id_literal(self) -> None:
        """resolve_secret_id returns literal secret_id."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="rid",
            secret_id="literal-secret-id",
        )
        assert vc.resolve_secret_id() == "literal-secret-id"

    def test_resolve_role_id_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """resolve_role_id reads from environment variable."""
        monkeypatch.setenv("TEST_ROLE_ID", "env-role-id")
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id_env="TEST_ROLE_ID",
            secret_id="sid",
        )
        assert vc.resolve_role_id() == "env-role-id"

    def test_resolve_secret_id_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """resolve_secret_id reads from environment variable."""
        monkeypatch.setenv("TEST_SECRET_ID", "env-secret-id")
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="rid",
            secret_id_env="TEST_SECRET_ID",
        )
        assert vc.resolve_secret_id() == "env-secret-id"

    def test_resolve_role_id_file(self, tmp_path: "pathlib.Path") -> None:
        """resolve_role_id reads from file."""
        role_file = tmp_path / "role_id"
        role_file.write_text("file-role-id\n")
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id_file=str(role_file),
            secret_id="sid",
        )
        assert vc.resolve_role_id() == "file-role-id"

    def test_resolve_secret_id_file(self, tmp_path: "pathlib.Path") -> None:
        """resolve_secret_id reads from file."""
        secret_file = tmp_path / "secret_id"
        secret_file.write_text("file-secret-id\n")
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="rid",
            secret_id_file=str(secret_file),
        )
        assert vc.resolve_secret_id() == "file-secret-id"

    def test_resolve_role_id_file_priority(
        self,
        tmp_path: "pathlib.Path",
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """File has highest priority for role_id resolution."""
        role_file = tmp_path / "role_id"
        role_file.write_text("file-role-id\n")
        monkeypatch.setenv("TEST_ROLE_ID", "env-role-id")
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="literal",
            role_id_env="TEST_ROLE_ID",
            role_id_file=str(role_file),
            secret_id="sid",
        )
        assert vc.resolve_role_id() == "file-role-id"

    def test_resolve_secret_id_file_priority(
        self,
        tmp_path: "pathlib.Path",
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """File has highest priority for secret_id resolution."""
        secret_file = tmp_path / "secret_id"
        secret_file.write_text("file-secret-id\n")
        monkeypatch.setenv("TEST_SECRET_ID", "env-secret-id")
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="rid",
            secret_id="literal",
            secret_id_env="TEST_SECRET_ID",
            secret_id_file=str(secret_file),
        )
        assert vc.resolve_secret_id() == "file-secret-id"

    def test_resolve_role_id_env_over_literal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variable has higher priority than literal for role_id."""
        monkeypatch.setenv("TEST_ROLE_ID", "env-role-id")
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="literal",
            role_id_env="TEST_ROLE_ID",
            secret_id="sid",
        )
        assert vc.resolve_role_id() == "env-role-id"

    def test_resolve_role_id_missing_file(self, tmp_path: "pathlib.Path") -> None:
        """resolve_role_id returns None when file does not exist."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id_file=str(tmp_path / "nonexistent"),
            secret_id="sid",
        )
        assert vc.resolve_role_id() is None

    def test_resolve_secret_id_missing_file(self, tmp_path: "pathlib.Path") -> None:
        """resolve_secret_id returns None when file does not exist."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="rid",
            secret_id_file=str(tmp_path / "nonexistent"),
        )
        assert vc.resolve_secret_id() is None

    def test_resolve_role_id_missing_env(self) -> None:
        """resolve_role_id returns None when env var is not set."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id_env="NONEXISTENT_ROLE_VAR",
            secret_id="sid",
        )
        assert vc.resolve_role_id() is None

    def test_resolve_secret_id_missing_env(self) -> None:
        """resolve_secret_id returns None when env var is not set."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="rid",
            secret_id_env="NONEXISTENT_SECRET_VAR",
        )
        assert vc.resolve_secret_id() is None

    def test_approle_mount_point_default(self) -> None:
        """AppRole mount point defaults to 'approle'."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="test-role-id",
            secret_id="test-secret-id",
        )
        assert vc.approle_mount_point == "approle"

    def test_approle_mount_point_custom(self) -> None:
        """AppRole mount point can be customized."""
        vc = VaultConfig(
            name="test",
            address="http://localhost",
            auth_method="approle",
            role_id="test-role-id",
            secret_id="test-secret-id",
            approle_mount_point="my-approle",
        )
        assert vc.approle_mount_point == "my-approle"
