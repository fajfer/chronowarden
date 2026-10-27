# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Configuration loading and validation for Chronowarden."""

import logging
import os
import pathlib
import re
from typing import Annotated, Literal, Optional, Union

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyNetwork,
    ValidationError,
    field_validator,
    model_validator,
)

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
_INTERVAL_PATTERN = re.compile(r"^(\d+)([smhd])$")
_INTERVAL_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
MIN_POLLING_SECONDS = 60

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


def parse_interval_seconds(interval: str) -> Optional[int]:
    """
    Parse a polling interval such as '30m', '6h' or '1d' to seconds; 'off' gives None.

    Unlike expiry durations, `m` means minutes here (ADR-013).

    Raises:
        ValueError: If the format is invalid or the interval is shorter than `MIN_POLLING_SECONDS`.
    """
    text = interval.strip().lower()
    if text == "off":
        return None
    match = _INTERVAL_PATTERN.match(text)
    if not match:
        raise ValueError(f"Invalid interval: '{interval}'. Expected <number><s|m|h|d> (e.g. '30m', '6h') or 'off'")
    seconds = int(match.group(1)) * _INTERVAL_UNITS[match.group(2)]
    if seconds < MIN_POLLING_SECONDS:
        raise ValueError(f"Interval '{interval}' is shorter than {MIN_POLLING_SECONDS} seconds")
    return seconds


def _resolve_value(name: str, literal: Optional[str], env: Optional[str], path: Optional[str]) -> Optional[str]:
    """Read a value from its file, env var or literal setting, in that order (like vault credentials)."""
    if path:
        try:
            return pathlib.Path(path).read_text().strip()
        except OSError:
            logger.exception("Failed to read %s from %s", name, path)
            return None
    if env:
        value = os.environ.get(env)
        if value is None:
            # Names the setting, not the variable: CodeQL treats anything read from a *secret* setting as sensitive
            logger.warning("The environment variable configured for %s is not set", name)
        return value
    return literal


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
        return _resolve_value(
            f"{field} of vault '{self.name}'",
            getattr(self, field),
            getattr(self, f"{field}_env"),
            getattr(self, f"{field}_file"),
        )

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


class ControlScope(BaseModel):
    """Which secrets a policy control applies to; empty lists and null match everything."""

    model_config = _STRICT

    vaults: list[str] = Field(default_factory=list, description="Vault names")
    engines: list[str] = Field(default_factory=list, description="Engine mount paths")
    systems: list[str] = Field(default_factory=list, description="System names")
    severities: list[str] = Field(default_factory=list, description="Expiry profiles (severities)")
    paths: list[str] = Field(
        default_factory=list, description="Glob patterns matched against the full path, vault/engine/path"
    )
    privileged: Optional[bool] = Field(default=None, description="true: only privileged secrets; false: only others")


class MaxRotationAgeRule(BaseModel):
    """Fails a secret whose last rotation (backend update) is older than `days`, or unknown."""

    model_config = _STRICT

    type: Literal["max_rotation_age"]
    days: int = Field(ge=1, description="Maximum age of the last rotation in days")


class NotExpiredRule(BaseModel):
    """Fails a secret whose TTL has passed."""

    model_config = _STRICT

    type: Literal["not_expired"]


class HasOwnerRule(BaseModel):
    """Fails a secret without an effective owner (its own or its system's)."""

    model_config = _STRICT

    type: Literal["has_owner"]


class HasSystemRule(BaseModel):
    """Fails a secret that isn't assigned to a system."""

    model_config = _STRICT

    type: Literal["has_system"]


class RotationConfirmedRule(BaseModel):
    """Fails a secret whose rotation has waited for confirmation longer than the grace period (ADR-021)."""

    model_config = _STRICT

    type: Literal["rotation_confirmed"]


