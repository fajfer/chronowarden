<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# metrics: Prometheus

## Purpose

Defines the Prometheus metrics, which are exposed at `GET /api/v1/metrics` (`chronowarden/api/health.py`, via
`prometheus_client.generate_latest()` on the default registry).

## Files

- `prometheus.py`: all metric objects (module-level, registered on import).
- `__init__.py`: re-exports every metric; import from `chronowarden.metrics`.

## Contracts

Metric names and labels are what `/api/v1/metrics` scrapers see. All are prefixed `chronowarden_`.

| Constant | Type | Labels | Set by |
|---|---|---|---|
| `VAULT_CONNECTIONS_TOTAL` | Counter | `status` (`success`/`failure`) | `integrations/manager.py` |
| `INTEGRATION_HEALTH` | Gauge | `integration` (`vault:<name>`) | `integrations/manager.py` |
| `VAULT_OPERATIONS_TOTAL` | Counter | `operation` (`list_secrets`/`get_metadata`), `status` (`success`/`not_found`) | `api/vault.py` |
| `SECRETS_TOTAL`, `SECRETS_EXPIRING_SOON`, `SECRETS_EXPIRED` | Gauge | `engine_type` | **nothing yet** |
| `API_REQUESTS_TOTAL`, `API_REQUEST_DURATION_SECONDS` | Counter / Histogram | `method`, `endpoint`(, `status`) | **nothing yet** |
| `VAULT_OPERATION_DURATION_SECONDS` | Histogram | `operation` | **nothing yet** |
| `NOTIFICATIONS_SENT_TOTAL` | Counter | `router_type`, `status` | **nothing yet** (no notifier exists) |

## How to

- **Add a metric**: define it in `prometheus.py` next to its group, with a `chronowarden_` name and help text.
  Export it in `__init__.py` (`import` + `__all__`). Set it where the event happens, reusing the
  label values above.
- **Wire an existing metric**: follow
  [the wiring spec](../../.ai/specs/2026-10-09-wire-prometheus-metrics.md).
- **Test**: no existing test asserts metric values yet; the wiring spec defines the first ones.

## Gotchas

- Metrics are module-level objects on the default registry, shared by the whole process (including the test run).
- The README promises "Prometheus Metrics … for alerting", but the expiry gauges are not set yet (see the table
  above).

## Related ADRs

[ADR-009](../../.ai/adr/ADR-009-offline-tolerant-reconnect.md)

## Validate

`uv run pytest tests/test_manager.py tests/test_vault_api.py tests/test_app.py`
