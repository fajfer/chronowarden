<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Third-party licences

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

Chronowarden is licensed under EUPL-1.2. The libraries it uses keep their own licences. The SBOMs attached to every
release list each component with its licence.

This page is about licences that can matter to **whoever builds or forks** Chronowarden, even when they don't
affect the released images. It isn't legal advice: read the licence texts yourself.

## ApexCharts, through flowbite-svelte

- **Where it comes from:** the UI uses `flowbite-svelte`, which depends on `apexcharts` for its chart components.
- **The licence:** since version 5, ApexCharts is under a dual licence, not an open-source one.
  - **Community licence:** free for individuals, non-profits and organisations with less than USD 2 million in
    annual revenue. It doesn't allow sublicensing under different terms.
  - **Commercial licence:** paid; needed by larger organisations.
  - 4.7.0 was the last MIT-licensed release.
- **Chronowarden doesn't ship it.** It doesn't use flowbite's chart components, so the bundler leaves
  `apexcharts` out of the built UI. It's only downloaded into `node_modules` when the frontend is built.
- **It matters if you fork:** say you're an organisation over the revenue threshold, and your fork adds a
  flowbite chart or imports `apexcharts`. Your build then contains it, and you'd need a commercial licence from
  ApexCharts or another charting library.
- **How to check a build:** after `npm run build` in `frontend/`, `grep -rli apexcharts build/` should print
  nothing.
