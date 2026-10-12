# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Standard Webhooks signatures (https://www.standardwebhooks.com/), ADR-022."""

import base64
import hashlib
import hmac
import secrets

SECRET_PREFIX = "whsec_"


def generate_secret() -> str:
    """A new signing secret: `whsec_` and 32 random bytes in base64."""
    return SECRET_PREFIX + base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def signature_headers(secret: str, message_id: str, timestamp: int, body: bytes) -> dict[str, str]:
    """
    The `webhook-id`, `webhook-timestamp` and `webhook-signature` headers for one delivery.

    The signature is `v1,` and the base64 HMAC-SHA256 of `{id}.{timestamp}.{body}` keyed with the secret's bytes.
    """
    key = base64.b64decode(secret.removeprefix(SECRET_PREFIX))
    signed = f"{message_id}.{timestamp}.".encode("utf-8") + body
    signature = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("ascii")
    return {"webhook-id": message_id, "webhook-timestamp": str(timestamp), "webhook-signature": f"v1,{signature}"}
