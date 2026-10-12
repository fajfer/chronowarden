<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Compliance policies and PDF reports (0.7.x)

- **Status:** in progress
- **Date:** 2026-10-11
- **Issue:** #97, #98

## Goal

Users define compliance policies in config. The Compliance tab shows, per policy, which controls pass, which secrets
break them, and the trend across snapshots. Every snapshot can be exported as a PDF report. Example policies for KNF
KRI ICT, PCI DSS 4.0 and DORA ship in the docs, clearly marked as non-authoritative.

## Non-goals

- Built-in policy packs (examples only).
- A policy editor in the UI (after authentication, 0.9) and free-form rule expressions.
- Review-based rules (Chronowarden stores no review state).

## Design

**Policies** live in config (`compliance.policies`, strict). A control is a scope selector, one rule from a fixed set,
and RAG thresholds:

```yaml
compliance:
  policies:
    - id: bank-pam
      name: Internal PAM standard
      framework: Internal
      version: "2026.1"
      controls:
        - id: PAM-01
          title: Privileged credentials rotated at least every 90 days
          scope: { privileged: true }          # also: severity, vault, engine, system, path_glob
          rule: { type: max_rotation_age, days: 90 }
          thresholds: { amber: 1, red: 5 }     # failing secrets; or amber_pct / red_pct
```

Rule types: `max_rotation_age`, `not_expired`, `has_owner`, `has_system`, `rotation_confirmed` (no unconfirmed
rotation older than the grace period). Policies are evaluated from the DB and config only; snapshots gain per-policy
results.

**PDF reports** are rendered server-side with **Typst** from a snapshot: cover (instance, period, policy and version,
snapshot hash), summary with RAG, per-control results, failing secrets with their responsible owner (paths and
metadata only, never values), methodology and limitations. PDF/A. `GET /api/v1/compliance/snapshots/{id}/report.pdf`.

**Compliance tab** adds Overview (RAG per policy, trend) and Policies (read-only YAML).

## Scope

`chronowarden/config.py`, `config.example.yaml`, `chronowarden/compliance/`, `chronowarden/api/`, `frontend/`,
`docs/` (examples, with the maintainer), `pyproject.toml`, `architecture/main.c4`,
`README.md`, `CHANGELOG.md`, `.ai/adr/`.

## Load

- [root AGENTS.md](../../AGENTS.md)
- [core](../../chronowarden/AGENTS.md), [api](../../chronowarden/api/AGENTS.md), [frontend](../../frontend/AGENTS.md)
- [ADR-006](../adr/ADR-006-config-source-of-truth.md)
- [compliance evidence spec](implemented/2026-10-11-compliance-evidence.md)

## ADRs affected

New **ADR-019 Compliance policies as config, examples not built in** and **ADR-020 PDF reports with Typst**.

## Tasks

| # | Task | Load | Done when | Status | Commit |
|---|---|---|---|---|---|
| 1 | ADR-019 and ADR-020 accepted; Typst spike (arm64, distroless, PDF/A) | [.ai/adr](../adr/README.md) | Both indexed; spike result in ADR-020 | done | 676bfae |
| 2 | Policy config models and `config.example.yaml` | core | Config tests: valid, unknown rule type, duplicate ids | done | ca8589d |
| 3 | Evaluation engine, `GET /compliance/policies` and `/policies/{id}/evaluation`; snapshots store per-policy results | core, api | Unit tests per rule type and threshold edges | done | ba9bf71, f42d3f6 |
| 4 | Example policies for KNF KRI ICT, PCI DSS 4.0, DORA in the docs, each control citing its source, marked non-authoritative (the maintainer reviews `docs/`) | none | Citations checked; maintainer approved | doing | b41407e (drafted; awaiting the maintainer's review) |
| 5 | Typst PDF renderer from a snapshot with Typst's embedded fonts (ADR-020) | core | Golden test on extracted text; the image smoke test renders a report | done | 931767e |
| 6 | Compliance tab: Overview, Policies, PDF download on Snapshots | frontend | `npm run check` clean; walk-through renders a PDF | done | 1a33b3a |
| 7 | `main.c4`, README, `chronowarden/compliance/AGENTS.md`, CHANGELOG | [architecture](../../architecture/AGENTS.md) | Docs match | done | c44d6a2 |

## Validation

`uv run pytest`, black, ruff, `npm run check`, `check_agents_docs.py`, `docker build` of both targets.
