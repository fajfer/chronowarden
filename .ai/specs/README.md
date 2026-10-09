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
| [2026-10-09-systems-and-owners](2026-10-09-systems-and-owners.md) | Systems (CMDB URI, asset number, owners) and owners assigned to secrets (#61) |
| [2026-10-09-wire-prometheus-metrics](2026-10-09-wire-prometheus-metrics.md) | Defined-but-unset metrics get producers |
| [2026-10-09-generic-provider-registry](2026-10-09-generic-provider-registry.md) | A second provider can plug in without editing Vault-specific code |

## Implemented

| Spec | Goal |
|---|---|
| [2026-10-09-release-0-6](implemented/2026-10-09-release-0-6.md) | Release 0.6 Foundations: order of work (released as v0.6.0) |
| [2026-10-09-strict-config-validation](implemented/2026-10-09-strict-config-validation.md) | Fail fast on any config error (#12) |
| [2026-10-09-sync-reconnect-first](implemented/2026-10-09-sync-reconnect-first.md) | Sync reconnects a disconnected vault before failing (#59) |
| [2026-10-09-logging](implemented/2026-10-09-logging.md) | Timestamps, no probe noise in access logs (#58) |
| [2026-10-09-instance-ui-settings](implemented/2026-10-09-instance-ui-settings.md) | Vault URLs and runtime default theme (#19, #57) |
| [2026-10-09-per-profile-alert-threshold](implemented/2026-10-09-per-profile-alert-threshold.md) | WARNING window per expiry profile instead of fixed 30 days |
| [2026-10-09-remove-enabled-flag](implemented/2026-10-09-remove-enabled-flag.md) | Remove `enabled` and `PATCH` severity overrides; config is the only source |
| [2026-10-09-remove-deprecation-shims](implemented/2026-10-09-remove-deprecation-shims.md) | Drop pre-1.0 deprecation warnings and legacy config paths (#30) |
