# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Configuration loading and validation for Chronowarden."""

import logging
import os
import pathlib
import re
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

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

VALID_SEVERITY_VALUES = {"default", "critical", "pci-dss-4.0", "none"}

_DURATION_PATTERN = re.compile(r"^(\d+)([dmy])$")


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

    rotation_period: str = Field(description="Rotation period (e.g. '365d', '6m', '1y')")

    @field_validator("rotation_period")
    @classmethod
    def validate_rotation_period(cls, v: str) -> str:
        """Validate the rotation period format."""
        parse_duration_to_days(v)
        return v

    @property
    def rotation_days(self) -> int:
        """Return rotation period in days."""
        return parse_duration_to_days(self.rotation_period)


class EngineConfig(BaseModel):
    """Per-engine configuration."""

    id: str = Field(description="Engine identifier (e.g. 'secret/my-app')")
    default_severity: Optional[str] = Field(default=None, description="Default severity for all secrets in this engine")

    @field_validator("default_severity")
    @classmethod
    def validate_severity(cls, v: Optional[str]) -> Optional[str]:
        """Validate severity value."""
        if v is not None and v not in VALID_SEVERITY_VALUES:
            logger.warning("Invalid severity value '%s' in engine config, will use 'default'", v)
        return v


class VaultConfig(BaseModel):
    """Configuration for a single Vault instance."""

    name: str = Field(description="Unique identifier for this Vault instance")
    address: str = Field(description="Vault server address (e.g. https://vault.example.com:8200)")
    token: Optional[str] = Field(default=None, description="Vault token (prefer token_env or token_file)")
    token_env: Optional[str] = Field(default=None, description="Environment variable containing the Vault token")
    token_file: Optional[str] = Field(default=None, description="Path to file containing the Vault token")
    namespace: Optional[str] = Field(default=None, description="Vault namespace (enterprise feature)")
    mount_path: str = Field(default="secret", description="KV secrets engine mount path")
    verify_ssl: bool = Field(default=True, description="Whether to verify TLS certificates")
    auth_method: str = Field(default="token", description="Vault authentication method")
    date_format: Optional[str] = Field(default=None, description="Date format override for this vault (YYYY-MM-DD)")
    default_severity: Optional[str] = Field(default=None, description="Default severity for secrets in this vault")

    @model_validator(mode="after")
    def validate_token_source(self) -> "VaultConfig":
        """Ensure at least one token source is configured."""
        if not self.token and not self.token_env and not self.token_file:
            raise ValueError(f"Vault '{self.name}': at least one of token, token_env, or token_file must be set")
        return self

    @field_validator("default_severity")
    @classmethod
    def validate_severity(cls, v: Optional[str]) -> Optional[str]:
        """Validate severity value."""
        if v is not None and v not in VALID_SEVERITY_VALUES:
            logger.warning("Invalid severity value '%s' in vault config, will use 'default'", v)
        return v

    def resolve_token(self) -> Optional[str]:
        """
        Resolve the Vault token from the configured source.

        Priority: token_file > token_env > token (literal).

        Returns:
            The resolved token string, or None if resolution fails.
        """
        if self.token_file:
            try:
                return pathlib.Path(self.token_file).read_text().strip()
            except OSError:
                logger.exception("Failed to read token file for vault '%s'", self.name)
                return None

        if self.token_env:
            value = os.environ.get(self.token_env)
            if value is None:
                logger.warning("Environment variable '%s' not set for vault '%s'", self.token_env, self.name)
            return value

        return self.token


