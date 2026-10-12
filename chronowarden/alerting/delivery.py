# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Deliver queued webhooks with retries and a log (ADR-025)."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from typing import Any, Optional

import requests

from chronowarden.alerting.signing import signature_headers
from chronowarden.metrics.prometheus import NOTIFICATIONS_SENT_TOTAL
from chronowarden.timestamps import utc_timestamp

logger = logging.getLogger("uvicorn.error")

# Seconds before the 2nd, 3rd, 4th and later attempts
BACKOFF_SECONDS = (60, 300, 1800, 7200)
TIMEOUT_SECONDS = 10
WORKER_INTERVAL_SECONDS = 15.0


def _retryable(status_code: Optional[int]) -> bool:
    """Network errors, 429 and 5xx are retried; other answers won't change by retrying."""
    return status_code is None or status_code == 429 or status_code >= 500


def _target(db: Any, config: Any, delivery: dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(url, signing secret, error) for a delivery; the URL is looked up now, never stored with the delivery."""
    if delivery["route_id"] is not None:
        route = db.get_route_target(delivery["route_id"])
        if route is None:
            return None, None, "the route was deleted"
        return route["address"], route["signing_secret"], None
    route = next((r for r in config.alerting.default_routes if r.name == delivery["default_route"]), None)
    if route is None:
        return None, None, "the default route is no longer configured"
    url = route.resolve_url()
    if not url:
        return None, None, "the default route's URL couldn't be read"
    return url, route.resolve_signing_secret(), None


def post(url: str, body: bytes, message_id: str, secret: Optional[str], now: datetime) -> tuple[Optional[int], str]:
    """
    POST one webhook: 10 s timeout, no redirects, signed when the route has a secret.

    Returns:
        (status code or None, error text or ""). Error texts never contain the URL, which may carry a token.
    """
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"Chronowarden/{version('chronowarden')}",
        "webhook-id": message_id,
    }
    if secret:
        headers.update(signature_headers(secret, message_id, int(now.timestamp()), body))
    try:
        response = requests.post(url, data=body, headers=headers, timeout=TIMEOUT_SECONDS, allow_redirects=False)
    except requests.RequestException as exc:
        return None, type(exc).__name__
    if 300 <= response.status_code < 400:
        return response.status_code, f"HTTP {response.status_code}: redirects aren't followed"
    return response.status_code, "" if response.ok else f"HTTP {response.status_code}"


def send(db: Any, config: Any, delivery: dict[str, Any], now: datetime) -> str:
    """
    Attempt one queued delivery and record the outcome.

    Returns:
        `delivered`, `pending` (will be retried) or `failed` (given up).
    """
    url, secret, error = _target(db, config, delivery)
    status_code: Optional[int] = None
    if url is not None:
        status_code, error = post(url, delivery["payload"].encode("utf-8"), f"msg_{delivery['id']}", secret, now)
    attempts = delivery["attempts"] + 1
    next_attempt: Optional[str] = None
    if url is not None and not error:
        outcome = "delivered"
    elif url is not None and _retryable(status_code) and attempts < config.alerting.max_attempts:
        outcome = "pending"
        delay = BACKOFF_SECONDS[min(attempts - 1, len(BACKOFF_SECONDS) - 1)]
        next_attempt = utc_timestamp(now + timedelta(seconds=delay))
    else:
        outcome = "failed"
    db.record_delivery_attempt(delivery["id"], outcome, utc_timestamp(now), next_attempt, status_code, error or None)
    NOTIFICATIONS_SENT_TOTAL.labels(router_type="webhook", status=outcome).inc()
    if outcome != "delivered":
        logger.warning(
            "Webhook %s (%s) to %s: %s, attempt %d, %s",
            delivery["id"],
            delivery["alertname"],
            delivery["receiver"],
            error,
            attempts,
            "will retry" if outcome == "pending" else "giving up",
        )
    return outcome


def deliver_due(db: Any, config: Any, now: Optional[datetime] = None) -> int:
    """Attempt every delivery that is due; returns how many were attempted. Blocking (network I/O)."""
    moment = now or datetime.now(tz=timezone.utc)
    due = db.due_deliveries(utc_timestamp(moment))
    for delivery in due:
        send(db, config, delivery, moment)
    return len(due)


class DeliveryWorker:
    """Works the delivery queue every few seconds in a worker thread."""

    def __init__(self, db: Any, config: Any, interval: float = WORKER_INTERVAL_SECONDS) -> None:
        self._db = db
        self._config = config
        self._interval = interval
        self._task: Optional[asyncio.Task[None]] = None

    def start(self) -> None:
        """Start working the queue (also when alerting is off: queued webhooks still go out)."""
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        """Stop the worker; pending deliveries stay queued for the next start."""
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.to_thread(deliver_due, self._db, self._config)
            except Exception:  # top level of a background job: keep working the queue
                logger.exception("Delivering webhooks failed")
            await asyncio.sleep(self._interval)
