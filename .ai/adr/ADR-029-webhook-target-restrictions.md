<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-029: Admins can restrict where webhooks go

- **Status:** Accepted
- **Date:** 2026-11-07
- **Evidence:** maintainer decisions of 2026-10-29 and 2026-11-07
- **Supersedes:** ADR-022

## Context

ADR-022 accepted that whoever can set a webhook URL can make Chronowarden send requests to any address the server
can reach. Since 0.9 only owners and admins can set routes (ADR-026), but an owner isn't necessarily trusted with
the server's network position: with a route and its test endpoint, an owner can probe which internal hosts and
ports answer, and send a POST to internal services that act on any request.

The impact is limited by how webhooks are sent: always a POST with Chronowarden's own JSON body, no redirects
followed, and the response body never read. That also rules out reading cloud metadata, which needs a GET or a PUT,
or a special header. Many deployments are internal or air-gapped, where every receiver is on a private address, so
blocking address ranges by default would break them. A fixed list of forbidden ranges would also need upkeep.

## Decision

ADR-022 stands, except for its accepted risk on webhook URLs:

- **Metrics** are optional and **off by default** (`metrics.enabled: false`); when off, `/api/v1/metrics` returns
  404.
- **Webhooks** are sent for the configured events, to the secret's effective owner through the owner's webhook
  routes, with an **Alertmanager-compatible JSON** payload, retries with backoff, a delivery log and optional
  **Standard Webhooks** signing. ADR-025 governs the alert lifecycle and default routes.
- **Opt-in allowlist:** `alerting.allowed_networks`, a list of CIDRs, is not set by default, and then webhooks may
  go to any address, as before. When it is set, a webhook is sent only if every address its host resolves to is in
  one of those networks. There is no built-in list of forbidden ranges.
- When the allowlist is set, **the request goes to the address that was checked**, so a DNS answer that changes
  between check and connect can't get around it. Redirects stay unfollowed.
- The check runs on every send, and also when a route is created or updated and on the route test endpoint, so a
  target outside the allowlist is reported at once.
- A refused send is a failed delivery that isn't retried. Its log line and delivery error name the reason and the
  route, never the URL (webhook URLs carry tokens, ADR-025).

## Consequences

- Nothing changes for existing deployments; an admin who doesn't want owners to reach the internal network sets
  `alerting.allowed_networks`.
- The decision about where the server may send requests belongs to the admin, in config, not to owners through the
  API.
- With an HTTP(S) proxy in the environment, the proxy makes the connection; egress rules belong on the proxy too.
- Every new outbound request made from user-supplied input must go through the same check.

## Related files

- `chronowarden/alerting/delivery.py`, `chronowarden/config.py`, `chronowarden/models/owner.py`,
  `chronowarden/api/owners.py`, `config.example.yaml`, `docs/guides/webhooks.md`
