<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Systems and owners

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

Assign each secret to the business system it belongs to and to the people or teams responsible for it, so you can
see rotation risk per system and know who to ask.

## Systems

A system has a name, a description, a link to its record in your CMDB, an asset number and its own owners. Create
them under **Settings → Systems** or with `POST /api/v1/systems/`.

## Assigning secrets

Open a secret and use the **Assignment** section: pick one system (or "Unassigned") and tick its owners. The API
equivalents are `PUT /api/v1/secrets/{id}/system` and `PUT /api/v1/secrets/{id}/owners`; both replace the whole value.

A secret's **effective owners** are its own owners, or, if it has none, its system's owners. That is who the secret
table, the dashboard and compliance snapshots show as responsible.

## Good to know

- Assignments live only in Chronowarden's database, never in Vault. Back up `chronowarden.db`.
- They follow the secret's path, so they survive a cache rebuild or a secret that is deleted and recreated.
- A system that still has secrets can't be deleted; unassign them first. Deleting an owner removes it everywhere.
- Until authentication arrives in 0.9, anyone who can reach Chronowarden can change assignments; every change is
  recorded in the audit log.