PolicyRule = Annotated[
    Union[MaxRotationAgeRule, NotExpiredRule, HasOwnerRule, HasSystemRule, RotationConfirmedRule],
    Field(discriminator="type"),
]


class ControlThresholds(BaseModel):
    """
    When a control turns amber or red: a number of failing secrets, or a percentage of those in scope.

    Without thresholds, one failing secret is red.
    """

    model_config = _STRICT

    amber: Optional[int] = Field(default=None, ge=1, description="Failing secrets that make the control amber")
    red: Optional[int] = Field(default=None, ge=1, description="Failing secrets that make the control red")
    amber_pct: Optional[float] = Field(default=None, gt=0, le=100, description="Failing percent for amber")
    red_pct: Optional[float] = Field(default=None, gt=0, le=100, description="Failing percent for red")

    @model_validator(mode="after")
    def check_kind_and_order(self) -> "ControlThresholds":
        """Counts or percentages, not both; amber below or at red."""
        counts = self.amber is not None or self.red is not None
        pcts = self.amber_pct is not None or self.red_pct is not None
        if counts and pcts:
            raise ValueError("use either amber/red (counts) or amber_pct/red_pct, not both")
        for amber, red in ((self.amber, self.red), (self.amber_pct, self.red_pct)):
            if amber is not None and red is not None and amber > red:
                raise ValueError("the amber threshold must not be above the red one")
        return self


class PolicyControl(BaseModel):
    """One checkable requirement: a scope, one rule and when it turns amber or red."""

    model_config = _STRICT

    id: str = Field(min_length=1, max_length=64, description="Control id, unique within the policy (e.g. PAM-01)")
    title: str = Field(min_length=1, max_length=300)
    source: Optional[str] = Field(default=None, max_length=500, description="Where the requirement comes from")
    scope: ControlScope = Field(default_factory=ControlScope)
    rule: PolicyRule
    thresholds: ControlThresholds = Field(default_factory=ControlThresholds)


class CompliancePolicy(BaseModel):
    """A set of controls evaluated against the inventory (ADR-019)."""

    model_config = _STRICT

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$", description="Policy id used in URLs, e.g. bank-pam")
    name: str = Field(min_length=1, max_length=200)
    framework: Optional[str] = Field(default=None, max_length=100, description="e.g. PCI DSS, DORA, Internal")
    version: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=2000)
    controls: list[PolicyControl] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_control_ids(self) -> "CompliancePolicy":
        """Control ids identify results, so they must be unique within a policy."""
        ids = [control.id for control in self.controls]
        duplicates = sorted({cid for cid in ids if ids.count(cid) > 1})
        if duplicates:
            raise ValueError(f"policy '{self.id}' has duplicate control id(s): {', '.join(duplicates)}")
        return self


class ComplianceConfig(BaseModel):
    """Compliance evidence settings (#94)."""

    model_config = _STRICT

    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    policies: list[CompliancePolicy] = Field(default_factory=list, description="Compliance policies (ADR-019)")

    @model_validator(mode="after")
    def check_unique_policy_ids(self) -> "ComplianceConfig":
        """Policy ids are used in URLs and snapshots, so they must be unique."""
        ids = [policy.id for policy in self.policies]
        duplicates = sorted({pid for pid in ids if ids.count(pid) > 1})
        if duplicates:
            raise ValueError(f"duplicate compliance policy id(s): {', '.join(duplicates)}")
        return self


ALERT_NAMES = (
    "SecretExpiringSoon",
    "SecretExpired",
    "SecretRotationUnconfirmed",
    "SecretRotated",
    "SecretRotationConfirmed",
    "VaultUnreachable",
    "CompliancePeriodEnded",
    "ComplianceSnapshotCreated",
)
AlertName = Literal[
    "SecretExpiringSoon",
    "SecretExpired",
    "SecretRotationUnconfirmed",
    "SecretRotated",
    "SecretRotationConfirmed",
    "VaultUnreachable",
    "CompliancePeriodEnded",
    "ComplianceSnapshotCreated",
]


