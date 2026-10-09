<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Wire the defined-but-unset Prometheus metrics

- **Status:** draft
- **Date:** 2026-10-09
- **Issue:** #71

## Goal

Every metric in `chronowarden/metrics/prometheus.py` is either set by real code or explicitly marked as reserved,
starting with the secret-expiry gauges the README alerting promise depends on.

## Non-goals

- Notifications (`NOTIFICATIONS_SENT_TOTAL` stays reserved until a notifier exists).
- Dashboards or alert rules.

## Scope

`chronowarden/metrics`, `chronowarden/metadata.py` or `chronowarden/api/sync.py`, `chronowarden/app.py`,
`chronowarden/integrations/vault.py`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [metrics](../../chronowarden/metrics/AGENTS.md)
- [core](../../chronowarden/AGENTS.md)

## ADRs affected

Implements [ADR-012](../adr/ADR-012-alertmanager-native-alerting.md) (Alertmanager-native alerting).

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | Per ADR-012: expose per-secret series (e.g. days remaining, status) labeled with vault, engine, path and severity, refreshed from the cache after each sync; keep or replace the aggregate `SECRETS_*` gauges; ship example Prometheus alert rules | metrics, core, [api](../../chronowarden/api/AGENTS.md) | Test asserts gauge values after a sync of fixture data | todo | |
| 2 | Request middleware sets `API_REQUESTS_TOTAL` and `API_REQUEST_DURATION_SECONDS` with the route template (not the raw path) as `endpoint` | metrics, core | Test asserts a counter delta after a request | todo | |
| 3 | `VAULT_OPERATION_DURATION_SECONDS` around Vault calls in `vault.py` | metrics, [integrations](../../chronowarden/integrations/AGENTS.md) | Test asserts a histogram sample count delta | todo | |
| 4 | Update the metrics table in `chronowarden/metrics/AGENTS.md` | metrics | Table matches code | todo | |

## Validation

`uv run pytest`, then `curl localhost:8000/api/v1/metrics` against a dev vault (`uv run python dev-setup.py`).

## Open questions

- Exact metric names, and whether `secret_path` is a label or hashed (series count).
