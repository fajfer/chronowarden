<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Compliance evidence

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

The **Compliance** tab gives you inventory and evidence for the reviews you run in your own process (a GRC tool,
tickets, a signed spreadsheet). Chronowarden doesn't store the review itself.

## Privileged secrets

Mark a secret privileged with the toggle in its details; Chronowarden writes `chronowarden_privileged: true` to its
Vault metadata, next to your other keys. You can also set that key in Vault yourself; only `true` counts.

## Summaries and tree

**Overview** counts secrets and privileged secrets per vault, engine and system. **Tree** lets you walk vault →
engine → secret, or system → secret, with status counts on every level.

## Snapshots

A snapshot freezes the inventory of a scope (vaults, systems, privileged only): each secret's status, TTL, last
rotation, system with CMDB link and asset number, responsible owners, privileged flag and confirmation state. It is
stored with a SHA-256 of its content and the audit log's newest hash, and can't be changed or deleted. Download it as
JSON (the exact bytes the hash covers) or CSV.

Before freezing, Chronowarden lists the gaps in scope (no owner, no system, expired or no TTL, privileged without an
owner, rotations awaiting confirmation). Fix what you can, or freeze anyway; the snapshot records the inventory as
it is.

## Reporting periods

To report on a fixed rhythm, configure cadences:

```yaml
compliance:
  reporting:
    cadences:
      - period: quarterly
        scope: { privileged_only: true }
      - period: yearly
        scope: {}
```

When a period ends, the Overview asks you to close it; closing freezes a snapshot of the cadence's scope that also
lists secrets removed during the period. A closed period can be corrected with a new snapshot that supersedes the
old one.