class DefaultRoute(BaseModel):
    """A webhook for alerts without an owner: vault health, compliance and unowned secrets (ADR-025)."""

    model_config = _STRICT

    name: str = Field(min_length=1, max_length=100, description="Shown as the receiver in the payload")
    url: Optional[str] = Field(default=None, description="Webhook URL (prefer url_env or url_file: URLs carry tokens)")
    url_env: Optional[str] = Field(default=None, description="Environment variable holding the URL")
    url_file: Optional[str] = Field(default=None, description="File holding the URL")
    signing_secret_env: Optional[str] = Field(
        default=None, description="Environment variable with a Standard Webhooks secret (whsec_...) to sign with"
    )

    @model_validator(mode="after")
    def check_one_source(self) -> "DefaultRoute":
        """Exactly one of url, url_env and url_file; a literal URL must be http(s)."""
        if sum(v is not None for v in (self.url, self.url_env, self.url_file)) != 1:
            raise ValueError(f"default route '{self.name}' needs exactly one of url, url_env, url_file")
        if self.url is not None and not self.url.lower().startswith(("http://", "https://")):
            raise ValueError(f"default route '{self.name}' url must be http:// or https://")
        return self

    def resolve_url(self) -> Optional[str]:
        """The URL from url_file, url_env or url."""
        return _resolve_value(f"default route '{self.name}'", self.url, self.url_env, self.url_file)

    def resolve_signing_secret(self) -> Optional[str]:
        """The signing secret, or None when the route isn't signed."""
        if self.signing_secret_env is None:
            return None
        return _resolve_value(f"default route '{self.name}' signing secret", None, self.signing_secret_env, None)


class AlertingConfig(BaseModel):
    """Webhook alerting (#99, ADR-022, ADR-025)."""

    model_config = _STRICT

    enabled: bool = Field(default=True, description="Send webhooks; nothing is sent without routes")
    events: list[AlertName] = Field(default_factory=lambda: list(ALERT_NAMES), description="Alerts to send")
    repeat_interval: str = Field(
        default="1d", description="How often a still-firing alert is sent again (e.g. '12h', '1d'), or 'off'"
    )
    max_attempts: int = Field(default=5, ge=1, le=20, description="Delivery attempts before giving up")
    default_routes: list[DefaultRoute] = Field(default_factory=list)
    external_url: Optional[str] = Field(
        default=None, description="Chronowarden's own URL, for links in the payload (generatorURL)"
    )

    @field_validator("repeat_interval")
    @classmethod
    def validate_repeat_interval(cls, v: str) -> str:
        """Same format as polling_interval."""
        parse_interval_seconds(v)
        return v

    @property
    def repeat_seconds(self) -> Optional[int]:
        """The repeat interval in seconds, or None when firing alerts aren't repeated."""
        return parse_interval_seconds(self.repeat_interval)

    @model_validator(mode="after")
    def check_unique_route_names(self) -> "AlertingConfig":
        """Route names identify receivers in the payload and the delivery log."""
        names = [route.name for route in self.default_routes]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate default route name(s): {', '.join(duplicates)}")
        return self


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


AuthMode = Literal["oidc", "proxy", "none"]
Role = Literal["admin", "owner", "viewer"]

# Highest first: a user in groups of several roles gets the first one that matches
ROLES: tuple[Role, ...] = ("admin", "owner", "viewer")


