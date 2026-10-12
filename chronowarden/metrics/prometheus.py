# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Prometheus metrics for Chronowarden."""

from prometheus_client import Counter, Gauge, Histogram

# Secret metrics (#71): refreshed from the cache after every sync while metrics are enabled
_SECRET_LABELS = ["vault", "engine", "secret_path", "severity"]

SECRETS = Gauge(
    "chronowarden_secrets",
    "Secrets still in the backends, by vault and status (ok, warning, expired, no_ttl)",
    ["vault", "status"],
)

SECRET_EXPIRY_TIMESTAMP = Gauge(
    "chronowarden_secret_expiry_timestamp_seconds",
    "When the secret's TTL ends, as Unix time; no series for secrets without a TTL",
    _SECRET_LABELS,
)

SECRET_LAST_ROTATION_TIMESTAMP = Gauge(
    "chronowarden_secret_last_rotation_timestamp_seconds",
    "The backend's last update (rotation) of the secret, as Unix time",
    _SECRET_LABELS,
)

SECRET_CONFIRMATION_OVERDUE = Gauge(
    "chronowarden_secret_confirmation_overdue",
    "1 while the secret's newest version has waited for confirmation past its grace period (ADR-021), else 0",
    _SECRET_LABELS,
)

# API metrics
API_REQUESTS_TOTAL = Counter(
    "chronowarden_api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status"],
)

API_REQUEST_DURATION_SECONDS = Histogram(
    "chronowarden_api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
)

# Vault integration metrics
VAULT_CONNECTIONS_TOTAL = Counter(
    "chronowarden_vault_connections_total",
    "Total number of Vault connection attempts",
    ["status"],
)

VAULT_OPERATIONS_TOTAL = Counter(
    "chronowarden_vault_operations_total",
    "Total number of Vault operations",
    ["operation", "status"],
)

VAULT_OPERATION_DURATION_SECONDS = Histogram(
    "chronowarden_vault_operation_duration_seconds",
    "Vault operation duration in seconds",
    ["operation"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# Notification metrics
NOTIFICATIONS_SENT_TOTAL = Counter(
    "chronowarden_notifications_sent_total",
    "Total number of notifications sent",
    ["router_type", "status"],
)

# Health metrics
INTEGRATION_HEALTH = Gauge(
    "chronowarden_integration_health",
    "Health status of integrations (1=healthy, 0=unhealthy)",
    ["integration"],
)
