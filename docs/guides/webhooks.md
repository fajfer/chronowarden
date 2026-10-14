<!--
SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->
# Webhook alerts

!!! warning "AI-generated draft"
    This page was drafted by an AI assistant (Claude Code) and hasn't been reviewed by the maintainer yet.
    Check it against the README and the behaviour you see before relying on it.

Chronowarden sends alerts itself, so you can get them in a chat tool without running Alertmanager. The body is
Alertmanager's webhook JSON, so receivers built for Alertmanager work unchanged.

## Who gets what

| Alert | Fires when | Kind |
|---|---|---|
| `SecretExpiringSoon` | a secret enters its warning window | repeats, resolves |
| `SecretExpired` | a secret passes its rotation date | repeats, resolves |
| `SecretRotationUnconfirmed` | a rotation waits for [confirmation](rotation-confirmation.md) past its grace period | repeats, resolves |
| `SecretRotated` | sync sees a new version | once |
| `SecretRotationConfirmed` | someone confirms a rotation as applied | once |
| `VaultUnreachable` | a vault is offline or authentication fails | repeats, resolves |
| `CompliancePeriodEnded` | a reporting period ends and isn't closed yet | once |
| `ComplianceSnapshotCreated` | a snapshot is taken | once |

- A secret's alerts go to the webhook routes of its **effective owners** (its own, or its system's). Add routes in
  **Settings → Owners → Webhook routes**.
- Vault and compliance alerts, and alerts of secrets whose owners have no routes, go to the **default routes** in
  `config.yaml`.
- An alert that keeps firing is sent again every `repeat_interval` (default one day), and once more as `resolved`
  when it ends. Alerts are evaluated after every sync, so their timing follows `polling_interval`.

```yaml
alerting:
  repeat_interval: 1d
  # events: [SecretExpired, VaultUnreachable]   # only these; default: all
  default_routes:
    - name: platform-team
      url_env: PLATFORM_WEBHOOK_URL               # or url_file, or url
      signing_secret_env: PLATFORM_WEBHOOK_SECRET  # optional
```

## Payload

```json
{
  "version": "4",
  "status": "firing",
  "receiver": "owner:alice",
  "groupLabels": {"alertname": "SecretExpired"},
  "commonLabels": {"alertname": "SecretExpired", "vault": "prod", "engine": "apps", "secret_path": "db",
                   "severity": "critical", "system": "Billing", "owners": "Alice"},
  "commonAnnotations": {"summary": "prod/apps/db is past its rotation date (2026-10-01)"},
  "externalURL": "https://chronowarden.example.com",
  "alerts": [{"status": "firing", "labels": {"...": "..."}, "annotations": {"...": "..."},
              "startsAt": "2026-10-02T06:00:00.000000Z", "endsAt": "0001-01-01T00:00:00Z",
              "generatorURL": "https://chronowarden.example.com/compliance", "fingerprint": "…"}]
}
```

Payloads hold secret paths, owner and system names and dates; never secret values.

## Delivery

Each webhook is a `POST` with a 10-second timeout. Redirects aren't followed. Network errors, `429` and `5xx`
answers are retried after 1 minute, 5 minutes, 30 minutes and 2 hours, up to `max_attempts` (default 5); other
answers fail at once. **Settings → Webhooks** shows what is firing and every delivery with its last answer, and
**Send test** on a route posts a test alert right away.

## Signing

Turn on **Sign** for a route to get a [Standard Webhooks](https://www.standardwebhooks.com/) secret
(`whsec_…`). It is shown once; store it in the receiver. Each delivery then carries `webhook-id`,
`webhook-timestamp` and `webhook-signature` headers. To verify in Python:

```python
import base64, hashlib, hmac

def verify(secret: str, headers: dict[str, str], body: bytes) -> bool:
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed = f"{headers['webhook-id']}.{headers['webhook-timestamp']}.".encode() + body
    expected = "v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return any(hmac.compare_digest(expected, s) for s in headers["webhook-signature"].split())
```

Also reject timestamps more than a few minutes old. **New secret** replaces the secret; **Stop signing** sends
unsigned webhooks again. Both are recorded in the audit log, without the secret.

## Security

- Until authentication arrives (0.9), anyone who can reach Chronowarden can add webhook routes, so it can be made to
  POST to addresses on your network. Run it on a trusted network or behind an authenticating proxy.
- Webhook URLs usually carry a token. Chronowarden shows only their scheme and host and never logs them; the
  database holds them and the signing secrets, so protect and back up `chronowarden.db` like the config.
