# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Configuration loading and validation for Chronowarden."""

import logging
import os
import pathlib
import re
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger("uvicorn.error")

_DEFAULT_CONFIG_PATHS = [
    pathlib.Path("/etc/chronowarden/config.yaml"),
    pathlib.Path("config.yaml"),
]

_ENV_CONFIG_PATH = "CHRONOWARDEN_CONFIG"

DEFAULT_EXPIRY_PROFILES: dict[str, dict[str, str]] = {
    "default": {"rotation_period": "365d"},
    "critical": {"rotation_period": "6m"},
    "pci-dss-4.0": {"rotation_period": "90d"},
}

RESERVED_SEVERITY_VALUES = {"none"}

DEFAULT_ALERT_THRESHOLD = "30d"

# UI theme IDs; keep in sync with THEME_DEFINITIONS in frontend/src/lib/stores/theme.ts
THEME_IDS = frozenset({"default", "bison"})
DEFAULT_THEME = "default"
_ENV_THEME = "CHRONOWARDEN_THEME"

_DURATION_PATTERN = re.compile(r"^(\d+)([dmy])$")

# Unknown keys are rejected so that typos never get silently ignored
_STRICT = ConfigDict(extra="forbid")


class ConfigError(Exception):
    """Raised when the configuration file is missing, unreadable or invalid."""


