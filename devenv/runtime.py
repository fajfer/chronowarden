# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""The container runtime the dev environment uses: podman preferred, docker as fallback."""

import os
import shutil
import subprocess
from dataclasses import dataclass, field

ENV_RUNTIME = "CHRONOWARDEN_CONTAINER_RUNTIME"


class ContainerRuntimeError(Exception):
    """No usable container runtime, or a runtime command failed."""


def detect_runtime() -> str:
    """
    Choose the container CLI: `CHRONOWARDEN_CONTAINER_RUNTIME`, else podman, else docker.

    Raises:
        ContainerRuntimeError: If the chosen or any runtime isn't installed.
    """
    chosen = os.environ.get(ENV_RUNTIME)
    candidates = [chosen] if chosen else ["podman", "docker"]
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    raise ContainerRuntimeError(f"No container runtime found (tried {', '.join(candidates)}); install podman or docker")


@dataclass
class ContainerSpec:
    """How to run one dev container."""

    name: str
    image: str
    ports: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cap_add: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    command: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    network: str | None = None
    workdir: str | None = None
    entrypoint: str | None = None
    extra_args: list[str] = field(default_factory=list)


@dataclass
class Runtime:
    """Thin wrapper around the podman/docker CLI."""

    cli: str

    def _run(self, *args: str) -> str:
        try:
            return subprocess.run([self.cli, *args], capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError as exc:
            raise ContainerRuntimeError(f"{self.cli} {' '.join(args[:2])} failed: {exc.stderr.strip()}") from None

    def exists(self, name: str) -> bool:
        """Whether a container with exactly this name exists (running or stopped)."""
        return name in self._run("ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}").split()

    def running(self, name: str) -> bool:
        """Whether a container with exactly this name is running."""
        return name in self._run("ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}").split()

    def start(self, spec: ContainerSpec) -> None:
        """Run a container detached."""
        args = ["run", "-d", "--name", spec.name]
        for port in spec.ports:
            args += ["-p", port]
        for key, value in spec.env.items():
            args += ["-e", f"{key}={value}"]
        for cap in spec.cap_add:
            args += ["--cap-add", cap]
        for key, value in spec.labels.items():
            args += ["--label", f"{key}={value}"]
        for volume in spec.volumes:
            args += ["-v", volume]
        for flag, value in (
            ("--network", spec.network),
            ("--workdir", spec.workdir),
            ("--entrypoint", spec.entrypoint),
        ):
            if value is not None:
                args += [flag, value]
        args += spec.extra_args
        self._run(*args, spec.image, *spec.command)

    def remove(self, name: str) -> None:
        """Force-remove a container."""
        self._run("rm", "--force", name)

    def labelled(self, key: str, value: str | None = None) -> list[str]:
        """Names of all containers (running or stopped) carrying label `key`, or `key=value` when given."""
        selector = key if value is None else f"{key}={value}"
        return self._run("ps", "-a", "--filter", f"label={selector}", "--format", "{{.Names}}").split()

    def label(self, name: str, key: str) -> str:
        """The value of label `key` on container `name` (empty if unset)."""
        return self._run("inspect", "--format", f'{{{{index .Config.Labels "{key}"}}}}', name).strip()
