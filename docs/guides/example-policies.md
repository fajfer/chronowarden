<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Example policies

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

!!! danger "Not authoritative"
    These examples are a starting point, not legal or audit advice. They are one reading of public texts, they
    cover only what Chronowarden can measure, and every number below except PCI DSS 8.3.9's 90 days is a value your
    organization sets for itself. Check them with your compliance team and auditor, and keep the policy in your own
    words. The citations were checked on 2026-10-12.

Each example is a complete `compliance.policies` entry you can copy into `config.yaml` (see
[Compliance policies and reports](compliance-policies.md)). The scopes use `privileged` and `severities` only, so
they work on any inventory; narrow them with `vaults`, `engines`, `systems` or `paths` to match yours.

## What no policy here can cover

Chronowarden reads metadata only and stores no access-review state. It cannot evaluate:

- periodic reviews of access rights (PCI DSS 7.2.4, 7.2.5.1; RTS 2024/1774 Art. 21(e)(iv) and Art. 33(e));
- removal of inactive accounts (PCI DSS 8.2.6) or revocation on termination (PCI DSS 8.2.5; RTS Art. 21(e)(iii));
- least privilege and need-to-use assignment (PCI DSS 7.2.2, 7.2.5; RTS Art. 21(e)(ii));
- whether a credential is also hard-coded somewhere (PCI DSS 8.6.2).

For those, keep the evidence in your own process. Half-yearly or yearly [snapshots](compliance-evidence.md) can be
attached as the inventory that a review covered, and each snapshot lists the secrets removed in its period.

## PCI DSS v4.0.1

