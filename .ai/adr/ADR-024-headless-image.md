<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-024: Headless image without the UI or Typst

- **Status:** Accepted
- **Date:** 2026-10-12
- **Evidence:** maintainer decisions of 2026-10-12 (headless image spec); issue #48
- **Supersedes:** none (extends ADR-008 and ADR-020)

## Context

#48 asks for Chronowarden without the frontend: as a Kubernetes CronJob that syncs and exits (ADR-013), or as an
API-only server. Since 0.7.3 the image also carries Typst (ADR-020), about 77 MiB, which an API-only or CronJob
deployment that never renders PDF reports doesn't need.

## Decision

- A third image target, `headless`, next to `production` (still the default) and `dev` (ADR-008): the same
  distroless, non-root base, without the frontend build and without Typst. CI publishes it as `:<tag>-headless` for
  amd64 and arm64 with the same cosign signature, SLSA provenance and SBOM attestations as the production image.
- Typst becomes the optional `reports` extra (`chronowarden[reports]`); the production and dev images install it
  (ADR-020 is unchanged for them). Without it, `GET /api/v1/compliance/snapshots/{id}/report.pdf` stays in the API
  and answers 501 with a message naming the image that has reports.
- Without a frontend build, paths outside `/api` answer 404 instead of the SPA. `GET /api/v1/info` reports
  `features: {ui, pdf_reports}`.
- The headless image ships with 0.8, together with the one-shot sync.

## Consequences

- `report.py` imports Typst lazily; tests cover both cases.
- Everything else (snapshots, JSON/CSV exports, policies, audit, sync, metrics, webhooks) behaves the same in both
  images.
- A third image to build, sign and attest per release; CI time grows accordingly.

## Related files

- `Dockerfile`, `.github/workflows/docker.yaml`, `pyproject.toml`
- `chronowarden/app.py`, `chronowarden/compliance/report.py`, `chronowarden/api/compliance.py`
