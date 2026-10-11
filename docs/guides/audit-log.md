<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Audit log

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

Every change Chronowarden makes or sees is recorded in an append-only log: assignments, systems and owners, the
privileged flag, rotation confirmations, secrets removed or purged, configuration changes, and changes made directly
in Vault: other teams' metadata keys (with their values), version-cleanup settings and new versions. Secret values
are never read.

Open **Compliance → Audit log** for the whole log, or the **History** of a single secret in its details.

## Tamper evidence

Each event carries the hash of the previous one, so editing or deleting an entry breaks the chain from that point.
The page shows whether the chain is intact and its newest hash; `GET /api/v1/audit/verify` does the same. The
database refuses to update or delete events.

**Export JSONL** downloads the log exactly as stored. Anyone can recompute the chain from it; the recipe is in
`chronowarden/audit/AGENTS.md` in the repository. Compliance snapshots record the newest hash, which proves later
that no events were cut off.

## Revert

System and owner assignments, the privileged flag and rotation confirmations can be reverted from the log. A revert
is a new event; nothing is erased. Changes made in Vault and severity/TTL (which come from `config.yaml`) can't be
reverted from Chronowarden.
