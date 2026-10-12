<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Compliance policies and reports

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

A **policy** is a set of controls that Chronowarden checks against your inventory. Each control turns green, amber
or red, and every snapshot freezes the results, so you get a trend and a PDF report you can hand to an auditor.

Policies are your own interpretation of the rules you follow. Chronowarden ships no built-in regulation packs; the
[example policies](example-policies.md) are a starting point.

## Defining a policy

Policies live in `config.yaml` under `compliance.policies` and are validated strictly at startup, like the rest
of the config. Restart Chronowarden after changing them; the change is recorded in the audit log.

```yaml
compliance:
  policies:
    - id: bank-pam                    # lowercase letters, digits, - and _; used in URLs
      name: Internal PAM standard
      framework: Internal             # optional
      version: "2026.1"               # optional
      controls:
        - id: PAM-01
          title: Privileged credentials rotated at least every 90 days
          source: PAM standard, section 4.2   # optional: where the requirement comes from
          scope: { privileged: true }
          rule: { type: max_rotation_age, days: 90 }
          thresholds: { amber: 1, red: 5 }
```

### Scope

A control applies to the secrets that match **all** the selectors you set. Empty lists and a missing `privileged`
match everything.

| Selector | Matches |
|---|---|
| `vaults` | Vault names from `vaults:` |
| `engines` | Engine mount paths |
| `systems` | System names (an unassigned secret never matches) |
| `severities` | Expiry profiles, or `none` |
| `paths` | Glob patterns on the full path `vault/engine/path`, e.g. `prod/*/db/*` |
| `privileged` | `true`: only privileged secrets; `false`: only the others |

Secrets removed from the backend are never evaluated.

### Rules

Each control has exactly one rule:

| Rule | A secret fails when |
|---|---|
| `max_rotation_age` (`days`) | its last rotation (the backend's last update) is older than `days`, or unknown |
| `not_expired` | its TTL has passed (status Overdue) |
| `has_owner` | it has no owner, neither its own nor its system's |
| `has_system` | it isn't assigned to a system |
| `rotation_confirmed` | its newest version has waited for [confirmation](rotation-confirmation.md) longer than the grace period |

Chronowarden stores no access-review state, so a requirement like "review access rights every year" can't be a
rule. Keep that evidence in your review process; the snapshots give it the inventory.

### Thresholds

`thresholds` say when a control turns amber or red, either by the number of failing secrets (`amber`, `red`) or by
their share of the secrets in scope (`amber_pct`, `red_pct`). Use one kind per control.

- Without thresholds, a single failing secret makes the control red.
- A control with no secrets in scope is green; its "In scope" count shows 0.
- A policy's status is its worst control.

## Results and trend

**Compliance → Overview** shows every policy with its status and the number of green, amber and red controls.
Open a policy to see each control, how many secrets it covers, and which secrets fail, with their owners.

Each snapshot freezes the results of every policy configured at that moment, together with the policy and control
definitions. The squares on the right of a policy are its status in each snapshot, oldest first. Changing a policy
later doesn't change what earlier snapshots say.

**Compliance → Policies** shows each policy as configured (read-only; editing in the UI comes with authentication).

The same data is in the API: `GET /api/v1/compliance/policies` and `GET /api/v1/compliance/policies/{id}/evaluation`.

## PDF reports

Every snapshot has a **PDF** link in **Compliance → Snapshots**
(`GET /api/v1/compliance/snapshots/{id}/report.pdf`). The report is rendered from the snapshot alone, as PDF/A for
archiving, and contains:

- a cover with the snapshot's period or label, scope, SHA-256 and the audit log head;
- a summary of every policy and the inventory by status;
- per policy, each control with its requirement, source, counts and status, and the failing secrets with owners;
- methodology and limitations.

The report shows secret paths and owner names, never secret values. Treat it as confidential as the instance
itself. To prove a report matches the snapshot, compare the SHA-256 on its cover with that of the snapshot's JSON
export.