def parse_duration_to_days(duration: str) -> int:
    """
    Parse a duration string (e.g. '365d', '6m', '1y') to number of days.

    Args:
        duration: Duration string with unit suffix (d=days, m=months, y=years).

    Returns:
        Number of days.

    Raises:
        ValueError: If format is invalid.
    """
    match = _DURATION_PATTERN.match(duration.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration format: '{duration}'. Expected format: <number><d|m|y> (e.g. '365d', '6m')")

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "d":
        return value
    elif unit == "m":
        return value * 30
    elif unit == "y":
        return value * 365
    else:
        raise ValueError(f"Unknown duration unit: '{unit}'")


class ExpiryProfile(BaseModel):
    """Configuration for a single expiry profile."""

    model_config = _STRICT

    rotation_period: str = Field(description="Rotation period (e.g. '365d', '6m', '1y')")
    alert_threshold: str = Field(
        default=DEFAULT_ALERT_THRESHOLD,
        description="Secrets expiring within this window get the 'warning' status (e.g. '30d', '1m')",
    )
    confirmation_grace: Optional[str] = Field(
        default=None,
        description="How long a rotation may stay unconfirmed before it is overdue (default: confirmation_grace)",
    )

    @field_validator("rotation_period", "alert_threshold", "confirmation_grace")
    @classmethod
    def validate_duration(cls, v: Optional[str]) -> Optional[str]:
        """Validate the duration format."""
        if v is not None:
            parse_duration_to_days(v)
        return v

    @property
    def rotation_days(self) -> int:
        """Return rotation period in days."""
        return parse_duration_to_days(self.rotation_period)

    @property
    def alert_days(self) -> int:
        """Return the alert threshold in days."""
        return parse_duration_to_days(self.alert_threshold)


class SecretConfig(BaseModel):
    """Per-secret overrides in config.yaml."""

    model_config = _STRICT

    path: str = Field(description="Exact secret path within the engine")
    severity: Optional[str] = Field(default=None, description="Severity override for this specific secret")
    confirmation_required: Optional[bool] = Field(
        default=None, description="Whether rotations of this secret must be confirmed as applied (ADR-021)"
    )

    @model_validator(mode="after")
    def check_has_override(self) -> "SecretConfig":
        """A secret entry must override something."""
        if self.severity is None and self.confirmation_required is None:
            raise ValueError(f"secret '{self.path}' sets neither severity nor confirmation_required")
        return self


class EngineConfigNested(BaseModel):
    """Per-engine configuration nested within a vault."""

    model_config = _STRICT

    name: str = Field(description="Engine name (mount point)")
    severity: Optional[str] = Field(default=None, description="Severity override for this engine")
    confirmation_required: Optional[bool] = Field(
        default=None, description="Whether rotations in this engine must be confirmed as applied"
    )
    secrets: list[SecretConfig] = Field(default_factory=list, description="Per-secret overrides")


class VaultConfig(BaseModel):
    """Configuration for a single Vault instance."""

    model_config = _STRICT

    name: str = Field(description="Unique identifier for this Vault instance")
    address: str = Field(description="Vault server address (e.g. https://vault.example.com:8200)")
    auth_method: str = Field(default="token", description="Authentication method: 'token' or 'approle'")

    # Token auth fields
    token: Optional[str] = Field(default=None, description="Vault token (prefer token_env or token_file)")
    token_env: Optional[str] = Field(default=None, description="Environment variable containing the Vault token")
    token_file: Optional[str] = Field(default=None, description="Path to file containing the Vault token")

    # AppRole auth fields
    role_id: Optional[str] = Field(default=None, description="AppRole role ID")
    role_id_env: Optional[str] = Field(default=None, description="Environment variable containing role ID")
    role_id_file: Optional[str] = Field(default=None, description="Path to file containing role ID")
    secret_id: Optional[str] = Field(default=None, description="AppRole secret ID")
    secret_id_env: Optional[str] = Field(default=None, description="Environment variable containing secret ID")
    secret_id_file: Optional[str] = Field(default=None, description="Path to file containing secret ID")
    approle_mount_point: str = Field(default="approle", description="AppRole auth method mount point")

    namespace: Optional[str] = Field(default=None, description="Vault namespace (enterprise feature)")
    mount_path: str = Field(default="secret", description="KV secrets engine mount path")
    verify_ssl: bool = Field(default=True, description="Whether to verify TLS certificates")
    date_format: Optional[str] = Field(default=None, description="Date format override for this vault (YYYY-MM-DD)")
    severity: Optional[str] = Field(default=None, description="Default severity for all secrets in this vault")
    confirmation_required: Optional[bool] = Field(
        default=None, description="Whether rotations in this vault must be confirmed as applied (default: false)"
    )
    engines: list[EngineConfigNested] = Field(
        default_factory=list, description="Nested engine configurations with optional overrides"
    )

    @model_validator(mode="after")
    def validate_auth_config(self) -> "VaultConfig":
        """Validate authentication configuration based on auth_method."""
        if self.auth_method not in {"token", "approle"}:
            raise ValueError(f"Vault '{self.name}': auth_method must be 'token' or 'approle', got '{self.auth_method}'")

        if self.auth_method == "token":
            if not any([self.token, self.token_env, self.token_file]):
                raise ValueError(
                    f"Vault '{self.name}': when auth_method='token', at least one of "
                    "token, token_env, or token_file must be set"
                )

        elif self.auth_method == "approle":
            if not any([self.role_id, self.role_id_env, self.role_id_file]):
                raise ValueError(
                    f"Vault '{self.name}': when auth_method='approle', at least one of "
                    "role_id, role_id_env, or role_id_file must be set"
                )
            if not any([self.secret_id, self.secret_id_env, self.secret_id_file]):
                raise ValueError(
                    f"Vault '{self.name}': when auth_method='approle', at least one of "
                    "secret_id, secret_id_env, or secret_id_file must be set"
                )

        return self

    def get_engine_config(self, engine_name: str) -> Optional[EngineConfigNested]:
        """
        Get nested engine configuration by name.

        Args:
            engine_name: The engine name (mount point).

        Returns:
            The engine config, or None if not found.
        """
        for engine in self.engines:
            if engine.name == engine_name:
                return engine
        return None

    def get_secret_config(self, engine_name: str, secret_path: str) -> Optional[SecretConfig]:
        """
        Get secret-specific configuration from nested engines.

        Args:
            engine_name: The engine name (mount point).
            secret_path: The exact secret path.

        Returns:
            The secret config, or None if not found.
        """
        engine = self.get_engine_config(engine_name)
        if engine is None:
            return None
        for secret in engine.secrets:
            if secret.path == secret_path:
                return secret
        return None

    def _resolve_credential(self, field: str) -> Optional[str]:
        """
        Resolve a credential from its ``<field>_file``, ``<field>_env`` or literal setting, in that order.

        Returns:
            The resolved value, or None if resolution fails.
        """
        path, env = getattr(self, f"{field}_file"), getattr(self, f"{field}_env")
        if path:
            try:
                return pathlib.Path(path).read_text().strip()
            except OSError:
                logger.exception("Failed to read %s file for vault '%s'", field, self.name)
                return None

        if env:
            value = os.environ.get(env)
            if value is None:
                logger.warning("Environment variable '%s' not set for vault '%s'", env, self.name)
            return value

        return getattr(self, field)

    def resolve_token(self) -> Optional[str]:
        """Resolve the Vault token: token_file > token_env > token (literal)."""
        return self._resolve_credential("token")

    def resolve_role_id(self) -> Optional[str]:
        """Resolve the AppRole role_id: role_id_file > role_id_env > role_id (literal)."""
        return self._resolve_credential("role_id")

    def resolve_secret_id(self) -> Optional[str]:
        """Resolve the AppRole secret_id: secret_id_file > secret_id_env > secret_id (literal)."""
        return self._resolve_credential("secret_id")


class ComplianceScope(BaseModel):
    """Which secrets a snapshot covers; empty lists mean all."""

    model_config = _STRICT

    vaults: list[str] = Field(default_factory=list, description="Vault names")
    engines: list[str] = Field(default_factory=list, description="Engine mount paths")
    systems: list[str] = Field(default_factory=list, description="System names")
    privileged_only: bool = Field(default=False, description="Only secrets marked chronowarden_privileged")


class ReportingCadence(BaseModel):
    """A reporting period whose snapshot is closed by hand after the period ends."""

    model_config = _STRICT

    period: Literal["monthly", "quarterly", "half-yearly", "yearly"]
    scope: ComplianceScope = Field(default_factory=ComplianceScope)


class ReportingConfig(BaseModel):
    """Periodic reporting; no cadences means not opted in."""

    model_config = _STRICT

    cadences: list[ReportingCadence] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_unique_periods(self) -> "ReportingConfig":
        """One cadence per period, so a period's snapshot is unambiguous."""
        periods = [cadence.period for cadence in self.cadences]
        duplicates = sorted({period for period in periods if periods.count(period) > 1})
        if duplicates:
            raise ValueError(f"duplicate reporting cadence(s): {', '.join(duplicates)}")
        return self


class ComplianceConfig(BaseModel):
    """Compliance evidence settings (#94)."""

    model_config = _STRICT

    reporting: ReportingConfig = Field(default_factory=ReportingConfig)


class MetricsConfig(BaseModel):
    """Prometheus metrics settings (ADR-022)."""

    model_config = _STRICT

    enabled: bool = Field(default=False, description="Serve Prometheus metrics at /api/v1/metrics")


class UiConfig(BaseModel):
    """Instance-wide UI settings."""

    model_config = _STRICT

    default_theme: Optional[str] = Field(
        default=None, description=f"Default UI theme for this instance ({', '.join(sorted(THEME_IDS))})"
    )

    @field_validator("default_theme")
    @classmethod
    def validate_default_theme(cls, v: Optional[str]) -> Optional[str]:
        """Reject unknown theme IDs."""
        if v is not None and v not in THEME_IDS:
            raise ValueError(f"Unknown theme '{v}'. Allowed values: {', '.join(sorted(THEME_IDS))}")
        return v


class AppConfig(BaseModel):
    """Root application configuration."""

    model_config = _STRICT

    ca_certs_dir: Optional[str] = Field(
        default=None, description="Directory containing CA certificates (all .pem, .crt, .cert files will be loaded)"
    )
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error reporting")
    sentry_traces_sample_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Sentry transaction tracing sample rate (0.0-1.0)"
    )
    sentry_profiles_sample_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Sentry profiling sample rate (0.0-1.0)"
    )
    vaults: list[VaultConfig] = Field(default_factory=list, description="List of Vault instances to connect to")
    date_format: str = Field(default="YYYY-MM-DD", description="Global date format for chronowarden_ttl")
    confirmation_grace: str = Field(
        default="7d", description="How long a rotation may stay unconfirmed before it is overdue (per profile override)"
    )
    polling_interval: str = Field(default="6h", description="Global polling interval for change detection")
    vault_reconnect_interval: int = Field(
        default=120,
        ge=10,
        description="Seconds between reconnection attempts for offline or disconnected vault instances (minimum 10)",
    )
    vault_reconnect_max_attempts: int = Field(
        default=5,
        ge=1,
        description="Maximum number of reconnect cycles before the background reconnect loop stops (minimum 1)",
    )
    expiry_profiles: dict[str, ExpiryProfile] = Field(
        default_factory=lambda: {name: ExpiryProfile(**profile) for name, profile in DEFAULT_EXPIRY_PROFILES.items()},
        description="Expiry profiles mapping severity names to rotation periods",
    )
    ui: UiConfig = Field(default_factory=UiConfig, description="Instance-wide UI settings")
    metrics: MetricsConfig = Field(default_factory=MetricsConfig, description="Prometheus metrics (off by default)")
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig, description="Compliance evidence settings")
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Host names Chronowarden answers to (e.g. chronowarden.example.com, *.example.com); "
        "set it to stop DNS rebinding from other web pages",
    )

    @field_validator("confirmation_grace")
    @classmethod
    def validate_confirmation_grace(cls, v: str) -> str:
        """Validate the duration format."""
        parse_duration_to_days(v)
        return v

    @model_validator(mode="after")
    def validate_unique_names(self) -> "AppConfig":
        """Ensure all vault names are unique."""
        names = [v.name for v in self.vaults]
        duplicates = [n for n in names if names.count(n) > 1]
        if duplicates:
            raise ValueError(f"Duplicate vault names: {', '.join(set(duplicates))}")
        return self

    @model_validator(mode="after")
    def merge_default_expiry_profiles(self) -> "AppConfig":
        """Ensure built-in profiles are always present; user-provided profiles take precedence."""
        merged = {name: ExpiryProfile(**profile) for name, profile in DEFAULT_EXPIRY_PROFILES.items()}
        merged.update(self.expiry_profiles)
        self.expiry_profiles = merged
        return self

    @model_validator(mode="after")
    def validate_compliance_vaults(self) -> "AppConfig":
        """Reporting scopes may only name configured vaults."""
        known = {vault.name for vault in self.vaults}
        unknown = sorted(
            {name for cadence in self.compliance.reporting.cadences for name in cadence.scope.vaults} - known
        )
        if unknown:
            raise ValueError(f"compliance reporting scope names unknown vault(s): {', '.join(unknown)}")
        return self

    @model_validator(mode="after")
    def validate_severity_values(self) -> "AppConfig":
        """
        Reject severity values that match no expiry profile.

        Raises:
            ValueError: Listing every unknown severity and the allowed values.
        """
        valid_values = set(self.expiry_profiles) | RESERVED_SEVERITY_VALUES
        unknown = [
            f"'{severity}' in {context}"
            for severity, context in self._iter_configured_severities()
            if severity not in valid_values
        ]
        if unknown:
            raise ValueError(
                f"Unknown severity {', '.join(unknown)}. Allowed values: {', '.join(sorted(valid_values))}"
            )
        return self

    def _iter_configured_severities(self) -> list[tuple[str, str]]:
        """Return (severity, context) for every severity set at vault, engine or secret level."""
        found: list[tuple[str, str]] = []
        for vault in self.vaults:
            if vault.severity is not None:
                found.append((vault.severity, f"vault '{vault.name}'"))
            for engine in vault.engines:
                if engine.severity is not None:
                    found.append((engine.severity, f"engine '{vault.name}/{engine.name}'"))
                for secret in engine.secrets:
                    if secret.severity is not None:
                        found.append((secret.severity, f"secret '{vault.name}/{engine.name}/{secret.path}'"))
        return found

    def _get_vault_config(self, vault_name: str) -> Optional[VaultConfig]:
        """
        Get vault configuration by name.

        Args:
            vault_name: The vault instance name.

        Returns:
            The vault config, or None if not found.
        """
        for vault in self.vaults:
            if vault.name == vault_name:
                return vault
        return None

    def _resolve_severity_with_source(
        self,
        engine_id: Optional[str],
        vault_name: Optional[str],
        secret_path: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Resolve severity and its source using the configuration cascade.

        Config is the source of truth. Priority (highest to lowest):
            1. Secret-specific config (vaults[].engines[].secrets[])
            2. Engine config (vaults[].engines[].severity)
            3. Vault config (vaults[].severity)
            4. Global default ("default" profile / 365 days)

        Args:
            engine_id: Engine identifier for engine-level override.
            vault_name: Vault name for vault-level override.
            secret_path: Secret path for secret-level config override.

        Returns:
            Tuple of (severity, source) where source describes the cascade level.
        """
        vault_config = self._get_vault_config(vault_name) if vault_name else None

        if vault_config and engine_id and secret_path:
            secret_config = vault_config.get_secret_config(engine_id, secret_path)
            if secret_config and secret_config.severity:
                return secret_config.severity, "secret_config"

        if vault_config and engine_id:
            engine_config = vault_config.get_engine_config(engine_id)
            if engine_config and engine_config.severity:
                return engine_config.severity, "engine_config"

        if vault_config and vault_config.severity:
            return vault_config.severity, "vault_config"

        return "default", "global_default"

    def resolve_severity(
        self,
        engine_id: Optional[str],
        vault_name: Optional[str],
        secret_path: Optional[str] = None,
    ) -> str:
        """
        Resolve severity using the configuration cascade.

        Args:
            engine_id: Engine identifier for engine-level override.
            vault_name: Vault name for vault-level override.
            secret_path: Secret path for secret-level config override.

        Returns:
            Resolved severity string.
        """
        severity, _ = self._resolve_severity_with_source(engine_id, vault_name, secret_path)
        return severity

    def resolve_severity_source(
        self,
        engine_id: Optional[str],
        vault_name: Optional[str],
        secret_path: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Resolve severity and return the source that determined it.

        Args:
            engine_id: Engine identifier.
            vault_name: Vault name.
            secret_path: Secret path.

        Returns:
            Tuple of (severity, source) where source describes the cascade level.
        """
        return self._resolve_severity_with_source(engine_id, vault_name, secret_path)

    def resolve_default_theme(self) -> str:
        """
        Return the instance default UI theme: `ui.default_theme`, then CHRONOWARDEN_THEME, then 'default'.

        Returns:
            A theme ID from THEME_IDS.
        """
        return self.ui.default_theme or os.environ.get(_ENV_THEME) or DEFAULT_THEME

    def resolve_confirmation_required(self, engine_id: str, vault_name: str, secret_path: str) -> bool:
        """
        Resolve whether a secret's rotations must be confirmed: secret → engine → vault → false (ADR-021).

        Args:
            engine_id: Engine mount path.
            vault_name: Vault name.
            secret_path: Secret path within the engine.

        Returns:
            Whether confirmation is required.
        """
        vault_config = self._get_vault_config(vault_name)
        if vault_config is None:
            return False
        secret_config = vault_config.get_secret_config(engine_id, secret_path)
        if secret_config and secret_config.confirmation_required is not None:
            return secret_config.confirmation_required
        engine_config = vault_config.get_engine_config(engine_id)
        if engine_config and engine_config.confirmation_required is not None:
            return engine_config.confirmation_required
        return bool(vault_config.confirmation_required)

    def get_confirmation_grace_days(self, severity: str) -> int:
        """Return how many days a rotation may stay unconfirmed: the profile's grace, else the global one."""
        profile = self._profile_for(severity)
        if profile and profile.confirmation_grace:
            return parse_duration_to_days(profile.confirmation_grace)
        return parse_duration_to_days(self.confirmation_grace)

    def _profile_for(self, severity: str) -> Optional[ExpiryProfile]:
        """Return the expiry profile for a severity, falling back to the 'default' profile."""
        return self.expiry_profiles.get(severity) or self.expiry_profiles.get("default")

    def get_rotation_days(self, severity: str) -> int:
        """
        Get rotation period in days for a given severity.

        Args:
            severity: The severity profile name.

        Returns:
            Number of days for the rotation period.
        """
        profile = self._profile_for(severity)
        return profile.rotation_days if profile else 365

    def get_alert_days(self, severity: str) -> int:
        """
        Get the alert threshold in days for a given severity.

        Args:
            severity: The severity profile name.

        Returns:
            Number of days before expiry at which a secret gets the 'warning' status.
        """
        profile = self._profile_for(severity)
        return profile.alert_days if profile else parse_duration_to_days(DEFAULT_ALERT_THRESHOLD)

    def resolve_date_format(self, vault_name: Optional[str] = None) -> str:
        """
        Resolve date format using the configuration cascade.

        Priority: vault → global.

        Args:
            vault_name: Vault name for vault-level override.

        Returns:
            Date format string.
        """
        if vault_name is not None:
            for vault in self.vaults:
                if vault.name == vault_name and vault.date_format:
                    return vault.date_format

        return self.date_format


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from a YAML file.

    Resolution order:
        1. Explicit path argument
        2. CHRONOWARDEN_CONFIG environment variable
        3. /etc/chronowarden/config.yaml
        4. ./config.yaml

    If no configuration file exists at the default paths, returns a default (empty) config. An empty file also
    yields the defaults.

    Args:
        config_path: Explicit path to the config file.

    Returns:
        Validated application configuration.

    Raises:
        ConfigError: If an explicitly requested file is missing, or the file can't be read, parsed or validated.
    """
    _check_theme_env()
    path = _resolve_config_path(config_path)

    if path is None:
        logger.info("No configuration file found, using defaults")
        return AppConfig()

    logger.info("Loading configuration from %s", path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Cannot read configuration file {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(f"Configuration file {path} is not valid UTF-8: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Cannot parse configuration file {path}: {exc}") from exc

    if data is None:
        return AppConfig()
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration file {path} must contain a mapping, got {type(data).__name__}")

    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(_format_validation_errors(path, exc)) from exc


def _check_theme_env() -> None:
    """
    Validate the CHRONOWARDEN_THEME environment variable, if set.

    Raises:
        ConfigError: If it names an unknown theme.
    """
    theme = os.environ.get(_ENV_THEME)
    if theme is not None and theme not in THEME_IDS:
        raise ConfigError(
            f"{_ENV_THEME}='{theme}' is not a known theme. Allowed values: {', '.join(sorted(THEME_IDS))}"
        )


def _format_validation_errors(path: pathlib.Path, exc: ValidationError) -> str:
    """
    Format every validation error as one line with its key path.

    Args:
        path: The configuration file that failed validation.
        exc: The pydantic validation error.

    Returns:
        Multi-line message, one `key.path: reason` line per error.
    """
    lines = [f"Invalid configuration in {path} ({exc.error_count()} error(s)):"]
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(root)"
        lines.append(f"  {location}: {error['msg']}")
    return "\n".join(lines)


def _resolve_config_path(explicit_path: Optional[str] = None) -> Optional[pathlib.Path]:
    """
    Resolve the configuration file path.

    Args:
        explicit_path: Explicitly provided path (highest priority).

    Returns:
        Path to the config file, or None if no file exists at the default paths.

    Raises:
        ConfigError: If the explicit path or the CHRONOWARDEN_CONFIG path does not exist.
    """
    if explicit_path:
        path = pathlib.Path(explicit_path)
        if path.is_file():
            return path
        raise ConfigError(f"Configuration file does not exist: {explicit_path}")

    env_path = os.environ.get(_ENV_CONFIG_PATH)
    if env_path:
        path = pathlib.Path(env_path)
        if path.is_file():
            return path
        raise ConfigError(f"Configuration file from {_ENV_CONFIG_PATH} does not exist: {env_path}")

    for candidate in _DEFAULT_CONFIG_PATHS:
        if candidate.is_file():
            return candidate

    return None
