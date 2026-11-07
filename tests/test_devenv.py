# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the dev environment helpers (#78)."""

import importlib.util
import json
import os
import re
import signal
import socket
import stat
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest
import requests
import yaml

from chronowarden.alerting.delivery import post
from chronowarden.config import load_config
from chronowarden.database import Database
from devenv import keycloak
from devenv.backends import OPENBAO, POLICY, VAULT
from devenv.config import HEADER, can_write, write_dev_config
from devenv.processes import spawn, started_at, stop, wait_http, wait_listening
from devenv.receiver import make_server
from devenv.runs import (
    DEFAULT_RUN,
    LABEL,
    SCRATCH_LABEL,
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
from devenv.seed import OWNED_SECRETS, OWNER_EMAIL, OWNER_GROUP, seed_database

CREDENTIALS = {OPENBAO: ("role-a", "secret-a"), VAULT: ("role-b", "secret-b")}


class TestConfigMode:
    def test_the_dev_config_is_owner_only(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        path.touch()
        path.chmod(0o644)
        path.write_text(HEADER)
        write_dev_config(path, CREDENTIALS)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


class TestPolicy:
    def test_dev_policy_is_the_readme_policy(self) -> None:
        """The dev AppRole gets what users grant, so a narrower dev policy can't hide or fake permission errors."""
        readme = (Path(__file__).parent.parent / "README.md").read_text()
        section = readme.split("## Vault Permissions", 1)[1]
        block = re.search(r"```hcl\n(.*?)```", section, re.DOTALL)
        assert block is not None

        def rules(hcl: str) -> list[str]:
            return [line.strip() for line in hcl.splitlines() if line.strip() and not line.strip().startswith("#")]

        assert rules(POLICY) == rules(block.group(1))


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

    def start(self, spec: ContainerSpec) -> None:
        raise ContainerRuntimeError(f"cannot start {spec.name}")


class TestRuns:
    @pytest.mark.parametrize("name", ["dev", "qa-1a2b", "a", "x" * 31])
    def test_accepts_run_names(self, name: str) -> None:
        assert check_name(name) == name

    @pytest.mark.parametrize("name", ["", "-a", "QA", "a_b", "a b", "x" * 32, "../x", "a\n"])
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

    def test_a_port_picked_twice_is_refused(self) -> None:
        port = free_port()
        with pytest.raises(RunError, match=f"Port {port} picked for both receiver and app"):
            require_free({"receiver": port, "app": port})

    def test_default_scratch_is_per_run(self) -> None:
        assert default_scratch("a") != default_scratch("b")
        assert default_scratch("a").name == "chronowarden-a"

    def test_run_json_is_private_and_readable_back(self, tmp_path: Path) -> None:
        info = RunInfo(run="a", scratch=tmp_path, config=tmp_path / "config.yaml", urls={"dev-vault": "http://x"})
        path = info.write()
        assert path.stat().st_mode & 0o777 == 0o600
        assert read_run(tmp_path) == json.loads(path.read_text())
        assert read_run(tmp_path / "missing") is None

    def test_read_run_rejects_what_isnt_a_run(self, tmp_path: Path) -> None:
        (tmp_path / "run.json").write_text("[]")
        assert read_run(tmp_path) is None
        (tmp_path / "run.json").write_text('{"run": "a", "pids": []}')
        assert read_run(tmp_path) is None
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        RunInfo(run="a", scratch=elsewhere, config=elsewhere / "config.yaml").write()
        (tmp_path / "run.json").unlink()
        (tmp_path / "run.json").symlink_to(elsewhere / "run.json")
        assert read_run(tmp_path) is None

    def test_record_process_stores_its_start_time(self, tmp_path: Path) -> None:
        info = RunInfo(run="a", scratch=tmp_path, config=tmp_path / "config.yaml")
        info.record_process("app", os.getpid())
        assert read_run(tmp_path)["pids"] == {"app": {"pid": os.getpid(), "started": started_at(os.getpid())}}


class TestCleanup:
    @pytest.fixture(autouse=True)
    def _default_scratch_in_tmp(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("devenv.runs.tempfile.gettempdir", lambda: str(tmp_path))

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

    def test_finds_a_custom_scratch_dir_from_the_container_labels(self, tmp_path: Path) -> None:
        dev_setup = _load_dev_setup()
        custom = tmp_path / "custom"
        custom.mkdir()
        RunInfo(run="a", scratch=custom, config=custom / "config.yaml").write()
        runtime = FakeRuntime({"cw-a-vault": {LABEL: "a", SCRATCH_LABEL: str(custom)}})
        assert dev_setup.cleanup(runtime, "a", None) == 0
        assert not custom.exists() and runtime.removed == ["cw-a-vault"]

    def test_refuses_a_scratch_dir_of_another_run(self, tmp_path: Path) -> None:
        dev_setup = _load_dev_setup()
        RunInfo(run="a", scratch=tmp_path, config=tmp_path / "config.yaml").write()
        runtime = FakeRuntime({"cw-b-vault": {LABEL: "b"}})
        assert dev_setup.cleanup(runtime, "b", tmp_path) == 1
        assert (tmp_path / "run.json").exists() and runtime.removed == []

    def test_removes_an_empty_scratch_dir(self, tmp_path: Path) -> None:
        dev_setup = _load_dev_setup()
        empty = tmp_path / "empty"
        empty.mkdir()
        assert dev_setup.cleanup(FakeRuntime({}), "a", empty) == 0
        assert not empty.exists()

    def test_a_failed_start_leaves_a_run_json_for_cleanup(self, tmp_path: Path) -> None:
        dev_setup = _load_dev_setup()
        scratch = tmp_path / "scratch"
        with pytest.raises(ContainerRuntimeError, match="cannot start"):
            dev_setup.setup(FakeRuntime({}), "a", scratch, tmp_path / "unused.yaml", False)
        assert read_run(scratch)["run"] == "a"
        assert dev_setup.cleanup(FakeRuntime({}), "a", scratch) == 0
        assert not scratch.exists()

    def test_lists_runs_by_label(self, capsys: pytest.CaptureFixture[str]) -> None:
        dev_setup = _load_dev_setup()
        runtime = FakeRuntime({"cw-a-vault": {LABEL: "a"}, "cw-a-openbao": {LABEL: "a"}, "unrelated": {}})
        dev_setup.list_runs(runtime)
        assert capsys.readouterr().out == "a: cw-a-openbao, cw-a-vault\n"


class RecordingRuntime(FakeRuntime):
    """A runtime whose containers start: records each spec."""

    def __init__(self) -> None:
        super().__init__({})
        self.started: list[ContainerSpec] = []

    def start(self, spec: ContainerSpec) -> None:
        self.started.append(spec)
        self.containers[spec.name] = dict(spec.labels)


class TestSetup:
    @pytest.fixture
    def dev_setup(self, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
        """dev-setup.py with the vaults faked: no network, no real ports."""
        module = _load_dev_setup()
        monkeypatch.setattr(module, "_wait_ready", lambda backend, token: object())
        monkeypatch.setattr(module, "seed", lambda client: None)
        monkeypatch.setattr(module, "setup_approle", lambda client: ("role", "secret"))
        monkeypatch.setattr(module, "require_free", lambda ports: None)
        monkeypatch.setattr(module, "seed_database", lambda *args: pytest.fail("the dev run has no database to seed"))
        return module

    def test_the_dev_run_is_unchanged(self, dev_setup: ModuleType, tmp_path: Path) -> None:
        runtime = RecordingRuntime()
        config = tmp_path / "config.yaml"
        assert dev_setup.setup(runtime, DEFAULT_RUN, None, config, False) == 0
        specs = {spec.name: spec for spec in runtime.started}
        assert sorted(specs) == ["openbao-dev", "vault-dev"]
        assert specs["openbao-dev"].ports == ["127.0.0.1:8200:8200"]
        assert specs["vault-dev"].ports == ["127.0.0.1:8201:8201"]
        assert all(spec.labels == {LABEL: DEFAULT_RUN} for spec in specs.values())
        assert load_config(str(config)).vaults[0].name == "dev-openbao"
        assert not list(tmp_path.glob("*.json"))  # no run.json and no keycloak-users.json

    def test_the_dev_run_keeps_a_hand_written_config(self, dev_setup: ModuleType, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("vaults: []\n")
        assert dev_setup.setup(RecordingRuntime(), DEFAULT_RUN, None, config, False) == 1
        assert config.read_text() == "vaults: []\n"

    def test_the_dev_run_has_no_receiver_or_app(self, dev_setup: ModuleType, tmp_path: Path) -> None:
        options = dev_setup.Options(receiver=True)
        assert dev_setup.setup(RecordingRuntime(), DEFAULT_RUN, None, tmp_path / "c.yaml", False, options) == 1

    def test_a_scratch_path_with_a_colon_is_refused(self, dev_setup: ModuleType, tmp_path: Path) -> None:
        scratch = tmp_path / "a:b"
        assert dev_setup.setup(RecordingRuntime(), "a", scratch, tmp_path / "unused.yaml", False) == 1
        assert not scratch.exists()

    def test_restarting_a_run_replaces_only_that_run(
        self, dev_setup: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(dev_setup, "seed_database", lambda *args: None)  # a named run seeds its own database
        runtime = RecordingRuntime()
        runtime.containers = {"cw-a-vault": {LABEL: "a"}, "cw-b-vault": {LABEL: "b"}}
        assert dev_setup.setup(runtime, "a", tmp_path / "a", tmp_path / "unused.yaml", False) == 0
        assert runtime.removed == ["cw-a-vault"] and "cw-b-vault" in runtime.containers

    def test_config_is_only_for_the_dev_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dev_setup = _load_dev_setup()
        monkeypatch.setattr(sys, "argv", ["dev-setup.py", "--run", "a", "--config", "x.yaml"])
        assert dev_setup.main() == 1

    def test_a_written_oidc_and_alerting_config_loads(self, tmp_path: Path) -> None:
        idp = keycloak.Keycloak("kc", 8180)
        path = tmp_path / "config.yaml"
        alerting = {"enabled": True, "default_routes": [{"name": "dev-receiver", "url": "http://127.0.0.1:9/default"}]}
        write_dev_config(path, CREDENTIALS, auth=keycloak.oidc_auth(idp, "s3cret", "http://x/cb"), alerting=alerting)
        config = load_config(str(path))
        assert config.auth.mode == "oidc" and config.auth.oidc.issuer == idp.issuer
        assert [route.name for route in config.alerting.default_routes] == ["dev-receiver"]

    def test_the_owner_user_maps_to_the_seeded_owner(self) -> None:
        """Owner scope comes from the IdP group and email; the realm, the role mapping and the seed must agree."""
        users = {u["username"]: u for u in json.loads(keycloak.REALM_TEMPLATE.read_text())["users"]}
        assert users["owner"]["email"] == OWNER_EMAIL
        assert f"/{OWNER_GROUP}" in users["owner"]["groups"]
        assert OWNER_GROUP in keycloak.ROLE_GROUPS["owner"]


class TestScratch:
    def test_an_existing_open_dir_is_made_private(self, tmp_path: Path) -> None:
        scratch = tmp_path / "s"
        scratch.mkdir()
        scratch.chmod(0o777)
        assert _load_dev_setup()._prepare_scratch(scratch)
        assert stat.S_IMODE(scratch.stat().st_mode) == 0o700

    def test_a_symlink_is_refused(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        target.mkdir()
        (tmp_path / "link").symlink_to(target)
        assert not _load_dev_setup()._prepare_scratch(tmp_path / "link")

    def test_a_dir_of_another_user_is_refused(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        scratch = tmp_path / "s"
        scratch.mkdir()
        dev_setup = _load_dev_setup()
        monkeypatch.setattr(os, "getuid", lambda: os.stat(scratch).st_uid + 1)
        assert not dev_setup._prepare_scratch(scratch)

    def test_the_receiver_is_recorded_before_it_is_waited_for(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dev_setup = _load_dev_setup()

        def never_ready(*args: object, **kwargs: object) -> None:
            raise ContainerRuntimeError("not ready")

        monkeypatch.setattr(dev_setup, "wait_listening", never_ready)
        info = RunInfo(run="a", scratch=tmp_path, config=tmp_path / "config.yaml")
        with pytest.raises(ContainerRuntimeError):
            dev_setup._start_receiver(info, free_port())
        recorded = read_run(tmp_path)["pids"]["receiver"]
        assert stop(recorded["pid"], recorded["started"])


class TestCredentialOutput:
    def test_a_named_run_points_to_run_json_without_printing_secrets(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        info = RunInfo(run="a", scratch=tmp_path, config=tmp_path / "config.yaml")
        _load_dev_setup()._print_credentials(info, {VAULT: "root-token-x"}, {"admin": "pw-x"}, "http://kc", tmp_path)
        out = capsys.readouterr().out
        assert str(tmp_path / "run.json") in out
        assert "root-token-x" not in out and "pw-x" not in out

    def test_the_dev_run_prints_root_tokens_and_files_passwords(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _load_dev_setup()._print_credentials(None, {VAULT: "root-token-x"}, {"admin": "pw-x"}, "http://kc", tmp_path)
        out = capsys.readouterr().out
        assert "root-token-x" in out and "pw-x" not in out and "admin" in out
        users = tmp_path / "keycloak-users.json"
        assert json.loads(users.read_text()) == {"keycloak": "http://kc", "users": {"admin": "pw-x"}}
        assert stat.S_IMODE(users.stat().st_mode) == 0o600

    def test_the_dev_run_without_keycloak_writes_no_file(self, tmp_path: Path) -> None:
        _load_dev_setup()._print_credentials(None, {VAULT: "root-token-x"}, {}, "http://kc", tmp_path)
        assert not (tmp_path / "keycloak-users.json").exists()


class TestKeycloak:
    def test_the_realm_says_it_is_dev_only(self) -> None:
        realm = json.loads(keycloak.REALM_TEMPLATE.read_text())
        assert realm["displayName"].startswith("Chronowarden DEV ONLY")
        assert realm["sslRequired"] == "none"  # only for the 127.0.0.1 dev Keycloak; a change here is deliberate

    def test_realm_fills_client_and_users(self) -> None:
        passwords = {"admin": "pa", "owner": "po", "viewer": "pv"}
        data = keycloak.realm("http://localhost:9000/api/v1/auth/callback", "s3cret", passwords)
        client = data["clients"][0]
        assert (client["clientId"], client["secret"]) == ("chronowarden", "s3cret")
        assert client["redirectUris"] == ["http://localhost:9000/api/v1/auth/callback"]
        assert client["attributes"]["pkce.code.challenge.method"] == "S256"
        assert client["protocolMappers"][0]["config"]["full.path"] == "false"
        users = {u["username"]: u for u in data["users"]}
        assert {name: u["credentials"][0]["value"] for name, u in users.items()} == passwords
        assert all(u["emailVerified"] and not u["credentials"][0]["temporary"] for u in users.values())

    def test_every_user_is_in_one_role_group(self) -> None:
        groups = {g for names in keycloak.ROLE_GROUPS.values() for g in names}
        data = keycloak.realm("http://x/cb", "s", {u: "p" for u in keycloak.usernames()})
        assert {g["name"] for g in data["groups"]} == groups
        for user in data["users"]:
            assert [g.removeprefix("/") for g in user["groups"]] == keycloak.ROLE_GROUPS[user["username"]]

    def test_oidc_config_validates(self, tmp_path: Path) -> None:
        idp = keycloak.Keycloak("cw-a-keycloak", 49200)
        auth = keycloak.oidc_auth(idp, "s3cret", "http://localhost:49201/api/v1/auth/callback")
        path = tmp_path / "config.yaml"
        write_dev_config(path, CREDENTIALS, auth=auth)
        config = load_config(path)
        assert config.auth.oidc is not None
        assert config.auth.oidc.issuer == "http://localhost:49200/realms/chronowarden"
        assert config.auth.roles.admin == ["cw-admins"]


class TestProcesses:
    def test_spawn_and_stop_by_pid(self, tmp_path: Path) -> None:
        process = spawn(
            [sys.executable, "-c", "import time; print('up', flush=True); time.sleep(60)"], tmp_path, tmp_path / "log"
        )
        started = started_at(process.pid)
        assert stop(process.pid, started)
        assert not stop(process.pid, started)  # gone (and reaped) once stop() returns

    def test_stop_kills_what_ignores_sigterm(self, tmp_path: Path) -> None:
        code = (
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('up', flush=True); "
            "time.sleep(60)"
        )
        process = spawn([sys.executable, "-c", code], tmp_path, tmp_path / "log")
        wait_until = time.monotonic() + 5
        while "up" not in (tmp_path / "log").read_text() and time.monotonic() < wait_until:
            time.sleep(0.05)
        assert stop(process.pid, started_at(process.pid), timeout=0.5)
        assert process.wait(timeout=5) == -signal.SIGKILL

    def test_a_reused_pid_is_not_stopped(self, tmp_path: Path) -> None:
        process = spawn([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, tmp_path / "log")
        try:
            assert not stop(process.pid, "Thu Jan  1 00:00:00 1970")
            assert process.poll() is None
        finally:
            assert stop(process.pid, started_at(process.pid))

    @pytest.mark.parametrize("pid", [0, 1, -1, "12", True, None])
    def test_only_plain_pids_above_1_are_stopped(self, pid: object, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(os, "killpg", lambda *args: pytest.fail("signalled"))
        assert not stop(pid, "any")

    def test_a_pid_of_another_user_is_left_alone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(*args: object) -> None:
            raise PermissionError(1, "Operation not permitted")

        monkeypatch.setattr(os, "killpg", refuse)
        assert not stop(os.getpid(), started_at(os.getpid()))

    def test_wait_listening_fails_when_another_server_answers(self, tmp_path: Path) -> None:
        with socket.socket() as other:
            other.bind(("127.0.0.1", 0))
            other.listen()
            port = other.getsockname()[1]
            process = spawn([sys.executable, "-c", "raise SystemExit(1)"], tmp_path, tmp_path / "log")
            process.wait(timeout=5)
            with pytest.raises(ContainerRuntimeError, match="exited"):
                wait_listening(port, process, tmp_path / "log", timeout=2)

    def test_wait_http_fails_when_another_server_answers(self, tmp_path: Path) -> None:
        other = make_server(0, tmp_path / "other.jsonl")  # answers GET with 501, so serve a 200 instead
        other.RequestHandlerClass.do_GET = lambda self: (self.send_response(200), self.end_headers())  # type: ignore
        threading.Thread(target=other.serve_forever, daemon=True).start()
        calls = iter([True, False])  # ours was alive at the first look, gone once something answered
        try:
            with pytest.raises(ContainerRuntimeError, match="exited"):
                wait_http(f"http://127.0.0.1:{other.server_port}/", 5, lambda: next(calls, False))
        finally:
            other.shutdown()

    def test_wait_http_fails_fast_when_the_process_dies(self, tmp_path: Path) -> None:
        process = spawn([sys.executable, "-c", "raise SystemExit(3)"], tmp_path, tmp_path / "log")
        with pytest.raises(ContainerRuntimeError, match="exited; see app.log"):
            wait_http(f"http://127.0.0.1:{free_port()}/", 10, lambda: process.poll() is None, "app.log")


class TestReceiver:
    def test_records_requests_as_json_lines(self, tmp_path: Path) -> None:
        out = tmp_path / "webhooks.jsonl"
        server = make_server(0, out)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/owner"
            assert requests.post(url, json={"a": 1}, headers={"webhook-signature": "v1,x"}, timeout=5).ok
        finally:
            server.shutdown()
        (entry,) = [json.loads(line) for line in out.read_text().splitlines()]
        assert (entry["path"], json.loads(entry["body"])) == ("/owner", {"a": 1})
        assert entry["headers"]["webhook-signature"] == "v1,x"

    def test_records_a_signed_delivery_from_chronowarden(self, tmp_path: Path) -> None:
        out = tmp_path / "webhooks.jsonl"
        server = make_server(0, out)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            status, error = post(
                f"http://127.0.0.1:{server.server_port}/owner",
                b'{"status": "firing"}',
                "msg_1",
                "whsec_" + "A" * 32,
                datetime.now(timezone.utc),
            )
        finally:
            server.shutdown()
        assert (status, error) == (200, "")
        (entry,) = [json.loads(line) for line in out.read_text().splitlines()]
        headers = {k.lower(): v for k, v in entry["headers"].items()}
        assert entry["path"] == "/owner" and headers["webhook-id"] == "msg_1"
        assert headers["webhook-signature"].startswith("v1,")

    def test_a_bad_content_length_is_refused_and_does_not_block(self, tmp_path: Path) -> None:
        out = tmp_path / "webhooks.jsonl"
        server = make_server(0, out)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_port
        try:
            for length, status in (("-1", 400), ("x", 400), (str(11 * 1024 * 1024), 413)):
                with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
                    sock.sendall(f"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: {length}\r\n\r\n".encode())
                    assert sock.recv(64).split()[1] == str(status).encode()
            with socket.create_connection(("127.0.0.1", port), timeout=5):  # a client that sends nothing
                assert requests.post(f"http://127.0.0.1:{port}/after", json={}, timeout=5).ok
        finally:
            server.shutdown()
        assert [json.loads(line)["path"] for line in out.read_text().splitlines()] == ["/after"]


class TestSeed:
    def test_owner_system_and_signed_route(self, tmp_path: Path) -> None:
        db_path = tmp_path / "chronowarden.db"
        secret = seed_database(db_path, "http://127.0.0.1:9/owner")
        assert secret is not None and secret.startswith("whsec_")
        db = Database(db_path)
        db.connect()
        try:
            (owner,) = db.list_owners()
            assert (owner["id"], owner["email"], owner["idp_group"]) == ("team-owner", OWNER_EMAIL, "teams")
            (route,) = db.list_notification_routes("team-owner")
            assert route["signed"] and route["address"] == "http://127.0.0.1:9/owner"
            systems, owners = db.get_assignments()
            assert all(systems[i] == "payments" and owners[i] == ["team-owner"] for i in OWNED_SECRETS)
        finally:
            db.close()

    def test_without_receiver_no_route(self, tmp_path: Path) -> None:
        assert seed_database(tmp_path / "chronowarden.db", None) is None
