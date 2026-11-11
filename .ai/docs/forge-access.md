<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Forge access for agents

Which credentials an agent uses on each forge, with exactly what permissions, and why. ADR-033 decides which forge
is used for what. Keep this file current: a credential an agent uses must be listed here, and a credential that
isn't listed must not be used. No token value ever goes into the repo, a commit, a log or a chat.

## GitLab: `reszka-org/chronowarden`

A **project access token**, so the agent can't reach other projects and acts as a bot user with its own identity
in the audit events.

| Field | Value | Why |
|---|---|---|
| Created at | Project → Settings → Access tokens (`https://gitlab.com/reszka-org/chronowarden/-/settings/access_tokens`) | project tokens need Premium or Ultimate on GitLab.com; we have Ultimate |
| Name | `claude-code-agent` | shows as the bot user's name on MRs, comments and audit events |
| Role | **Developer** | can push branches, open MRs and issues, comment, run pipelines on its own branches and read the vulnerability report. It **can't merge to protected branches, create protected tags or change settings**, which enforces "no merge or tag without the maintainer's go" |
| Scopes | **`api`**, **`write_repository`** | `api` for `glab` (MRs, issues, pipelines, the security report). Project tokens don't get Git over HTTPS through `api`, so pushing branches needs `write_repository` |
| Not granted | `read_registry`/`write_registry`, `create_runner`, `manage_runner`, `ai_features`, `k8s_proxy`, `self_rotate`, Maintainer/Owner | none are needed; images stay on ghcr (ADR-033) |
| Expiry | 90 days | short enough to limit a leak, long enough not to be a weekly chore; the maintainer rotates it |
| Stored | on the maintainer's workstation only, by `glab auth login --hostname gitlab.com` (glab's config file, mode 0600) | never in the repo, CI variables or the agent's memory |
| Git over HTTPS | remote `https://gitlab.com/reszka-org/chronowarden.git`, with glab as the credential helper | pushes go through the token's Developer role, not the maintainer's SSH key |

**Current token:** created 2026-11-11, expires 2027-02-28; bot user
`project_88817028_bot_7c85545c13d34dcb1cdb66be3c2bc80e`, Developer (checked with the API). Update this line on each
rotation.

**Rotation:** create a new token with the same fields, run `glab auth login` again, revoke the old one, and update
the line above.

## GitHub: `fajfer/chronowarden`

The `gh` CLI, logged in as the maintainer (OAuth token in the system keyring). The agent acts **as the maintainer**
on GitHub, so the "Never merge or tag without the maintainer's go" rule in AGENTS.md is the only control.

| Field | Value |
|---|---|
| Scopes | `repo`, `read:org`, `gist` (as of 2026-11-11) |
| Used for | PRs and CI until the switch (spec task 9); afterwards: releases, advisories, the PR bridge and the mirror's state |
| Known excess | `repo` covers all of the maintainer's repositories, and `gist` isn't used. A fine-grained token limited to this repo would be narrower; this is to be decided by the maintainer |

## Tools

- `glab` for GitLab and `gh` for GitHub. Each command names its forge; don't rely on the git remote to pick one.
- On GitLab the token can't change protected-branch rules, mirrors, policies, tokens or project settings. On
  GitHub the maintainer's token can; agents don't, and leave settings to the maintainer.
