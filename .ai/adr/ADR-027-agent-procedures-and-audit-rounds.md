<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# ADR-027: Agent procedures in `.agents/skills`, thin tool wrappers, audit rounds outside the repo

- **Status:** Proposed
- **Date:** 2026-10-31
- **Evidence:** maintainer decisions of 2026-10-29 on the [auditor spec](../specs/2026-10-29-auditor-agent.md) and
  the [live-QA spec](../specs/2026-10-29-live-qa-agent.md); the first round `~/chronowarden-audits/2026-10-18-owasp/`
- **Supersedes:** none

## Context

Agents now do more than follow the router: they audit diffs, modules, security and the AI catalogue, and they will
drive the app in a dev env to check changes live. Each of those is a procedure several sessions must follow the
same way, whatever agent tool runs them. Claude Code reads subagents from `.claude/agents/`, other tools read other
places, and `.claude` is ignored by git today. Audit reports name unfixed security problems, which must not land in
a public repository before the fix does, and repeated audit rounds circle back to findings already decided unless
the decisions are written down.

## Decision

- **Procedures are tool-neutral skills** in `.agents/skills/<name>/` (`SKILL.md` plus references, checklists and
  templates), like `likec4-dsl`. They are written so any agent tool can follow them by reading the files.
- **Tool wrappers are thin.** `.claude/agents/<name>.md` holds only what Claude Code needs to run a skill as a
  subagent (name, description, allowed tools) and points to the skill; it repeats no procedure. Other tools get
  their own wrappers the same way when needed. `.gitignore` tracks `.claude/agents/` and keeps the rest of
  `.claude/` ignored.
- **Audit rounds live outside the repository**, in `~/chronowarden-audits/<date>-<topic>/`: `reports/` (every
  auditor's report, an older one renamed with its date, never overwritten) and `DECISIONS.md` (the state of each
  finding and the history of every loop). Only fixes reach the repository, through PRs; a report or finding text
  is never committed or pasted into a public issue while the finding is open.
- **Auditors only read.** They write one report to the path they are given and change nothing else; reproducing a
  finding is the launching session's or the live-QA agent's job.

## Consequences

- A procedure changes in one place; a wrapper changes only when the tool's needs do.
- A new agent tool needs a wrapper per skill, not a copy of the procedure.
- Audit history isn't versioned with the code and isn't shared with other contributors; the maintainer backs up
  `~/chronowarden-audits/` and moves a closed round's findings into issues if they should be public.
- A session must load the round's `DECISIONS.md` before fixing a finding, so decided or cut behaviour isn't
  brought back.
- The catalogue audit checks `.agents/skills/` and the wrappers along with the AGENTS.md files.

## Related files

- `.agents/skills/` (procedures), `.claude/agents/` (Claude Code wrappers), `.gitignore`
- [auditor spec](../specs/2026-10-29-auditor-agent.md), [live-QA spec](../specs/2026-10-29-live-qa-agent.md)
