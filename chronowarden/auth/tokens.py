# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Random session IDs and API tokens, stored only as hashes (ADR-026)."""

import hashlib
import secrets

TOKEN_PREFIX = "cwt_"


def new_session_id() -> str:
    """A random session ID for the cookie."""
    return secrets.token_urlsafe(32)


def new_api_token() -> str:
    """A random API token; the prefix makes leaked tokens easy to recognise and scan for."""
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def digest(value: str) -> str:
    """
    SHA-256 of a session ID or token, the only form stored.

    Both are 256 random bits, so a fast hash is enough: there is nothing to guess.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
