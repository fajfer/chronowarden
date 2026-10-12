# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Regression (0.7.1): other web pages can't make an operator's browser change Chronowarden."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from chronowarden.app import app
from chronowarden.config import AppConfig
from chronowarden.request_guard import host_allowed

client = TestClient(app)  # no lifespan: the guard runs before any route
URL = "/api/v1/audit/events/1/revert"  # a body-less POST a plain HTML form could send


@pytest.mark.parametrize(
    "headers",
    [
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
        {"Origin": "https://evil.example"},
        {"Origin": "http://testserver.evil.example"},
    ],
)
def test_cross_site_writes_are_refused(headers: dict[str, str]) -> None:
    assert client.post(URL, headers=headers).status_code == 403


@pytest.mark.parametrize(
    "headers",
    [
        {},  # curl, pipelines
        {"Sec-Fetch-Site": "same-origin", "Origin": "http://localhost:5173"},  # the UI, also behind the dev proxy
        {"Sec-Fetch-Site": "none"},  # typed into the address bar
        {"Origin": "http://testserver"},  # same origin, older browser
    ],
)
def test_same_origin_and_non_browser_writes_pass_the_guard(headers: dict[str, str]) -> None:
    assert client.post(URL, headers=headers).status_code not in (400, 403)


def test_reads_are_never_refused_for_their_origin() -> None:
    assert client.get("/api/v1/health", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


def test_unlisted_host_is_refused() -> None:
    with patch("chronowarden.app.app_config", AppConfig(allowed_hosts=["chronowarden.example.com"])):
        assert client.get("/api/v1/health").status_code == 400
        assert client.get("/api/v1/health", headers={"Host": "chronowarden.example.com:8000"}).status_code == 200


@pytest.mark.parametrize(
    "host,allowed,expected",
    [
        ("anything", ["*"], True),
        ("Chronowarden.Example.com:443", ["chronowarden.example.com"], True),
        ("a.example.com", ["*.example.com"], True),
        ("example.com.evil.net", ["*.example.com"], False),
        ("rebinding.attacker.net", ["chronowarden.example.com"], False),
        (None, ["chronowarden.example.com"], False),
        ("[::1]:8000", ["[::1]"], True),
    ],
)
def test_host_allowed(host: str | None, allowed: list[str], expected: bool) -> None:
    assert host_allowed(host, allowed) is expected