class OidcConfig(BaseModel):
    """Built-in login against an OIDC provider: authorization code flow with PKCE (ADR-015)."""

    model_config = _STRICT

    issuer: str = Field(description="Issuer URL; discovery is read from <issuer>/.well-known/openid-configuration")
    client_id: str = Field(min_length=1, description="Client ID registered at the provider")
    client_secret: Optional[str] = Field(default=None, description="Client secret (prefer client_secret_env/_file)")
    client_secret_env: Optional[str] = Field(default=None, description="Environment variable holding the secret")
    client_secret_file: Optional[str] = Field(default=None, description="File holding the client secret")
    redirect_uri: str = Field(
        description="Callback URL registered at the provider, ending in /api/v1/auth/callback "
        "(e.g. https://chronowarden.example.com/api/v1/auth/callback)"
    )
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"], description="Requested scopes")
    groups_claim: str = Field(default="groups", description="ID token claim with the user's groups")
    username_claim: str = Field(default="preferred_username", description="ID token claim with the user name")

    @field_validator("issuer", "redirect_uri")
    @classmethod
    def check_http(cls, v: str) -> str:
        """Both are URLs the browser or the server calls; kept as written, the issuer must match the token's."""
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("must be an http:// or https:// URL")
        return v

    @field_validator("scopes")
    @classmethod
    def check_openid_scope(cls, v: list[str]) -> list[str]:
        """Without `openid` there is no ID token."""
        if "openid" not in v:
            raise ValueError("must include 'openid'")
        return v

    def resolve_client_secret(self) -> Optional[str]:
        """The client secret from client_secret_file, client_secret_env or client_secret; None for public clients."""
        return _resolve_value(
            "the OIDC client secret", self.client_secret, self.client_secret_env, self.client_secret_file
        )


class ProxyConfig(BaseModel):
    """Identity headers set by an authenticating reverse proxy such as oauth2-proxy (ADR-015)."""

    model_config = _STRICT

    trusted_proxies: list[IPvAnyNetwork] = Field(
        min_length=1,
        description="Addresses or CIDRs of the proxy; headers from any other peer are ignored. Checked against the TCP "
        "peer: run uvicorn with --no-proxy-headers (the images do), or X-Forwarded-For could stand in for it",
    )
    user_header: str = Field(default="X-Forwarded-User", description="Header with the user name")
    email_header: str = Field(default="X-Forwarded-Email", description="Header with the email address")
    groups_header: str = Field(default="X-Forwarded-Groups", description="Header with comma-separated groups")
    logout_url: Optional[str] = Field(
        default=None, description="Where the UI sends users to log out (e.g. /oauth2/sign_out)"
    )


class RoleGroups(BaseModel):
    """IdP groups per role; the highest matching role wins (ADR-015)."""

    model_config = _STRICT

    admin: list[str] = Field(default_factory=list, description="Groups whose members can do everything")
    owner: list[str] = Field(default_factory=list, description="Groups whose members act on secrets they own")
    viewer: list[str] = Field(default_factory=list, description="Groups whose members can only read")


