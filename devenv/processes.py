# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Background processes of a dev run (the app, the webhook receiver): started detached, stopped by recorded PID."""

import logging
import os
import signal
import socket
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

import requests
from requests.exceptions import RequestException

from devenv.runtime import ContainerRuntimeError

logger = logging.getLogger("dev-setup")


def started_at(pid: int) -> Optional[str]:
    """`ps`'s start time for `pid`, which tells it apart from a later process with the same PID; None if gone."""
    try:
        result = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, check=False)
    except OSError:
        return None
    return result.stdout.strip() or None


def spawn(args: list[str], cwd: Path, log: Path, env: Optional[dict[str, str]] = None) -> subprocess.Popen:
    """Start `args` in its own session (so it outlives dev-setup.py), output appended to `log`."""
    with log.open("ab") as out:
        return subprocess.Popen(
            args,
            cwd=cwd,
            env={**os.environ, **(env or {})},
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def stop(pid: object, started: object, timeout: float = 10) -> bool:
    """
    Stop the process group a recorded PID leads (spawn() made it a session leader); never matches by name.
    Only if the PID still belongs to the process recorded (`started`, from `started_at`): a PID reused by another
    process, or one that isn't a plain PID above 1, is left alone. SIGTERM first, SIGKILL after `timeout` seconds.

    Returns:
        Whether a process was there to stop.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1 or not isinstance(started, str):
        logger.warning("Not stopping %r: not a recorded process", pid)
        return False
    now = started_at(pid)
    if now is None:
        return False
    if now != started:
        logger.warning("PID %d now belongs to another process; not stopping it", pid)
        return False
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except PermissionError:
        logger.warning("PID %d belongs to another user; not stopping it", pid)
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.waitpid(pid, os.WNOHANG)  # reap it if it's our own child, or it lingers as a zombie
        except ChildProcessError:
            pass  # started by an earlier dev-setup.py; init reaps it
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # exited just now
    return True


def wait_http(url: str, timeout: float, alive: Optional[Callable[[], bool]] = None, logs: str = "") -> None:
    """
    Wait until `url` answers 2xx; fail early once `alive` says the server is gone.

    Raises:
        ContainerRuntimeError: On timeout or when the server died, pointing to its `logs`.
    """
    where = f"; see {logs}" if logs else ""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if alive is not None and not alive():
            raise ContainerRuntimeError(f"The server for {url} exited{where}")
        try:
            if requests.get(url, timeout=5).ok:
                return
        except RequestException:
            pass  # not up yet
        time.sleep(0.5)
    raise ContainerRuntimeError(f"{url} didn't answer within {timeout:.0f}s{where}")


def wait_listening(port: int, process: subprocess.Popen, log: Path, timeout: float = 15) -> None:
    """
    Wait until something accepts connections on 127.0.0.1:`port`; fail early if `process` exits.

    Raises:
        ContainerRuntimeError: On timeout or when the process died, pointing to `log`.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ContainerRuntimeError(f"Process for port {port} exited with {process.returncode}; see {log}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
        except OSError:
            time.sleep(0.2)
            continue
        if process.poll() is None:
            return  # still ours: the answer didn't come from something else on the port
        raise ContainerRuntimeError(f"Process for port {port} exited with {process.returncode}; see {log}")
    raise ContainerRuntimeError(f"Nothing listened on port {port} within {timeout:.0f}s; see {log}")
