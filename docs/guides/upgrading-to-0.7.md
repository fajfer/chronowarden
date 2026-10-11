<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Upgrading to 0.7

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

0.7 turns Chronowarden's database from a cache you could delete into a record you must keep.

## Before you upgrade

**Back up `chronowarden.db`.** 0.7 stores data that can't be rebuilt from Vault: system and owner assignments,
rotation confirmations, the audit log and compliance snapshots. Mount the file on a volume (Docker:
`-v $(pwd)/chronowarden.db:/app/chronowarden.db`; Kubernetes: the PVC) and include it in your backups.

## What happens on start

The database is upgraded automatically, one step at a time (`PRAGMA user_version`). A failed step is rolled back
and Chronowarden stops with the reason. A database from a newer release is refused, so going back to 0.6 means
restoring the backup you took before upgrading.

## Breaking changes

- **Prometheus metrics are off by default.** If Prometheus scrapes `/api/v1/metrics`, add to `config.yaml`:

  ```yaml
  metrics:
    enabled: true
  ```

- **Email notification routes are removed.** Existing email routes are deleted by the upgrade; webhook routes stay.
  Built-in webhook alerting arrives in 0.8.

## After you upgrade

Run a sync of each vault. The first sync records every secret once in the audit log ("first seen"), so the history
of each secret starts there.
