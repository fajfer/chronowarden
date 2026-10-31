# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the dev environment helpers (#78)."""

import importlib.util
import json
import socket
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from devenv.backends import OPENBAO, VAULT
from devenv.config import HEADER, can_write, write_dev_config
from devenv.runs import (
    DEFAULT_RUN,
    LABEL,
    RunError,
    RunInfo,
    check_name,
    container_name,
    default_scratch,
    free_port,
    port_free,
    read_run,
    require_free,
)
from devenv.runtime import ContainerRuntimeError, ContainerSpec, Runtime, detect_runtime

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

    def test_start_sets_labels_and_labelled_filters_by_them(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[str, ...]] = []
        runtime = Runtime("podman")
        monkeypatch.setattr(runtime, "_run", lambda *args: calls.append(args) or "a\nb\n")
        runtime.start(ContainerSpec(name="cw-a-vault", image="img", labels={LABEL: "a"}))
        assert calls[-1][-3:] == ("--label", f"{LABEL}=a", "img")
        assert runtime.labelled(LABEL, "a") == ["a", "b"]
        assert ("--filter", f"label={LABEL}=a") == calls[-1][2:4]
        runtime.labelled(LABEL)
        assert calls[-1][3] == f"label={LABEL}"


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


def _load_dev_setup() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dev_setup", Path(__file__).parent.parent / "dev-setup.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRuntime:
    """Containers as name -> labels, with the calls dev-setup.py makes."""

    cli = "fake"

    def __init__(self, containers: dict[str, dict[str, str]]) -> None:
        self.containers = containers
        self.removed: list[str] = []

    def exists(self, name: str) -> bool:
        return name in self.containers

    def labelled(self, key: str, value: str | None = None) -> list[str]:
        return [n for n, labels in self.containers.items() if key in labels and value in (None, labels[key])]

    def label(self, name: str, key: str) -> str:
        return self.containers[name].get(key, "")

    def remove(self, name: str) -> None:
        del self.containers[name]
        self.removed.append(name)


class TestRuns:
    @pytest.mark.parametrize("name", ["dev", "qa-1a2b", "a", "x" * 31])
    def test_accepts_run_names(self, name: str) -> None:
        assert check_name(name) == name

    @pytest.mark.parametrize("name", ["", "-a", "QA", "a_b", "a b", "x" * 32, "../x"])
    def test_rejects_run_names(self, name: str) -> None:
        with pytest.raises(RunError, match="Run name"):
            check_name(name)

    def test_dev_keeps_its_names_other_runs_are_prefixed(self) -> None:
        assert container_name(DEFAULT_RUN, "openbao", "openbao-dev") == "openbao-dev"
        assert container_name("qa-1", "openbao", "openbao-dev") == "cw-qa-1-openbao"

    def test_backend_for_run_publishes_another_port(self) -> None:
        backend = VAULT.for_run("cw-a-vault", 49152)
        assert (backend.container, backend.port, backend.address) == ("cw-a-vault", 8201, "http://localhost:49152")
        assert VAULT.address == "http://localhost:8201"

    def test_free_port_is_free_and_a_bound_one_is_not(self) -> None:
        port = free_port()
        assert port_free(port)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
            sock.listen()
            assert not port_free(port)
            with pytest.raises(RunError, match=f"{port} \\(vault\\)"):
                require_free({"vault": port})

    def test_default_scratch_is_per_run(self) -> None:
        assert default_scratch("a") != default_scratch("b")
        assert default_scratch("a").name == "chronowarden-a"

    def test_run_json_is_private_and_readable_back(self, tmp_path: Path) -> None:
        info = RunInfo(run="a", scratch=tmp_path, config=tmp_path / "config.yaml", urls={"dev-vault": "http://x"})
        path = info.write()
        assert path.stat().st_mode & 0o777 == 0o600
        assert read_run(tmp_path) == json.loads(path.read_text())
        assert read_run(tmp_path / "missing") is None


class TestCleanup:
    def test_removes_only_the_runs_containers(self, tmp_path: Path) -> None:
        dev_setup = _load_dev_setup()
        runtime = FakeRuntime(
            {
                "cw-a-openbao": {LABEL: "a"},
                "cw-a-vault": {LABEL: "a"},
                "cw-b-vault": {LABEL: "b"},
                "openbao-dev": {LABEL: "dev"},
                "unrelated": {},
            }
        )
        assert dev_setup.cleanup(runtime, "a", None) == 0
        assert sorted(runtime.removed) == ["cw-a-openbao", "cw-a-vault"]
        assert sorted(runtime.containers) == ["cw-b-vault", "openbao-dev", "unrelated"]

    def test_dev_also_removes_its_unlabelled_containers(self) -> None:
        dev_setup = _load_dev_setup()
        runtime = FakeRuntime({"openbao-dev": {}, "vault-dev": {LABEL: "dev"}, "cw-a-vault": {LABEL: "a"}})
        dev_setup.cleanup(runtime, DEFAULT_RUN, None)
        assert sorted(runtime.removed) == ["openbao-dev", "vault-dev"]

    def test_removes_a_scratch_dir_it_wrote_and_keeps_others(self, tmp_path: Path) -> None:
        dev_setup = _load_dev_setup()
        ours, theirs = tmp_path / "ours", tmp_path / "theirs"
        ours.mkdir()
        theirs.mkdir()
        RunInfo(run="a", scratch=ours, config=ours / "config.yaml").write()
        (theirs / "notes.txt").write_text("keep")
        assert dev_setup.cleanup(FakeRuntime({}), "a", ours) == 0
        assert not ours.exists()
        assert dev_setup.cleanup(FakeRuntime({}), "a", theirs) == 1
        assert (theirs / "notes.txt").read_text() == "keep"

    def test_lists_runs_by_label(self, capsys: pytest.CaptureFixture[str]) -> None:
        dev_setup = _load_dev_setup()
        runtime = FakeRuntime({"cw-a-vault": {LABEL: "a"}, "cw-a-openbao": {LABEL: "a"}, "unrelated": {}})
        dev_setup.list_runs(runtime)
        assert capsys.readouterr().out == "a: cw-a-openbao, cw-a-vault\n"
