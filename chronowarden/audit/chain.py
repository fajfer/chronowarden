# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Hash chaining of audit events: each event's hash covers its fields and the previous event's hash."""

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any, NamedTuple, Optional

GENESIS_HASH = "0" * 64

# The stored fields an event's hash covers, in addition to prev_hash
HASHED_FIELDS = (
    "id",
    "timestamp",
    "source",
    "actor",
    "event_type",
    "subject",
    "vault_name",
    "engine_id",
    "secret_path",
    "before",
    "after",
    "prev_hash",
)


def canonical_json(value: Any) -> str:
    """Serialize deterministically: sorted keys, no insignificant whitespace, UTF-8 kept as is."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_hash(event: Mapping[str, Any]) -> str:
    """
    Compute an event's hash.

    Args:
        event: The stored event; `before`/`after` are the stored JSON text, not parsed objects.

    Returns:
        Hex SHA-256 of the canonical JSON of `HASHED_FIELDS`.
    """
    return hashlib.sha256(canonical_json({key: event.get(key) for key in HASHED_FIELDS}).encode("utf-8")).hexdigest()


class ChainStatus(NamedTuple):
    """Result of verifying the audit log."""

    valid: bool
    events: int
    head_hash: str
    first_invalid_id: Optional[int] = None
    reason: Optional[str] = None


def verify_chain(events: Iterable[Mapping[str, Any]]) -> ChainStatus:
    """
    Walk the events in id order and check every link and hash.

    Edited, inserted or deleted rows break the chain at the first affected event. Removing the newest rows can't be
    detected here; snapshots record the head hash for that.

    Args:
        events: Stored events ordered by id.

    Returns:
        Whether the chain is intact, how many events it has, its head hash, and the first broken event if any.
    """
    previous_hash = GENESIS_HASH
    previous_id = 0
    count = 0
    for event in events:
        count += 1
        if event["id"] != previous_id + 1:
            return ChainStatus(False, count, previous_hash, event["id"], f"expected id {previous_id + 1}")
        if event["prev_hash"] != previous_hash:
            return ChainStatus(False, count, previous_hash, event["id"], "prev_hash doesn't match the previous event")
        if event_hash(event) != event["hash"]:
            return ChainStatus(False, count, previous_hash, event["id"], "hash doesn't match the event's content")
        previous_hash, previous_id = event["hash"], event["id"]
    return ChainStatus(True, count, previous_hash)
