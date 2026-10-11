<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-021: Rotation hand-over between the rotating and the applying team

- **Status:** Accepted
- **Date:** 2026-10-11
- **Evidence:** maintainer decisions of 2026-10-11; issues #24, #18
- **Supersedes:** none

## Context

Often one team rotates a secret in Vault and another team applies it in the real environment, by hand today and
automated later. A new version in Vault doesn't prove the environment uses it (#18). Chronowarden sees both sides
(Vault metadata, and who owns the secret) and should make the hand-over visible, then help automate it.

## Decision

- Whether a secret needs confirmation is a `confirmation_required` cascade in `config.yaml` (vault → engine →
  secret, like severity, ADR-006); default not required. A team that trusts its automation turns it off for an engine;
  a stricter manager turns it on.
- A new Vault version of such a secret counts as rotated but shows **awaiting confirmation** until someone confirms
  it was applied, in the UI or through `POST /api/v1/secrets/{id}/confirmations` (for pipelines). The confirmation
  records when it was applied (between the version's creation and now) and, through the API, who confirmed; it
  covers the newest version only.
- The next rotation is max(Vault `updated_time`, applied date) + rotation period.
- An unconfirmed rotation alerts the secret's effective owner (ADR-022): immediately for information, and again after
  the grace period (per expiry profile, with a global default).
- Confirmations are Chronowarden data (ADR-017), recorded and revertible through the audit log (ADR-014).

## Consequences

- The applying team is modeled as the secret's owner (ADR-010); no separate role.
- Automation can close the loop by calling the confirmation API after a deploy; until authentication (0.9) that API is
  open like other writes.
- Gap warnings before snapshots include unconfirmed rotations.

## Related files

- `chronowarden/config.py`, `chronowarden/metadata.py`, `chronowarden/api/secrets.py`, `chronowarden/audit/`
