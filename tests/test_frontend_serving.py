# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for serving the SPA: path traversal protection and API 404s."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chronowarden.app import _frontend_file, register_frontend

SECRET = "vault-token-must-not-leak"


@pytest.fixture()
def build_dir(tmp_path: Path) -> Path:
    """Create a fake frontend build with a secret file next to it (outside the build directory)."""
    build = tmp_path / "srv" / "frontend" / "build"
    (build / "_app").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html>index")
    (build / "robots.txt").write_text("User-agent: *")
    (build / "_app" / "start.js").write_text("console.log('app')")
    (tmp_path / "srv" / "config.yaml").write_text(SECRET)
    return build


@pytest.fixture()
def client(build_dir: Path) -> TestClient:
    """Build an app that serves the fake frontend."""
    app = FastAPI()

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    register_frontend(app, build_dir)
    return TestClient(app)


class TestFrontendFile:
    """Tests for the path resolution helper."""

    def test_file_inside_build_dir(self, build_dir: Path) -> None:
        """A real file in the build directory is returned."""
        assert _frontend_file(build_dir, "robots.txt") == (build_dir / "robots.txt").resolve()

    @pytest.mark.parametrize("path", ["../../config.yaml", "../../../srv/config.yaml", "_app/../../../config.yaml"])
    def test_traversal_is_refused(self, build_dir: Path, path: str) -> None:
        """Paths that resolve outside the build directory are refused."""
        assert _frontend_file(build_dir, path) is None

    def test_absolute_path_is_refused(self, build_dir: Path, tmp_path: Path) -> None:
        """An absolute path doesn't escape the build directory either."""
        assert _frontend_file(build_dir, str(tmp_path / "srv" / "config.yaml")) is None

    def test_directory_is_not_a_file(self, build_dir: Path) -> None:
        """Directories are not served as files."""
        assert _frontend_file(build_dir, "_app") is None


class TestServeSpa:
    """HTTP-level tests for the catch-all route."""

    @pytest.mark.parametrize(
        "url",
        [
            "/..%2f..%2fconfig.yaml",
            "/%2e%2e/%2e%2e/config.yaml",
            "/%2e%2e%2f%2e%2e%2fconfig.yaml",
            "/robots.txt%2f..%2f..%2f..%2fconfig.yaml",
        ],
    )
    def test_traversal_returns_index_not_the_file(self, client: TestClient, url: str) -> None:
        """Encoded traversal never returns a file from outside the build directory."""
        response = client.get(url)
        assert SECRET not in response.text
        assert response.text == "<!doctype html>index"

    def test_existing_file_is_served(self, client: TestClient) -> None:
        """Static files from the build directory are served."""
        assert client.get("/robots.txt").text == "User-agent: *"

    def test_client_route_falls_back_to_index(self, client: TestClient) -> None:
        """Unknown non-API paths are client-side routes and get index.html."""
        response = client.get("/secrets")
        assert response.status_code == 200
        assert response.text == "<!doctype html>index"

    @pytest.mark.parametrize("url", ["/api", "/api/v1/nonexistent", "/api/v2/secrets"])
    def test_unknown_api_path_is_404(self, client: TestClient, url: str) -> None:
        """Unknown API paths return 404 JSON instead of the SPA page."""
        response = client.get(url)
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}

    def test_known_api_route_still_works(self, client: TestClient) -> None:
        """Real API routes registered before the catch-all keep working."""
        assert client.get("/api/v1/health").json() == {"status": "healthy"}

    def test_app_assets_are_served(self, client: TestClient) -> None:
        """The /_app mount serves bundled assets."""
        assert client.get("/_app/start.js").text == "console.log('app')"
