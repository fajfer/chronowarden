<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# metrics: Prometheus

## Purpose

Defines the Prometheus metrics, which are exposed at `GET /api/v1/metrics` (`chronowarden/api/health.py`, via
`prometheus_client.generate_latest()` on the default registry) **only when `metrics.enabled: true`**; otherwise the
endpoint returns 404 (off by default since 0.7, ADR-022). Metrics are still recorded either way.

## Files

- `prometheus.py`: all metric objects (module-level, registered on import).
- `__init__.py`: re-exports every metric; import from `chronowarden.metrics`.

## Contracts

Metric names and labels are what `/api/v1/metrics` scrapers see. All are prefixed `chronowarden_`.

| Constant | Name | Type | Labels | Set by |
|---|---|---|---|---|
| `SECRETS` | `chronowarden_secrets` | Gauge | `vault`, `status` | `refresh.py` |
| `SECRET_EXPIRY_TIMESTAMP` | `chronowarden_secret_expiry_timestamp_seconds` | Gauge | `vault`, `engine`, `secret_path`, `severity` | `refresh.py` (no series without a TTL) |
| `SECRET_LAST_ROTATION_TIMESTAMP` | `chronowarden_secret_last_rotation_timestamp_seconds` | Gauge | same | `refresh.py` |
| `SECRET_CONFIRMATION_OVERDUE` | `chronowarden_secret_confirmation_overdue` | Gauge | same | `refresh.py` |
| `API_REQUESTS_TOTAL`, `API_REQUEST_DURATION_SECONDS` | `chronowarden_api_request*` | Counter / Histogram | `method`, `endpoint` (route template), `status` | `http.py` (middleware in `app.py`) |
| `VAULT_OPERATIONS_TOTAL`, `VAULT_OPERATION_DURATION_SECONDS` | `chronowarden_vault_operation*` | Counter / Histogram | `operation`, `status` (`success`/`not_found`/`forbidden`/`error`) | `backend.py` around hvac calls in `integrations/vault.py` |
| `VAULT_CONNECTIONS_TOTAL` | `chronowarden_vault_connections_total` | Counter | `status` | `integrations/manager.py` |
| `INTEGRATION_HEALTH` | `chronowarden_integration_health` | Gauge | `integration` (`vault:<name>`) | `integrations/manager.py` |
| `NOTIFICATIONS_SENT_TOTAL` | `chronowarden_notifications_sent_total` | Counter | `router_type`, `status` | **reserved** for webhooks (#99) |

- `refresh_secret_metrics(db, config)` runs at startup and after every `sync_vault_now` (API, schedule, one-shot,
  reconnect), only while `metrics.enabled`; it clears and refills the secret series, so removed secrets disappear.
- Per-secret labels carry the full path (maintainer decision 2026-10-12); series count = number of secrets.

## How to

- **Add a metric**: define it in `prometheus.py` next to its group, with a `chronowarden_` name and help text.
  Export it in `__init__.py` (`import` + `__all__`). Set it where the event happens, reusing the
  label values above.
- **Test**: read values with `prometheus_client.REGISTRY.get_sample_value(name, labels)`; compare deltas, since the
  registry is shared by the whole test run (`tests/test_metrics.py`).

## Gotchas

- Metrics are module-level objects on the default registry, shared by the whole process (including the test run).
- `endpoint` is rebuilt as prefix + route template (`http.endpoint_of`): FastAPI keeps an included router's paths
  without the `/api/v1` it was included with. Paths no route matched are `unmatched`.

## Related ADRs

[ADR-022](../../.ai/adr/ADR-022-webhooks-and-optional-metrics.md) (optional metrics; supersedes ADR-012),
[ADR-009](../../.ai/adr/ADR-009-offline-tolerant-reconnect.md)

## Validate

`uv run pytest tests/test_metrics.py tests/test_manager.py tests/test_vault_api.py tests/test_app.py`
