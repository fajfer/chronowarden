<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Specs

A spec is the plan for a task with 3+ steps: the goal, its scope, and a task list. Each task names the exact
files an agent must read (**Load**), so it can be done with only those files.

## Rules

- File name: `YYYY-MM-DD-slug.md`, copied from [TEMPLATE.md](TEMPLATE.md).
- GitHub issues are the backlog. Write a spec when work starts, and put the issue number in its `Issue` field.
- **Load** lists exact paths (scoped `AGENTS.md`, ADRs, specific source files). Nothing outside the list is
  needed; if it is, fix the list.
- Each task row has its own Load (a subset of, or addition to, the spec's Load), a checkable "Done when", a
  Status (`todo`/`doing`/`done`/`dropped`) and, when done, the Commit.
- If a spec changes a decision, it lists the ADRs affected, and a superseding ADR is written as one of its tasks.
- When all tasks are `done` and Validation passes, move the file to [implemented/](implemented/).

## Open

| Spec | Goal |
|---|---|
| [2026-10-27-access-control](2026-10-27-access-control.md) | #75: OIDC or proxy login, API tokens, admin/owner/viewer roles (0.9) |
| [2026-10-10-release-0-7](2026-10-10-release-0-7.md) | Release 0.7 Compliance evidence, extended scope: order of work |
| [2026-10-10-supply-chain-security](2026-10-10-supply-chain-security.md) | Scorecard 6.8 → ~8.7, SLSA Build L3, cosign, CycloneDX + SPDX SBOMs, fuzzing, signed Releases |
| [2026-10-10-compliance-policies-and-reports](2026-10-10-compliance-policies-and-reports.md) | 0.7.x: policies in config with example YAML, PDF reports with Typst |

## Implemented

| Spec | Goal |
|---|---|
| [2026-10-09-generic-provider-registry](implemented/2026-10-09-generic-provider-registry.md) | #72: providers built by `type:` through a registry, `/providers` API (ADR-011) |
| [2026-10-12-webhook-alerting](implemented/2026-10-12-webhook-alerting.md) | #99: Alertmanager-compatible webhooks to owners and default routes, retries, signing |
| [2026-10-09-wire-prometheus-metrics](implemented/2026-10-09-wire-prometheus-metrics.md) | Defined-but-unset metrics get producers |
| [2026-10-12-headless-image](implemented/2026-10-12-headless-image.md) | #48: a `headless` image without the UI or Typst (API and sync only) |
| [2026-10-12-scheduled-sync](implemented/2026-10-12-scheduled-sync.md) | #74: sync every `polling_interval`, plus `python -m chronowarden sync` for CronJobs (ADR-013) |
| [2026-10-12-audit-followups](implemented/2026-10-12-audit-followups.md) | Mask webhook URLs, audit route changes, cooldowns on manual sync and snapshots |
| [2026-10-11-dev-setup-rework](implemented/2026-10-11-dev-setup-rework.md) | dev-setup.py on podman, testcontainers integration tests in CI (#78) |
| [2026-10-11-compliance-evidence](implemented/2026-10-11-compliance-evidence.md) | Privileged flag in Vault, snapshots with scope and cadences, gap warnings, Compliance tab |
| [2026-10-11-audit-log-and-rotation-confirmation](implemented/2026-10-11-audit-log-and-rotation-confirmation.md) | #24: hash-chained audit log, change history with revert, rotation confirmation |
| [2026-10-11-optional-metrics](implemented/2026-10-11-optional-metrics.md) | Prometheus metrics off by default (ADR-022) |
| [2026-10-09-systems-and-owners](implemented/2026-10-09-systems-and-owners.md) | Systems (CMDB URI, asset number, owners) and owners assigned to secrets (#61) |
| [2026-10-11-release-0-6-3](implemented/2026-10-11-release-0-6-3.md) | Sync merges custom metadata instead of replacing it (released as v0.6.3) |
| [2026-10-10-sveltekit-3](implemented/2026-10-10-sveltekit-3.md) | Frontend on SvelteKit 3 and TypeScript 6 (#79, PR #80) |
| [2026-10-10-release-0-6-2](implemented/2026-10-10-release-0-6-2.md) | Remove Vault passthrough endpoints, urllib3 bump, Sentry/Node/k8s hardening (released as v0.6.2) |
| [2026-10-09-release-0-6-1](implemented/2026-10-09-release-0-6-1.md) | Path traversal fix, `/api` 404, CI image smoke test (released as v0.6.1) |
| [2026-10-09-release-0-6](implemented/2026-10-09-release-0-6.md) | Release 0.6 Foundations: order of work (released as v0.6.0) |
| [2026-10-09-strict-config-validation](implemented/2026-10-09-strict-config-validation.md) | Fail fast on any config error (#12) |
| [2026-10-09-sync-reconnect-first](implemented/2026-10-09-sync-reconnect-first.md) | Sync reconnects a disconnected vault before failing (#59) |
| [2026-10-09-logging](implemented/2026-10-09-logging.md) | Timestamps, no probe noise in access logs (#58) |
| [2026-10-09-instance-ui-settings](implemented/2026-10-09-instance-ui-settings.md) | Vault URLs and runtime default theme (#19, #57) |
| [2026-10-09-per-profile-alert-threshold](implemented/2026-10-09-per-profile-alert-threshold.md) | WARNING window per expiry profile instead of fixed 30 days |
| [2026-10-09-remove-enabled-flag](implemented/2026-10-09-remove-enabled-flag.md) | Remove `enabled` and `PATCH` severity overrides; config is the only source |
| [2026-10-09-remove-deprecation-shims](implemented/2026-10-09-remove-deprecation-shims.md) | Drop pre-1.0 deprecation warnings and legacy config paths (#30) |
