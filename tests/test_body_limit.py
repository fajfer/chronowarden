# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Regression: oversized request bodies are refused with 413 before they are buffered."""

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from chronowarden.app import app
from chronowarden.body_limit import MAX_BODY_BYTES, BodyLimitMiddleware


class Echo(BaseModel):
    """Any JSON body."""

    value: str


def _client(max_bytes: int = 100) -> TestClient:
    bare = FastAPI()

    @bare.post("/echo")
    def echo(body: Echo) -> Echo:
        return body

    bare.add_middleware(BodyLimitMiddleware, max_bytes=max_bytes)
    return TestClient(bare)


def _chunks(total: int, size: int = 16) -> Iterator[bytes]:
    yield b'{"value": "'
    for _ in range(total // size):
        yield b"x" * size
    yield b'"}'


def test_small_bodies_pass() -> None:
    response = _client().post("/echo", json={"value": "ok"})
    assert response.status_code == 200
    assert response.json() == {"value": "ok"}


def test_oversized_content_length_is_413() -> None:
    response = _client().post("/echo", json={"value": "x" * 200})
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large"}


def test_invalid_content_length_is_413() -> None:
    response = _client().post("/echo", content=b'{"value": "ok"}', headers={"Content-Length": "abc"})
    assert response.status_code == 413


def test_oversized_chunked_body_is_413() -> None:
    """No Content-Length: counted while it is read, refused once it crosses the limit."""
    response = _client().post("/echo", content=_chunks(1000), headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_chunked_body_under_the_limit_passes() -> None:
    response = _client().post("/echo", content=_chunks(32), headers={"Content-Type": "application/json"})
    assert response.status_code == 200


def test_the_app_refuses_oversized_bodies() -> None:
    """Wired into the real app: refused before authentication or validation see it."""
    response = TestClient(app).post("/api/v1/systems/", content=b"x" * (MAX_BODY_BYTES + 1))
    assert response.status_code == 413
