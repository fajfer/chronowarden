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
        self._run(*args, spec.image)

    def remove(self, name: str) -> None:
        """Force-remove a container."""
        self._run("rm", "--force", name)
