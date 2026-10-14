<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-022: Built-in webhook alerting, optional Prometheus metrics

- **Status:** Accepted
- **Date:** 2026-10-11
- **Evidence:** maintainer decisions of 2026-10-11
- **Supersedes:** ADR-012

## Context

ADR-012 left all alerting to Prometheus and Alertmanager. The intent was different: Chronowarden should fire alerts
itself, Alertmanager-like, so that a solo admin can be notified in a chat tool through its REST API without running
Alertmanager, while Prometheus users can still scrape metrics if they want.

## Decision

- **Metrics** are optional and **off by default** (`metrics.enabled: false`, written explicitly in
  `config.example.yaml`); when off, `/api/v1/metrics` returns 404. From 0.7.
- **Webhooks** (0.8): Chronowarden sends a webhook when configured events happen: rotation lifecycle (detected,
  unconfirmed after the grace period, confirmed), expiry (warning, expired), vault health (offline, auth failure,
  back online), compliance (period ended, snapshot created).
- Recipients: the secret's **effective owner**, through the owner's **webhook routes** (the existing notification
  routes). Email routes are deleted by the 0.7 migration. The owner-routes removal planned in #77 is superseded.
- Payload: **Alertmanager-compatible JSON**. Delivery: retries with backoff and a delivery log. Optional per-route
  signing following the **Standard Webhooks** spec.
- Until authentication (0.9) anyone who can reach the API can set webhook URLs (SSRF risk); accepted and documented.

## Consequences

- Time-based events (grace period, expiry) need the scheduler (ADR-013), so webhooks ship in 0.8.
- Existing scrapers of `/api/v1/metrics` must enable metrics after upgrading to 0.7 (breaking change).
- Receivers that don't verify signatures ignore the extra headers; chat-tool webhooks work unchanged.

## Later decisions

- ADR-025: alert lifecycle (repeat, resolve), default routes for alerts without an owner, signing secrets
  generated and stored by Chronowarden.

## Related files

- `chronowarden/config.py`, `chronowarden/api/health.py`, `chronowarden/api/owners.py`, `chronowarden/models/owner.py`
