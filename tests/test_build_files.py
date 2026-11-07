# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Checks on the files that build the images (ADR-032)."""

from pathlib import Path

REPO = Path(__file__).parent.parent


def test_docker_and_podman_ignore_the_same_files() -> None:
    """Docker reads only `.dockerignore`; buildah and podman read `.containerignore`. Both must exclude the same."""
    assert (REPO / ".dockerignore").read_text() == (REPO / ".containerignore").read_text()


def test_the_build_file_is_the_containerfile() -> None:
    """One build file at the root; ClusterFuzzLite keeps its own `Dockerfile`, a name its builder requires."""
    assert (REPO / "Containerfile").is_file()
    assert not (REPO / "Dockerfile").exists()
    assert (REPO / ".clusterfuzzlite" / "Dockerfile").is_file()


def test_the_distroless_stages_give_app_to_nonroot() -> None:
    """The database is created in /app; buildah makes a new WORKDIR root's, so its owner is set explicitly."""
    containerfile = (REPO / "Containerfile").read_text()
    for stage in ("headless", "production"):
        body = containerfile.split(f" AS {stage}\n", 1)[1].split("\nFROM ", 1)[0]
        lines = [line for line in body.splitlines() if line and not line.startswith("#")]
        assert lines[:2] == ["COPY --from=backend-builder --chown=65532:65532 /workdir /app", "WORKDIR /app"], stage
