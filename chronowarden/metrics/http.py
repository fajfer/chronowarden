# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Count and time API requests by route template (#71)."""

import time
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from chronowarden.metrics.prometheus import API_REQUEST_DURATION_SECONDS, API_REQUESTS_TOTAL

UNMATCHED = "unmatched"


def endpoint_of(request: Request) -> str:
    """
    The matched route's full template (e.g. `/api/v1/secrets/{secret_id}`), so the label count stays bounded.

    FastAPI keeps an included router's routes without the prefix it was included with (`/api/v1`), so the prefix
    is what the request path has in front of the route's path filled with the request's own parameters.
    """
    route = request.scope.get("route")
    template = getattr(route, "path_format", None)
    if template is None:
        return UNMATCHED
    try:
        concrete = template.format(**request.path_params)
    except (KeyError, IndexError, ValueError):
        return template
    path = request.scope.get("path", "")
    prefix = path[: len(path) - len(concrete)] if concrete and path.endswith(concrete) else ""
    return prefix + template


async def observe_request(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Record `chronowarden_api_requests_total` and `chronowarden_api_request_duration_seconds`."""
    start = time.perf_counter()
    status = 500  # an exception escaping the app is answered with 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        endpoint = endpoint_of(request)
        API_REQUESTS_TOTAL.labels(method=request.method, endpoint=endpoint, status=str(status)).inc()
        API_REQUEST_DURATION_SECONDS.labels(method=request.method, endpoint=endpoint).observe(
            time.perf_counter() - start
        )