class AuthConfig(BaseModel):
    """Authentication for the UI and API (ADR-015, ADR-026)."""

    model_config = _STRICT

    mode: AuthMode = Field(description="'oidc', 'proxy', or 'none' (no login: only on trusted networks)")
    oidc: Optional[OidcConfig] = Field(default=None, description="Required when mode is 'oidc'")
    proxy: Optional[ProxyConfig] = Field(default=None, description="Required when mode is 'proxy'")
    roles: RoleGroups = Field(default_factory=RoleGroups, description="IdP groups mapped to roles")
    default_role: Optional[Role] = Field(
        default=None, description="Role for users in none of the role groups; unset means they get 403"
    )
    session_lifetime: str = Field(default="12h", description="How long a login lasts (e.g. '8h', '1d')")
    token_max_lifetime: str = Field(default="1y", description="Longest expiry an API token may have (e.g. '90d')")

    @field_validator("session_lifetime")
    @classmethod
    def validate_session_lifetime(cls, v: str) -> str:
        """Same format as polling_interval, but never 'off'."""
        if parse_interval_seconds(v) is None:
            raise ValueError("sessions must expire; use a duration such as '12h'")
        return v

    @field_validator("token_max_lifetime")
    @classmethod
    def validate_token_max_lifetime(cls, v: str) -> str:
        """Same format as expiry profiles."""
        parse_duration_to_days(v)
        return v

    @model_validator(mode="after")
    def check_mode_section(self) -> "AuthConfig":
        """The section of the chosen mode must be there."""
        if self.mode == "oidc" and self.oidc is None:
            raise ValueError("mode 'oidc' needs an oidc section")
        if self.mode == "proxy" and self.proxy is None:
            raise ValueError("mode 'proxy' needs a proxy section")
        return self

    @property
    def session_seconds(self) -> int:
        """The session lifetime in seconds."""
        return parse_interval_seconds(self.session_lifetime) or 0

    @property
    def token_max_days(self) -> int:
        """The longest API token expiry in days."""
        return parse_duration_to_days(self.token_max_lifetime)


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
    polling_interval: str = Field(
        default="6h", description="How often the server syncs every vault (e.g. '30m', '6h'), or 'off' (ADR-013)"
    )
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
    manual_sync_cooldown: int = Field(
        default=30, ge=0, description="Seconds before a vault can be synced again on request (0 turns it off)"
    )
    snapshot_min_interval: int = Field(
        default=60, ge=0, description="Seconds between compliance snapshots taken on request (0 turns it off)"
    )
    expiry_profiles: dict[str, ExpiryProfile] = Field(
        default_factory=lambda: {name: ExpiryProfile(**profile) for name, profile in DEFAULT_EXPIRY_PROFILES.items()},
        description="Expiry profiles mapping severity names to rotation periods",
    )
    ui: UiConfig = Field(default_factory=UiConfig, description="Instance-wide UI settings")
    metrics: MetricsConfig = Field(default_factory=MetricsConfig, description="Prometheus metrics (off by default)")
    alerting: AlertingConfig = Field(default_factory=AlertingConfig, description="Webhook alerting (ADR-025)")
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig, description="Compliance evidence settings")
    auth: Optional[AuthConfig] = Field(
        default=None, description="Authentication (ADR-015); the server refuses to start without it"
    )
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Host names Chronowarden answers to (e.g. chronowarden.example.com, *.example.com); "
        "set it to stop DNS rebinding from other web pages",
    )

    @field_validator("polling_interval")
    @classmethod
    def validate_polling_interval(cls, v: str) -> str:
        """Reject intervals the scheduler can't use."""
        parse_interval_seconds(v)
        return v

    @property
    def polling_seconds(self) -> Optional[int]:
        """The polling interval in seconds, or None when the schedule is off."""
        return parse_interval_seconds(self.polling_interval)

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
    def validate_policy_scopes(self) -> "AppConfig":
        """Policy control scopes may only name configured vaults and known severities."""
        vaults = {vault.name for vault in self.vaults}
        severities = {*self.expiry_profiles, "none"}
        for policy in self.compliance.policies:
            for control in policy.controls:
                where = f"policy '{policy.id}' control '{control.id}'"
                unknown = sorted(set(control.scope.vaults) - vaults)
                if unknown:
                    raise ValueError(f"{where} names unknown vault(s): {', '.join(unknown)}")
                unknown = sorted(set(control.scope.severities) - severities)
                if unknown:
                    raise ValueError(f"{where} names unknown severity value(s): {', '.join(unknown)}")
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


def require_auth(config: AppConfig) -> AuthConfig:
    """
    Return the auth settings the server needs before it serves anything (ADR-015).

    Raises:
        ConfigError: If the config has no `auth` section.
    """
    if config.auth is None:
        raise ConfigError(
            "auth: missing; set auth.mode to 'oidc' or 'proxy', or to 'none' if only trusted networks can reach "
            "Chronowarden (see config.example.yaml)"
        )
    if config.auth.mode == "none":
        logger.warning("Authentication is off (auth.mode: none): anyone who reaches Chronowarden is an admin")
    return config.auth


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
