# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the health and info endpoints."""

from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.api.health import router
from chronowarden.config import AppConfig


def _build_client() -> TestClient:
    """Build a TestClient for the health router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


class TestInfoEndpoint:
    """Tests for GET /api/v1/info."""

    def test_info_returns_default_theme(self) -> None:
        """The instance default theme is exposed for the frontend (#57)."""
        config = AppConfig.model_validate({"ui": {"default_theme": "bison"}, "auth": {"mode": "none"}})
        with patch("chronowarden.app.app_config", config):
            response = _build_client().get("/api/v1/info")

        assert response.status_code == 200
        body = response.json()
        assert body["default_theme"] == "bison"
        assert body["auth_mode"] == "none", "the login page needs the mode before anyone logs in"
        assert set(body) == {"name", "version", "docs", "default_theme", "auth_mode", "features"}

    def test_features_say_what_this_image_has(self, tmp_path: Path) -> None:
        """ADR-024: the headless image has neither the UI nor PDF reports."""
        with (
            patch("chronowarden.app.app_config", AppConfig()),
            patch("chronowarden.app._FRONTEND_DIR", tmp_path / "missing"),
            patch("chronowarden.api.health.reports_available", return_value=False),
        ):
            features = _build_client().get("/api/v1/info").json()["features"]
        assert features == {"ui": False, "pdf_reports": False}


class TestMetricsEndpoint:
    """GET /api/v1/metrics is served only when metrics.enabled is set (ADR-022)."""

    def test_disabled_by_default_is_404(self) -> None:
        with patch("chronowarden.app.app_config", AppConfig()):
            response = _build_client().get("/api/v1/metrics")
        assert response.status_code == 404
        assert "metrics.enabled" in response.json()["detail"]

    def test_enabled_serves_prometheus_text(self) -> None:
        config = AppConfig.model_validate({"metrics": {"enabled": True}})
        with patch("chronowarden.app.app_config", config):
            response = _build_client().get("/api/v1/metrics")
        assert response.status_code == 200
        assert "chronowarden_" in response.text
