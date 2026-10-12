# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Refuse cross-site writes and unexpected Host headers (0.7.1, until authentication in 0.9)."""

from collections.abc import Awaitable, Callable
from typing import Optional
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _host_only(host: str) -> str:
    """Host without port, lower-cased (IPv6 brackets kept)."""
    host = host.strip().lower()
    if host.startswith("["):
        return host.split("]")[0] + "]"
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def host_allowed(host: Optional[str], allowed: list[str]) -> bool:
    """Whether a Host header matches `allowed_hosts` (`*` allows all; `*.example.com` allows subdomains)."""
    if "*" in allowed:
        return True
    if not host:
        return False
    name = _host_only(host)
    for pattern in (p.strip().lower() for p in allowed):
        if name == pattern or (pattern.startswith("*.") and name.endswith(pattern[1:])):
            return True
    return False


def cross_site_write(request: Request) -> bool:
    """
    Whether a state-changing request comes from another site's page (CSRF).

    Browsers say where a request comes from with `Sec-Fetch-Site`; older ones only send `Origin`, which must then
    match `Host`. Requests with neither are not from a browser (curl, pipelines) and are allowed.
    """
    if request.method in SAFE_METHODS:
        return False
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        return fetch_site not in ("same-origin", "none")
    origin = request.headers.get("origin")
    if origin is None:
        return False
    return urlsplit(origin).netloc.lower() != request.headers.get("host", "").lower()


async def guard_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]], allowed_hosts: list[str]
) -> Response:
    """
    HTTP middleware body: 400 for a Host outside `allowed_hosts` (DNS rebinding), 403 for cross-site writes.

    Args:
        request: The incoming request.
        call_next: The rest of the app.
        allowed_hosts: Configured `allowed_hosts`.

    Returns:
        The app's response, or the refusal.
    """
    if not host_allowed(request.headers.get("host"), allowed_hosts):
        return JSONResponse({"detail": "Host not allowed; see allowed_hosts in config.yaml"}, status_code=400)
    if cross_site_write(request):
        return JSONResponse({"detail": "Cross-site requests can't change Chronowarden"}, status_code=403)
    return await call_next(request)
