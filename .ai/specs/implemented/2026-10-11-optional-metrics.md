<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Optional Prometheus metrics, off by default

- **Status:** implemented
- **Date:** 2026-10-11
- **Issue:** #96

## Goal

Prometheus metrics are an opt-in feature: `metrics.enabled` in config, `false` by default and written explicitly in
`config.example.yaml`. When off, `/api/v1/metrics` returns 404. Part of ADR-022.

## Non-goals

- Wiring the unset metrics (#71) or webhooks (0.8).

## Scope

`chronowarden/config.py`, `config.example.yaml`, `chronowarden/api/health.py`, `README.md`, `deploy/`, `CHANGELOG.md`.

## Load

- [root AGENTS.md](../../../AGENTS.md)
- [metrics](../../../chronowarden/metrics/AGENTS.md), [core](../../../chronowarden/AGENTS.md),
  [api](../../../chronowarden/api/AGENTS.md), [deploy](../../../deploy/AGENTS.md)

## ADRs affected

[ADR-022](../../adr/ADR-022-webhooks-and-optional-metrics.md) (metrics half).

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | `MetricsConfig` (`enabled: bool = False`) in `config.py`; `metrics:` block in `config.example.yaml` with `enabled: false` and a comment | core | Config tests | done | 409f05d |
| 2 | `/api/v1/metrics` returns 404 when disabled; the quiet-paths log filter still applies | api, metrics | Tests for on/off | done | 409f05d |
| 3 | README (feature list, endpoints); Kubernetes and Compose examples with metrics off and a commented `metrics.enabled: true` + scrape annotation; CHANGELOG breaking-change entry | deploy | Docs match | done | 409f05d |

## Validation

`uv run pytest`, black, ruff, `check_agents_docs.py`.
