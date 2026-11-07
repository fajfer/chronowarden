<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-029: Webhooks only reach public addresses unless allowed

- **Status:** Proposed
- **Date:** 2026-11-07
- **Evidence:** maintainer decisions of 2026-10-29 and 2026-11-07
- **Supersedes:** ADR-022

## Context

ADR-022 accepted that whoever can set a webhook URL can make Chronowarden send requests to any address it can
reach, including internal services and cloud metadata endpoints. Since 0.9 only owners and admins can set routes
(ADR-026), but an owner is not necessarily trusted with the server's network position. Self-hosted receivers on a
private network (a chat server, a ticketing system) are a real use case and must keep working.

## Decision

ADR-022 stands, except for its accepted risk on webhook URLs:

- **Metrics** are optional and **off by default** (`metrics.enabled: false`); when off, `/api/v1/metrics` returns
  404.
- **Webhooks** are sent for the configured events, to the secret's effective owner through the owner's webhook
  routes, with an **Alertmanager-compatible JSON** payload, retries with backoff, a delivery log and optional
  **Standard Webhooks** signing. ADR-025 governs the alert lifecycle and default routes.
- **Target check on every send:** the host of a webhook URL (owner routes and `alerting.default_routes`) is
  resolved, and the request is refused unless every resolved address is globally routable. Refused: loopback,
  private (RFC 1918, `fc00::/7`), link-local (`169.254.0.0/16`, `fe80::/10`, which holds the cloud metadata
  endpoints), shared (`100.64.0.0/10`), unspecified, multicast and reserved ranges, and IPv4-mapped IPv6 forms of
  them.
- **The request goes to the checked address**, so a DNS answer that changes between check and connect (rebinding)
  can't reach a refused address. Redirects stay unfollowed.
- **Allowlist:** `alerting.allowed_networks` (a list of CIDRs, empty by default) lets private targets through, for
  self-hosted receivers. Link-local ranges can't be allowed.
- **The same check runs when a route is created or updated** and on the route test endpoint, so a refused target is
  reported at once. The check at send time is the one that counts.
- A refused send is a failed delivery that isn't retried. Its log line and delivery error name the reason and the
  route, never the URL (webhook URLs carry tokens, ADR-025).

## Consequences

- **Breaking:** a route to a receiver on a private network stops delivering until its network is in
  `alerting.allowed_networks`; the upgrade notes say so.
- The dev environment's webhook receiver listens on `127.0.0.1`, so the config written by `dev-setup.py` allows
  `127.0.0.1/32`.
- With an HTTP(S) proxy in the environment, the proxy makes the connection; the check still applies to the URL's
  host as Chronowarden resolves it, but egress rules belong on the proxy too.
- Every new outbound request made from user-supplied input must go through the same check.

## Related files

- `chronowarden/alerting/delivery.py`, `chronowarden/config.py`, `chronowarden/models/owner.py`,
  `chronowarden/api/owners.py`, `devenv/config.py`, `config.example.yaml`, `docs/guides/webhooks.md`