class AppConfig(BaseModel):
    """Root application configuration."""

    vaults: list[VaultConfig] = Field(default_factory=list, description="List of Vault instances to connect to")
    date_format: str = Field(default="YYYY-MM-DD", description="Global date format for chronowarden_ttl")
    polling_interval: str = Field(default="6h", description="Global polling interval for change detection")
    expiry_profiles: dict[str, ExpiryProfile] = Field(
        default_factory=lambda: {
            name: ExpiryProfile(**profile) for name, profile in DEFAULT_EXPIRY_PROFILES.items()
        },
        description="Expiry profiles mapping severity names to rotation periods",
    )
    engines: list[EngineConfig] = Field(default_factory=list, description="Per-engine configuration overrides")

    @model_validator(mode="after")
    def validate_unique_names(self) -> "AppConfig":
        """Ensure all vault names are unique."""
        names = [v.name for v in self.vaults]
        duplicates = [n for n in names if names.count(n) > 1]
        if duplicates:
            raise ValueError(f"Duplicate vault names: {', '.join(set(duplicates))}")
        return self

    def get_engine_config(self, engine_id: str) -> Optional[EngineConfig]:
        """
        Get engine configuration by ID.

        Args:
            engine_id: The engine identifier.

        Returns:
            The engine config, or None if not found.
        """
        for engine in self.engines:
            if engine.id == engine_id:
                return engine
        return None

    def resolve_severity(
        self,
        secret_severity: Optional[str],
        engine_id: Optional[str],
        vault_name: Optional[str],
    ) -> str:
        """
        Resolve severity using the configuration cascade.

        Priority: secret → engine → vault → global default.

        Args:
            secret_severity: Severity from Vault custom_metadata.
            engine_id: Engine identifier for engine-level override.
            vault_name: Vault name for vault-level override.

        Returns:
            Resolved severity string.
        """
        if secret_severity is not None and secret_severity in VALID_SEVERITY_VALUES:
            return secret_severity

        if secret_severity is not None:
            logger.warning("Invalid severity '%s', falling through to cascade", secret_severity)

        if engine_id is not None:
            engine_config = self.get_engine_config(engine_id)
            if engine_config and engine_config.default_severity:
                return engine_config.default_severity

        if vault_name is not None:
            for vault in self.vaults:
                if vault.name == vault_name and vault.default_severity:
                    return vault.default_severity

        return "default"

    def get_rotation_days(self, severity: str) -> int:
        """
        Get rotation period in days for a given severity.

        Args:
            severity: The severity profile name.

        Returns:
            Number of days for the rotation period.
        """
        profile = self.expiry_profiles.get(severity)
        if profile:
            return profile.rotation_days

        default_profile = self.expiry_profiles.get("default")
        if default_profile:
            return default_profile.rotation_days

        return 365

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

    If no configuration file is found, returns a default (empty) config.

    Args:
        config_path: Explicit path to the config file.

    Returns:
        Validated application configuration.
    """
    path = _resolve_config_path(config_path)

    if path is None:
        logger.info("No configuration file found, using defaults")
        return AppConfig()

    logger.info("Loading configuration from %s", path)
    try:
        raw = path.read_text()
        data = yaml.safe_load(raw)
    except OSError:
        logger.exception("Failed to read configuration file")
        return AppConfig()
    except yaml.YAMLError:
        logger.exception("Failed to parse configuration file")
        return AppConfig()

    if not data:
        return AppConfig()

    return AppConfig.model_validate(data)


def _resolve_config_path(explicit_path: Optional[str] = None) -> Optional[pathlib.Path]:
    """
    Resolve the configuration file path.

    Args:
        explicit_path: Explicitly provided path (highest priority).

    Returns:
        Path to the config file, or None if not found.
    """
    if explicit_path:
        path = pathlib.Path(explicit_path)
        if path.is_file():
            return path
        logger.warning("Explicit config path does not exist: %s", explicit_path)
        return None

    env_path = os.environ.get(_ENV_CONFIG_PATH)
    if env_path:
        path = pathlib.Path(env_path)
        if path.is_file():
            return path
        logger.warning("Config path from %s does not exist: %s", _ENV_CONFIG_PATH, env_path)
        return None

    for candidate in _DEFAULT_CONFIG_PATHS:
        if candidate.is_file():
            return candidate

    return None
