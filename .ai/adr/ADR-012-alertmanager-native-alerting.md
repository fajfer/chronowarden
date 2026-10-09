<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-012: Alertmanager-native alerting

- **Status:** Accepted
- **Date:** 2026-10-09
- **Evidence:** Maintainer decision 2026-10-09; maintainer comment on #61 (owners as routing targets, "as Alertmanager understands it"); issue #71.

## Context

Nothing alerts today: notification routes are stored but `test-route` sends nothing, and the expiry gauges are never set (#71). The README promises "Prometheus Metrics - Built-in monitoring endpoint for alerting" and "better support for routing alerts".

## Decision

Chronowarden doesn't send notifications itself. It exposes metrics at `/api/v1/metrics` that let Prometheus evaluate expiry and lets Alertmanager route the alerts: per-secret series labeled with vault, engine, severity, owner and system (assigned in the compliance milestone, ADR-010). It also ships example alerting rules. Routing (email, Slack, webhooks, silences, deduplication) is Alertmanager's job.

## Consequences

- The #71 spec changes from aggregate gauges by `engine_type` to per-secret series. Series count grows with the number of secrets, so labels stay limited to the identifiers above.
- The owner notification routes (`notification_routes` table, `/owners/{id}/routes`, `test-route`) become redundant. Removing them needs its own spec.
- Deployments without Prometheus get no alerts. That is an accepted trade-off.
- Alert timing depends on the sync schedule (ADR-013).

## Related files

- [`chronowarden/metrics/prometheus.py`](../../chronowarden/metrics/prometheus.py)
- [`chronowarden/api/owners.py`](../../chronowarden/api/owners.py)
- [`chronowarden/models/owner.py`](../../chronowarden/models/owner.py)
