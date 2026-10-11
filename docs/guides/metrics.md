<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Prometheus metrics

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

Metrics are off by default since 0.7. To let Prometheus scrape `/api/v1/metrics`:

```yaml
metrics:
  enabled: true
```

While disabled, the endpoint answers `404`. The Kubernetes example in `deploy/kubernetes/deployment.yaml` shows
the scrape annotations to uncomment.
