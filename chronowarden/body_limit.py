# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Refuse oversized request bodies before they are buffered and parsed."""

from fastapi import HTTPException, status
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# The API takes small JSON bodies; anything bigger is a mistake or an attack
MAX_BODY_BYTES = 1024 * 1024
TOO_LARGE = "Request body too large"


class BodyLimitMiddleware:
    """
    ASGI middleware: 413 for a body over `max_bytes`.

    A `Content-Length` over the limit is refused before the app runs; a chunked body is counted as it is read and
    refused once it crosses the limit, so it is never buffered whole.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = Headers(scope=scope).get("content-length")
        if length is not None and (not length.isdigit() or int(length) > self.max_bytes):
            await JSONResponse({"detail": TOO_LARGE}, status_code=status.HTTP_413_CONTENT_TOO_LARGE)(
                scope, receive, send
            )
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=TOO_LARGE)
            return message

        await self.app(scope, limited_receive, send)
