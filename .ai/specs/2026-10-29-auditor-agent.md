<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Auditor agent and audit rounds

- **Status:** approved
- **Date:** 2026-10-29
- **Issue:** none

## Goal

Any agent tool can run four kinds of audit on Chronowarden: a diff or PR, security (OWASP), a module in depth, and
drift in the AI catalogue (AGENTS.md, ADRs, specs, router, GitHub issues). Each audit is done by a read-only
auditor that writes one report. Every finding in it is a self-contained work item that the maintainer can decide on
and a subagent can take on without further context. Reports and the decisions about them live outside the public
repository, in `~/chronowarden-audits/`, so unfixed security findings are never published. Audit rounds inside a
working session keep one decisions document, so fixes don't go in circles.

Inspired by Hypersomnia's `auditor` agent and its `audit-rounds` and `audit-green-red` skills (TeamHypersomnia/
Hypersomnia, `.claude/`).

## Non-goals

- Auditors that edit code, run tests or start services: an auditor only reads. Reproducing a finding is the
  launching session's job, or the live-QA agent's ([live QA spec](2026-10-29-live-qa-agent.md)).
- Fixing findings automatically: fixes are dispatched per finding, after the maintainer's call where one is needed.
- HTML reports or dashboards: reports are Markdown.

## Scope

`.agents/skills/audit/` (new: `SKILL.md`, one checklist per audit kind, `finding-template.md`), `.claude/agents/
auditor.md` (thin wrapper), root `AGENTS.md` (router row), `.ai/docs/README.md`.

## Load

- [root AGENTS.md](../../AGENTS.md), [.ai/adr](../adr/README.md), [.ai/specs](README.md),
  [lessons](../lessons.md)
- `.agents/skills/likec4-dsl/SKILL.md` (how a skill is laid out here), `scripts/check_agents_docs.py`

## ADRs affected

New **ADR-027**: agent procedures live in `.agents/skills/` (tool-neutral), `.claude/agents/` holds thin wrappers, and audit rounds live outside the repository in `~/chronowarden-audits/`.

## Design

**Tool-neutral, with thin wrappers** (decided 2026-10-29). The procedure lives in `.agents/skills/audit/SKILL.md`,
which any agent tool can read. `.claude/agents/auditor.md` is the Claude Code subagent: tools `Read`, `Grep`,
`Glob`, `Bash` (read-only commands only: `rg`, `git log/show/diff`, `ls`, `sed -n`, `gh issue/pr view`) and `Write`
only for the report path the prompt names, plus a pointer to the skill's "Auditor" section.

**Kinds and checklists** (one file each under `.agents/skills/audit/checklists/`):

| Kind | Input | Checks |
|---|---|---|
| `diff` | a commit range or PR number | correctness of the change; a test for every behaviour change and a regression test for every fix; AGENTS.md rules (SPDX, no secret values or URLs in logs, exceptions, typing); ADRs it touches; CHANGELOG; docs and architecture model updated |
| `security` | repo or module | OWASP Top 10 mapped to Chronowarden: the ADR-026 permission matrix on every route, metadata-only access (ADR-004), SSRF and webhook delivery, input and body limits, sessions, tokens and cookies, CSRF and Host guard, secrets at rest and in logs, supply chain (pins, workflows) |
| `module` | one module | the code against its scoped AGENTS.md contracts and gotchas, error paths, tests that miss branches, dead code |
| `catalogue` | the repo | every path and link in AGENTS.md files exists; router rows cover every module; scoped files within budget and true to the code; spec Status vs task rows vs commits; ADR Status; GitHub issues and milestones open for finished work; `.ai/lessons.md` entries that should become rules; AI-draft notices waiting for the maintainer |

Each run of a kind is one auditor per scope (a module audit of `api`, `auth` and `alerting` is three auditors in
parallel), launched by the session with the checklist and a "current state" block (what was decided or removed on
purpose, e.g. no backward compatibility before 1.0), so auditors don't flag decided behaviour.

**Finding format** (`finding-template.md`). Every finding is a block a human can decide on and a fixing agent can
act on alone:

```markdown
### F-<round>-<n>: <one-line title>

- **Severity:** critical | high | medium | low | decision (intended behaviour unclear)
- **Complexity:** green (the fix keeps or removes code) | red (adds a field, flag, path, setting, or is a product call)
- **Confidence:** verified (only with the exact command or request and its output in the finding) | likely | uncertain
- **Where:** `path:line` (and other places)
- **What goes wrong:** two or three sentences.
- **Scenario:** concrete inputs or state → wrong result; a command or request when one exists.
- **Fix:** the smallest change; for a red finding, the cheaper variant that cuts something instead, if any.
- **Done when:** the regression test or check that proves the fix (name and assertion).
- **Load:** exact files a fixing agent must read, as in a spec's Load column.
- **Constraints:** ADRs, AGENTS.md rules and **Ask First** items the fix touches.
```

The report starts with a summary table (id, severity, complexity, title) and orders findings most severe first.

**Audit rounds.** Each round is a folder `~/chronowarden-audits/<date>-<topic>/` with `reports/` (every auditor's
report, never overwritten: an older one is renamed with its date) and `DECISIONS.md`: rules against circling, the
state of each finding (open, fixed with PR, accepted, cut, decided otherwise) and the history of every loop. Before
a fix, the session checks in order: is the finding the effect of something cut or decided (then decide openly, don't
bring back a smaller copy); does the fix add complexity (say what); is it the maintainer's call (product, UX, an Ask
First item); can the fix itself break something. A loop is a decision to record, not a verdict.

**When diff audits run.** Before an agent merges its own PR that changes code (not docs-only and not Dependabot),
it runs a `diff` audit of the PR and handles the findings first; otherwise on request.

**Dispatching fixes.** A green finding the maintainer hasn't reserved can go to a subagent with the finding block
as its whole prompt, in its own worktree, ending in a PR. Red and `decision` findings go to the maintainer with a
recommendation. `DECISIONS.md` records the PR.

The first round, `2026-10-18-owasp`, already exists in this format (the Oct 18 OWASP review, with H2, L1 and L2
open).

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 0 | ADR-027 (agent layout) and its index row | [.ai/adr](../adr/README.md) | Accepted by the maintainer; indexed | todo | |
| 1 | `.agents/skills/audit/SKILL.md`: kinds, launching, the "current state" block, rounds, `DECISIONS.md`, dispatching | root, `.agents/skills/likec4-dsl/SKILL.md` | The skill reads standalone; SPDX headers | todo | |
| 2 | Four checklists and `finding-template.md` | root, every scoped AGENTS.md (for the module and catalogue checklists) | Each checklist names the files and ADRs it checks against | todo | |
| 3 | `.claude/agents/auditor.md` wrapper (read-only tools, report path from the prompt) | — | A Claude Code session lists the `auditor` agent | todo | |
| 4 | Router row "Audit a diff, a module, security or the agent docs"; `.ai/docs/README.md` pointer; root **Workflow** step: a diff audit before merging one's own code PR | root | `check_agents_docs.py` passes | todo | |
| 5 | Acceptance: a `catalogue` audit of the repo as the second round; its green findings fixed through PRs | — | Round folder with report and `DECISIONS.md`; the maintainer has the red findings | todo | |

## Validation

`python3 scripts/check_agents_docs.py`; task 5's round exists and every finding follows the template.

## Open questions

Asked and answered 2026-10-29:

1. Diff audits run **before an agent merges its own code PR**, and otherwise on request.
2. A finding is `verified` **only with the exact command or request and its output** in the report.
3. The layout is recorded as **ADR-027** (task 0).
