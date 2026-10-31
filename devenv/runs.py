# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Named dev runs: container names, labels, ports and the scratch directory each run owns."""

import json
import os
import re
import socket
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_RUN = "dev"
LABEL = "chronowarden.devenv.run"
RUN_FILE = "run.json"
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")


class RunError(Exception):
    """A run can't be started as asked: bad name, busy port."""


def check_name(name: str) -> str:
    """
    Return `name` if it can name a run (and its containers).

    Raises:
        RunError: If it isn't 1-31 lowercase letters, digits or dashes, starting with a letter or digit.
    """
    if not _NAME.match(name):
        raise RunError(f"Run name {name!r}: use 1-31 lowercase letters, digits or dashes")
    return name


def container_name(run: str, service: str, legacy: str) -> str:
    """The container of `service` in `run`; the `dev` run keeps its pre-run names (`legacy`)."""
    return legacy if run == DEFAULT_RUN else f"cw-{run}-{service}"


def default_scratch(run: str) -> Path:
    """Where a run keeps config, database, logs and `run.json` unless told otherwise."""
    return Path(tempfile.gettempdir()) / f"chronowarden-{run}"


def port_free(port: int) -> bool:
    """Whether nothing listens on 127.0.0.1:`port`."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def free_port() -> int:
    """A port on 127.0.0.1 that was free a moment ago (the OS picks it)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def require_free(ports: dict[str, int]) -> None:
    """
    Check that every port is free before a run starts, so it never talks to whatever already listens there.

    Raises:
        RunError: Naming each busy port and what it was meant for.
    """
    busy = [f"{port} ({what})" for what, port in ports.items() if not port_free(port)]
    if busy:
        raise RunError(f"Port(s) already in use: {', '.join(busy)}; stop what listens there or use another --run")


@dataclass
class RunInfo:
    """What a run started, written to `<scratch>/run.json` for people and agents to read."""

    run: str
    scratch: Path
    config: Path
    containers: list[str] = field(default_factory=list)
    urls: dict[str, str] = field(default_factory=dict)
    users: dict[str, str] = field(default_factory=dict)
    pids: dict[str, int] = field(default_factory=dict)
    root_tokens: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """A JSON-ready dict (paths as strings)."""
        return {
            "run": self.run,
            "scratch": str(self.scratch),
            "config": str(self.config),
            "containers": self.containers,
            "urls": self.urls,
            "users": self.users,
            "pids": self.pids,
            "root_tokens": self.root_tokens,
        }

    def write(self) -> Path:
        """Write `run.json` into the scratch dir, readable by the owner only (it holds dev passwords)."""
        path = self.scratch / RUN_FILE
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as file:
            file.write(json.dumps(self.to_json(), indent=2) + "\n")
        path.chmod(0o600)  # an older run.json keeps its mode through O_TRUNC
        return path


def read_run(scratch: Path) -> dict[str, Any] | None:
    """The `run.json` in `scratch`, or None if there is none or it's unreadable."""
    try:
        return json.loads((scratch / RUN_FILE).read_text())
    except (OSError, json.JSONDecodeError):
        return None
