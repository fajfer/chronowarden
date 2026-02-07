# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Configuration loading and validation for Chronowarden."""

import logging
import os
import pathlib
from typing import Optional

import yaml
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATHS = [
    pathlib.Path("/etc/chronowarden/config.yaml"),
    pathlib.Path("config.yaml"),
]

_ENV_CONFIG_PATH = "CHRONOWARDEN_CONFIG"


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

    @model_validator(mode="after")
    def validate_token_source(self) -> "VaultConfig":
        """Ensure at least one token source is configured."""
        if not self.token and not self.token_env and not self.token_file:
            raise ValueError(f"Vault '{self.name}': at least one of token, token_env, or token_file must be set")
        return self

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

    @model_validator(mode="after")
    def validate_unique_names(self) -> "AppConfig":
        """Ensure all vault names are unique."""
        names = [v.name for v in self.vaults]
        duplicates = [n for n in names if names.count(n) > 1]
        if duplicates:
            raise ValueError(f"Duplicate vault names: {', '.join(set(duplicates))}")
        return self


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
