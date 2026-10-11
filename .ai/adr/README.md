<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Architecture Decision Records

Decisions that future work must respect. Read an ADR only when the Task Router, a scoped `AGENTS.md` or a spec links to it.

## Rules

- One decision per file: `ADR-NNN-slug.md`, numbered sequentially, copied from [TEMPLATE.md](TEMPLATE.md).
- Status: `Proposed`, `Accepted`, `Accepted (retroactive)`, `Superseded by ADR-MMM`, `Deprecated`.
- Retroactive ADRs record decisions already visible in the code. Their date is that of the commit where the decision first appears, and they cite the evidence.
- Supersede, don't rewrite: a changed decision gets a new ADR, and the old one only gets its status changed to `Superseded by ADR-MMM`.
- Add every ADR to the index below.

## Index

| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-001](ADR-001-eupl-and-spdx-headers.md) | EUPL-1.2 licence with SPDX headers | Accepted (retroactive) | 2025-02-20 |
| [ADR-002](ADR-002-architecture-as-code-likec4.md) | Architecture as code in LikeC4 | Accepted (retroactive) | 2025-02-20 |
| [ADR-003](ADR-003-pluggable-integrations-vault-first.md) | Pluggable secret-backend integrations, Vault first | Accepted (retroactive) | 2026-02-07 |
| [ADR-004](ADR-004-metadata-only-access.md) | Metadata-only access to secret backends | Accepted (retroactive) | 2026-02-07 |
| [ADR-005](ADR-005-sqlite-metadata-cache.md) | SQLite as the local metadata cache | Superseded by ADR-017 | 2026-02-07 |
| [ADR-006](ADR-006-config-source-of-truth.md) | Config is the source of truth for severity | Accepted (retroactive) | 2026-02-08 |
| [ADR-007](ADR-007-sveltekit-spa-served-by-fastapi.md) | SvelteKit SPA served by FastAPI, API under /api/v1 | Accepted (retroactive) | 2026-02-07 |
| [ADR-008](ADR-008-container-and-deployment-targets.md) | Distroless image; Compose and bare Kubernetes manifests | Accepted (retroactive) | 2026-02-09 |
| [ADR-009](ADR-009-offline-tolerant-reconnect.md) | Start with offline vaults and reconnect in the background | Accepted (retroactive) | 2026-03-18 |
| [ADR-010](ADR-010-owners-systems-and-permissions.md) | Owners and systems assigned to secrets, editable without RBAC for now | Accepted | 2026-10-09 |
| [ADR-011](ADR-011-provider-registry.md) | Generic provider registry | Proposed | 2026-10-09 |
| [ADR-012](ADR-012-alertmanager-native-alerting.md) | Alertmanager-native alerting | Superseded by ADR-022 | 2026-10-09 |
| [ADR-013](ADR-013-in-process-and-headless-sync.md) | Scheduled sync in-process, plus a headless one-shot mode | Accepted | 2026-10-09 |
| [ADR-014](ADR-014-rotation-confirmation-and-audit-log.md) | Rotation confirmation, audit log and change history | Accepted | 2026-10-11 |
| [ADR-015](ADR-015-authentication.md) | Authentication for UI and API | Proposed | 2026-10-09 |
| [ADR-016](ADR-016-stability-policy-for-1-0.md) | What 1.0 guarantees | Proposed | 2026-10-09 |
| [ADR-017](ADR-017-sqlite-holds-assignments.md) | SQLite holds assignments that can't be rebuilt from the backends | Accepted | 2026-10-11 |
| [ADR-018](ADR-018-release-integrity.md) | Release integrity with SLSA Build L3, cosign and SBOMs | Accepted | 2026-10-11 |
| [ADR-019](ADR-019-compliance-policies-as-config.md) | Compliance policies as config, with examples instead of built-in packs | Accepted | 2026-10-11 |
| [ADR-020](ADR-020-pdf-reports-with-typst.md) | PDF reports with Typst | Proposed | 2026-10-11 |
| [ADR-021](ADR-021-rotation-handover.md) | Rotation hand-over between the rotating and the applying team | Accepted | 2026-10-11 |
| [ADR-022](ADR-022-webhooks-and-optional-metrics.md) | Built-in webhook alerting, optional Prometheus metrics | Accepted | 2026-10-11 |