Source: *PCI DSS Requirements and Testing Procedures, v4.0.1* (June 2024), from the
[PCI SSC Document Library](https://www.pcisecuritystandards.org/document_library/). Requirements that were best
practice until 31 March 2025 are mandatory now.

```yaml
- id: pci-dss-4
  name: PCI DSS v4.0.1 - credentials and keys (example)
  framework: PCI DSS
  version: 4.0.1
  description: >-
    Example only. Rotation periods come from your targeted risk analyses (12.3.1) and cryptoperiods (3.7.4).
  controls:
    - id: "8.6.3"
      title: Application and system account passwords are changed periodically
      source: PCI DSS v4.0.1 req. 8.6.3 (frequency from the targeted risk analysis, req. 12.3.1)
      rule: { type: max_rotation_age, days: 365 }
      thresholds: { amber: 1, red: 5 }
    - id: 8.6.3-priv
      title: Privileged application and system credentials are changed more often
      source: PCI DSS v4.0.1 req. 8.6.3 and 7.2.5 (stricter value from the targeted risk analysis)
      scope: { privileged: true }
      rule: { type: max_rotation_age, days: 90 }
    - id: "8.6.3-applied"
      title: Changed credentials are applied where they are used
      source: PCI DSS v4.0.1 req. 8.6.3 ("upon suspicion or confirmation of compromise")
      rule: { type: rotation_confirmed }
    - id: "3.7.4"
      title: Keys are not used beyond their cryptoperiod
      source: PCI DSS v4.0.1 req. 3.7.4 and 3.7.5
      rule: { type: not_expired }
    - id: "3.6.1"
      title: Every key and credential has a responsible custodian
      source: PCI DSS v4.0.1 req. 3.6.1 (custodians) and 12.5.1 (inventory of in-scope components)
      rule: { type: has_owner }
    - id: "12.5.1"
      title: Every key and credential is mapped to the system it serves
      source: PCI DSS v4.0.1 req. 12.5.1 and 3.6.1.1
      rule: { type: has_system }
      thresholds: { amber_pct: 1, red_pct: 10 }
```

Notes:

- **8.3.9** (90 days) applies only to user passwords that are the sole authentication factor. If Vault holds such
  passwords, add a control with `rule: { type: max_rotation_age, days: 90 }` scoped to them with `paths`.
- **3.7.4** leaves the cryptoperiod to you. With expiry profiles set per key type, `not_expired` enforces it; a
  `max_rotation_age` per key type (scoped by `severities` or `paths`) does the same without profiles.

## DORA and RTS 2024/1774

Sources: Regulation (EU) 2022/2554 ([EUR-Lex](https://eur-lex.europa.eu/eli/reg/2022/2554/oj)) and Commission
Delegated Regulation (EU) 2024/1774 on the ICT risk management framework
([EUR-Lex](https://eur-lex.europa.eu/eli/reg_del/2024/1774/oj)), Title II (full framework).

```yaml
- id: dora-ict
  name: DORA - ICT assets and keys (example)
  framework: DORA
  version: RTS 2024/1774
  description: >-
    Example only. DORA and the RTS leave rotation periods to the entity; the values below are placeholders.
  controls:
    - id: RTS-4.2.b.iv
      title: The owner of every credential is recorded
      source: RTS 2024/1774 Art. 4(2)(b)(iv); DORA Art. 8(1)
      rule: { type: has_owner }
    - id: RTS-4.2.b.v
      title: The business function each credential supports is recorded
      source: RTS 2024/1774 Art. 4(2)(b)(v); DORA Art. 8(1), 8(4)
      rule: { type: has_system }
    - id: RTS-21.c
      title: Privileged and shared credentials are attributable to someone
      source: RTS 2024/1774 Art. 21(c) and 21(e)(ii)
      scope: { privileged: true }
      rule: { type: has_owner }
    - id: RTS-7.1
      title: Keys and credentials are renewed within their lifecycle
      source: RTS 2024/1774 Art. 7(1); DORA Art. 9(4)(d)
      rule: { type: max_rotation_age, days: 365 }
      thresholds: { amber_pct: 1, red_pct: 5 }
    - id: RTS-7.1-priv
      title: Privileged keys and credentials are renewed more often
      source: RTS 2024/1774 Art. 7(1) (period set by the entity)
      scope: { privileged: true }
      rule: { type: max_rotation_age, days: 180 }
    - id: RTS-7.5
      title: Certificates and keys are renewed before they expire
      source: RTS 2024/1774 Art. 7(5)
      rule: { type: not_expired }
    - id: RTS-7.3
      title: Replaced keys and credentials are applied
      source: RTS 2024/1774 Art. 7(3); DORA Art. 9(4)(e)
      rule: { type: rotation_confirmed }
```

Notes:

- DORA Art. 8(1) asks for the documentation of ICT assets to be reviewed "at least yearly"; a yearly
  [reporting cadence](compliance-evidence.md) freezes a snapshot for that review.
- Entities under the **simplified framework** (RTS Title III, Art. 29-41) can use the same controls, citing
  Art. 30(1) for the inventory and Art. 33 for access control; Title III has no separate key-management article.

## KNF: ICT key risk indicator reports

Polish supervised entities report the *Kluczowe wskaźniki ryzyka dla obszaru ICT* to KNF under DORA (the
[list of reporting forms](https://www.knf.gov.pl/knf/pl/komponenty/img/Zestawienie_obowiazkow_i_formularzy_sprawozdawczych_91844.pdf)
gives DORA Art. 50 as the basis):

| Form | Who files | How often |
|---|---|---|
| SPR-PF-26 | Entities with the full ICT risk management framework | Quarterly |
| SPR-PF-27 | Entities with the full ICT risk management framework | Yearly |
| SPR-PF-30 | Entities with the simplified ICT risk management framework | Yearly |

The form templates and their indicators are published only in KNF's CRP portal, so this page doesn't name or map
individual indicators. What Chronowarden can do is gather the credential data on the same cadence:

```yaml
# Reporting cadences matching the KRI forms: close each period to freeze its snapshot and PDF report
compliance:
  reporting:
    cadences:
      - period: quarterly        # SPR-PF-26
        scope: {}
      - period: yearly           # SPR-PF-27 / SPR-PF-30
        scope: {}
```

Together with the DORA example above, each quarterly snapshot then holds: the credentials in scope, which are
privileged, who owns them, which were rotated late, which expired, and which were removed during the quarter.

Rekomendacja D (2013), which set at least yearly reviews of access rights (Rek. 11.4) and formal key management
(Rek. 11.11), was repealed with effect from 17 January 2025 (Uchwała KNF nr 6/2025) because DORA now applies.
Cite DORA and RTS 2024/1774 instead.
