<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Risks when you fork or redistribute

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

Chronowarden is licensed under EUPL-1.2. The components it builds on keep their own licences, and the SBOMs attached
to every release list them. Some of those licences put conditions on **who** may use them. Those conditions are met
by the Chronowarden project itself, but may not be met by an organisation that forks or redistributes it.

This page lists those risks. It isn't legal advice: read the licence texts and decide for your organisation.

## ApexCharts: free below USD 2 million revenue

- **Where it comes from:** the UI is built with `flowbite-svelte`, whose chart components use `apexcharts`.
- **The licence:** since version 5, ApexCharts is under a dual licence, not an open-source one.
  - **Community licence:** free for individuals, non-profits, educators and organisations with less than
    USD 2 million in annual revenue. Modification and redistribution are allowed with attribution; sublicensing
    under different terms is not.
  - **Commercial licence:** paid, and required for organisations at or above that revenue.
  - 4.7.0 was the last MIT-licensed release.
- **The Chronowarden project** is non-commercial and qualifies for the Community licence, so the UI may use these
  charts.
- **If your organisation is at or above the threshold** and your build contains ApexCharts, you need a commercial
  licence from ApexCharts. The alternatives are to replace the charts or pin ApexCharts 4.7.0.
- **How to check a build:** after `npm run build` in `frontend/`, run `grep -rli apexcharts build/`. Any output
  means ApexCharts is in what you ship. (The image SBOMs don't list the UI's npm packages yet.)
