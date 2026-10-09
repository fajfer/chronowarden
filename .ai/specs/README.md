<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Specs

A spec is the plan for a task with 3+ steps: the goal, its scope, and a task list. Each task names the exact
files an agent must read (**Load**), so it can be done with only those files.

## Rules

- File name: `YYYY-MM-DD-slug.md`, copied from [TEMPLATE.md](TEMPLATE.md).
- **Load** lists exact paths (scoped `AGENTS.md`, ADRs, specific source files). Nothing outside the list is
  needed; if it is, fix the list.
- Each task row has its own Load (a subset of, or addition to, the spec's Load), a checkable "Done when", a
  Status (`todo`/`doing`/`done`/`dropped`) and, when done, the Commit.
- If a spec changes a decision, it lists the ADRs affected, and a superseding ADR is written as one of its tasks.
- When all tasks are `done` and Validation passes, move the file to [implemented/](implemented/).

## Open

| Spec | Goal |
|---|---|
| [2026-10-09-per-profile-alert-threshold](2026-10-09-per-profile-alert-threshold.md) | WARNING window per expiry profile instead of fixed 30 days |
| [2026-10-09-honor-enabled-flag-in-sync](2026-10-09-honor-enabled-flag-in-sync.md) | Sync respects `chronowarden_enabled` instead of resetting it |
| [2026-10-09-wire-prometheus-metrics](2026-10-09-wire-prometheus-metrics.md) | Defined-but-unset metrics get producers |
| [2026-10-09-generic-provider-registry](2026-10-09-generic-provider-registry.md) | A second provider can plug in without editing Vault-specific code |
