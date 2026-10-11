<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Secrets deleted in Vault

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

When a secret is deleted in Vault, the next sync marks it **removed** instead of showing it forever as an aging,
eventually "expired" secret.

- Removed secrets disappear from the secrets table, the stats and the dashboard. Turn on **Show removed** in the
  secrets table to see them, greyed out with the date they were removed.
- If the secret is created again at the same path, it comes back with its system and owners.
- **Purge** removes a removed secret from Chronowarden for good, together with its assignments; the audit log keeps
  its history. Purge one from its row, or all removed secrets of the current vault/engine filter at once.

Chronowarden only marks secrets after it listed an engine **completely**. If listing fails (for example the token
lost its `list` permission), nothing is marked and a warning is logged, so a permission problem never looks like
mass deletion.
