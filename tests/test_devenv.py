# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the dev environment helpers (#78)."""

from pathlib import Path

import pytest
import yaml

from devenv.backends import OPENBAO, VAULT
from devenv.config import HEADER, can_write, write_dev_config
from devenv.runtime import ContainerRuntimeError, detect_runtime

CREDENTIALS = {OPENBAO: ("role-a", "secret-a"), VAULT: ("role-b", "secret-b")}


class TestRuntime:
    def test_prefers_podman(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CHRONOWARDEN_CONTAINER_RUNTIME", raising=False)
        monkeypatch.setattr("devenv.runtime.shutil.which", lambda cli: f"/usr/bin/{cli}")
        assert detect_runtime() == "podman"

    def test_falls_back_to_docker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CHRONOWARDEN_CONTAINER_RUNTIME", raising=False)
        monkeypatch.setattr("devenv.runtime.shutil.which", lambda cli: "/usr/bin/docker" if cli == "docker" else None)
        assert detect_runtime() == "docker"

    def test_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHRONOWARDEN_CONTAINER_RUNTIME", "docker")
        monkeypatch.setattr("devenv.runtime.shutil.which", lambda cli: f"/usr/bin/{cli}")
        assert detect_runtime() == "docker"

    def test_none_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CHRONOWARDEN_CONTAINER_RUNTIME", raising=False)
        monkeypatch.setattr("devenv.runtime.shutil.which", lambda cli: None)
        with pytest.raises(ContainerRuntimeError, match="install podman or docker"):
            detect_runtime()


class TestConfig:
    def test_writes_a_new_config_with_header(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        write_dev_config(path, CREDENTIALS)
        text = path.read_text()
        assert text.startswith(HEADER)
        data = yaml.safe_load(text)
        assert data["auth"] == {"mode": "none"}
        vaults = data["vaults"]
        assert [(v["name"], v["address"], v["role_id"]) for v in vaults] == [
            ("dev-openbao", "http://localhost:8200", "role-a"),
            ("dev-vault", "http://localhost:8201", "role-b"),
        ]

    def test_refuses_a_hand_written_config(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        path.write_text("vaults: []  # mine\n")
        assert not can_write(path)
        with pytest.raises(Exception, match="wasn't written by dev-setup.py"):
            write_dev_config(path, CREDENTIALS)
        assert path.read_text() == "vaults: []  # mine\n"

    def test_rewrites_its_own_config_and_force_replaces_others(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        write_dev_config(path, CREDENTIALS)
        assert can_write(path)
        path.write_text("vaults: []\n")
        write_dev_config(path, CREDENTIALS, force=True)
        assert path.read_text().startswith(HEADER)
