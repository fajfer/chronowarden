<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Rotation confirmation

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

A new secret version in Vault doesn't prove the application uses it yet. Where one team rotates secrets and another
applies them, Chronowarden can wait for confirmation that a rotation was applied.

## Turning it on

Set `confirmation_required` for a vault, an engine or a single secret in `config.yaml` (the most specific wins;
default off):

```yaml
confirmation_grace: "7d"          # how long a rotation may stay unconfirmed
vaults:
  - name: production
    confirmation_required: true
    engines:
      - name: ci-tokens
        confirmation_required: false   # rotated and applied by trusted automation
```

## Confirming

When a new version appears, the secret shows **Awaiting confirmation**, and **Confirmation overdue** after the
grace period. Open the secret and use **Confirm applied** with the date it was applied, which may lie in the past.
Pipelines can call `POST /api/v1/secrets/{id}/confirmations` with `{"applied_at": "..."}` and an owner or admin API
token; the confirmation records the token's name as `token:<name>`.

The next rotation is due one rotation period after the later of the Vault update and the applied date. A
confirmation covers only the newest version, and a mistaken one can be reverted from the history.
