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

## What is exposed

| Metric | Labels | Meaning |
|---|---|---|
| `chronowarden_secrets` | `vault`, `status` | Secrets still in the backends per status (`ok`, `warning`, `expired`, `no_ttl`) |
| `chronowarden_secret_expiry_timestamp_seconds` | `vault`, `engine`, `secret_path`, `severity` | When the secret's TTL ends (Unix time); no series without a TTL |
| `chronowarden_secret_last_rotation_timestamp_seconds` | same | The backend's last update of the secret |
| `chronowarden_secret_confirmation_overdue` | same | 1 while a rotation waits for [confirmation](rotation-confirmation.md) past its grace period |
| `chronowarden_api_requests_total`, `chronowarden_api_request_duration_seconds` | `method`, `endpoint`, `status` | API requests by route template, e.g. `/api/v1/secrets/{secret_id}` |
| `chronowarden_vault_operations_total`, `chronowarden_vault_operation_duration_seconds` | `operation`, `status` | Calls to Vault/OpenBao (`list_secrets`, `read_metadata`, `write_metadata`, `health`, `list_mounts`) |
| `chronowarden_vault_connections_total`, `chronowarden_integration_health` | `status` / `integration` | Connection attempts and whether each vault is connected |

The secret series are refreshed at startup and after every sync (manual, scheduled or one-shot), so their
freshness follows `polling_interval`. They carry secret paths: anyone who can scrape `/api/v1/metrics` sees them.

## Example alert rules

A starting point for Prometheus; tune the windows to your expiry profiles.

```yaml
groups:
  - name: chronowarden
    rules:
      - alert: SecretExpired
        expr: chronowarden_secret_expiry_timestamp_seconds < time()
        for: 1h
        labels: { severity: critical }
        annotations:
          summary: "{{ $labels.vault }}/{{ $labels.engine }}/{{ $labels.secret_path }} is past its rotation date"
      - alert: SecretExpiresSoon
        expr: chronowarden_secret_expiry_timestamp_seconds - time() < 14 * 86400
        for: 1h
        labels: { severity: warning }
        annotations:
          summary: "{{ $labels.secret_path }} must be rotated within 14 days"
      - alert: SecretRotationUnconfirmed
        expr: chronowarden_secret_confirmation_overdue == 1
        for: 1h
        labels: { severity: warning }
        annotations:
          summary: "The rotation of {{ $labels.secret_path }} wasn't confirmed as applied"
      - alert: ChronowardenVaultDown
        expr: chronowarden_integration_health == 0
        for: 15m
        labels: { severity: warning }
        annotations:
          summary: "Chronowarden can't reach {{ $labels.integration }}"
```
