<!--
SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->

# Roadmap Gap Analysis

Analysis of the [README roadmap](README.md#roadmap) against existing issues, PRs,
and current implementation to identify gaps and propose additional tasks.

## Roadmap items

The README lists five roadmap items:

1. RBAC support
2. Support assigning each secret/engine/provider with internal systems
3. Generate automatic reports from Chronowarden for internal systems
4. Better support for routing alerts
5. Support additional backends for public cloud providers and their vaults

---

## Current coverage

### 1. RBAC support

**Status: not planned — no issue or PR exists.**

There is no authentication or authorisation layer in the codebase today.
The FastAPI app exposes every endpoint without any identity check.

### 2. Assigning secrets/engines/providers with internal systems

**Status: partially covered.**

| What exists | Where |
|---|---|
| Owner profiles (name, email) with CRUD API | `chronowarden/api/owners.py`, `chronowarden/models/owner.py` |
| Notification routes per owner (email, webhook) | Same files |
| `chronowarden_owner` custom-metadata field | `architecture/integrations.c4` (design) |

**Gap:** Owners represent *people*, not internal systems (services,
applications, environments). There is no model or API that links a secret,
engine, or vault to an internal system/service. Issue #24 (rotation
confirmation) adds an audit dimension but does not cover system assignment.

### 3. Automatic report generation

**Status: not planned — no issue or PR exists.**

Prometheus metrics are exported (`/metrics`) and can feed Grafana dashboards,
but there is no built-in report generation (PDF, CSV, scheduled email
summaries, compliance snapshots, etc.).

### 4. Better support for routing alerts

**Status: partially covered.**

| What exists | Where |
|---|---|
| Notification route model (email/webhook) | `chronowarden/models/owner.py` |
| `test-route` endpoint (stub — logs only) | `chronowarden/api/owners.py` |
| Prometheus counter `chronowarden_notifications_sent_total` | `chronowarden/metrics/prometheus.py` |

**Gap:** No actual alert dispatching logic exists. The `test_route` endpoint
just logs and returns success. There is no trigger that fires notifications
when a secret enters *warning* or *expired* state. Issue #24 mentions alert
routing in passing but does not cover it comprehensively.

### 5. Additional backends (public cloud vaults)

**Status: not planned — no issue or PR exists.**

The integration layer is tightly coupled to HashiCorp Vault / OpenBao:

- `BaseIntegration` in `chronowarden/integrations/base.py` defines the
  interface.
- `VaultIntegration` is the sole implementation.
- `VaultManager` assumes every backend is a Vault.
- Config models (`VaultConfig`) are Vault-specific (token, AppRole, namespace).

No issue, RFC, or design document exists for AWS Secrets Manager, Azure Key
Vault, GCP Secret Manager, or any other provider.

---

## Proposed additional tasks

The following tasks, broken into small deliverables, would close the gaps
identified above and make each roadmap item achievable incrementally.

### RBAC support

| # | Task | Rationale |
|---|---|---|
| R1 | **Add an authentication middleware (JWT / OIDC)** | Gate every API endpoint behind identity verification. Support external IdPs (Keycloak, Dex, Okta) via OIDC. |
| R2 | **Define a role/permission model and store it in SQLite** | Roles such as `viewer`, `editor`, `admin` with fine-grained permissions (e.g. read secrets, trigger sync, manage owners). |
| R3 | **Enforce authorisation on each API router** | Decorate endpoints with permission checks; return 403 when unauthorised. |
| R4 | **Add a login page and token handling in the frontend** | SvelteKit auth flow: login page, token storage, automatic refresh, redirect on 401. |

### Assigning secrets/engines/providers with internal systems

| # | Task | Rationale |
|---|---|---|
| S1 | **Create an "internal system" entity model and CRUD API** | A new `System` model (name, description, environment, team/owner link) stored in SQLite, exposed via `/api/v1/systems`. |
| S2 | **Link secrets and engines to systems** | Many-to-many relationship so a secret can belong to multiple systems and vice versa. Expose assignment endpoints. |
| S3 | **Add system filter to the secrets list and UI** | Allow filtering the dashboard by system to answer "which secrets does service X depend on?". |
| S4 | **Support `chronowarden_system` custom metadata in Vault** | Optionally read system assignment from Vault metadata during sync, similar to `chronowarden_severity`. |

### Automatic report generation

| # | Task | Rationale |
|---|---|---|
| G1 | **Implement a report data aggregation service** | Compute compliance snapshots: total secrets, expired count, warning count, grouped by severity/vault/system. |
| G2 | **Add CSV/JSON export endpoint** | `GET /api/v1/reports/export?format=csv` for on-demand downloads. |
| G3 | **Add PDF report generation** | Use a lightweight library (e.g. `weasyprint` or `fpdf2`) to produce branded compliance reports. |
| G4 | **Implement scheduled report delivery** | Configurable cron-like schedule that generates and sends reports via existing notification routes (email/webhook). |

### Better support for routing alerts

| # | Task | Rationale |
|---|---|---|
| A1 | **Implement actual email alert delivery** | Use SMTP (configurable in `config.yaml`) to send real emails when a notification route is of type `email`. |
| A2 | **Implement webhook alert delivery** | POST JSON payloads to configured webhook URLs (Slack, Teams, PagerDuty, generic). |
| A3 | **Add alert trigger logic on secret state transitions** | After each sync, compare previous and current status; fire alerts on transitions to `warning` or `expired`. |
| A4 | **Add alert cooldown / de-duplication** | Avoid repeated alerts for the same secret; track last-alerted timestamp per secret per route. |
| A5 | **Support additional route types (Slack, PagerDuty, OpsGenie)** | Extend the `notification_routes.type` enum and add provider-specific formatters. |

### Support additional backends

| # | Task | Rationale |
|---|---|---|
| B1 | **Refactor integration layer into a provider registry** | Rename `VaultManager` to a generic `IntegrationManager` that discovers and loads provider plugins by type. |
| B2 | **Make config models provider-agnostic** | Introduce a `ProviderConfig` base with `type` discriminator so `VaultConfig`, `AwsConfig`, etc. coexist in `config.yaml`. |
| B3 | **Implement AWS Secrets Manager integration** | Read secret metadata and rotation schedules from AWS Secrets Manager using `boto3`. |
| B4 | **Implement Azure Key Vault integration** | Read secret metadata, expiry dates, and rotation policies from Azure Key Vault. |
| B5 | **Implement GCP Secret Manager integration** | Read secret metadata and version information from GCP Secret Manager. |

---

## Summary matrix

| Roadmap item | Existing issue(s) | Coverage | Key gaps |
|---|---|---|---|
| RBAC support | — | None | No auth, no roles, no permissions |
| Internal system assignment | #24 (tangential) | Low | No system entity, no linking model |
| Automatic reports | — | None | No report generation at all |
| Better alert routing | #24 (tangential) | Low | Alert delivery is a stub, no triggers |
| Additional backends | — | None | Vault-only, tightly coupled |
