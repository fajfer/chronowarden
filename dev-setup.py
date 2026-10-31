#!/usr/bin/env -S uv run
# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""
Start the local OpenBao and HashiCorp Vault dev servers, seed them, and write a config.yaml for them (#78).

Every environment is a named run (`--run`, default `dev`); see .ai/docs/dev-env.md.
"""

import argparse
import logging
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import hvac
from requests.exceptions import RequestException

from devenv import keycloak
from devenv.backends import BACKENDS, Backend, random_token, seed, setup_approle
from devenv.config import can_write, write_dev_config
from devenv.processes import spawn, stop, wait_http, wait_listening
from devenv.runs import (
    DEFAULT_RUN,
    LABEL,
    RunError,
    RunInfo,
    check_name,
    container_name,
    default_scratch,
    free_port,
    read_run,
    require_free,
)
from devenv.runtime import ContainerRuntimeError, ContainerSpec, Runtime, detect_runtime
from devenv.seed import seed_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dev-setup")

REPO = Path(__file__).resolve().parent
APP_IMAGE = "chronowarden:test"  # docker build -t chronowarden:test . (deploy/AGENTS.md); podman adds localhost/
WEBHOOKS_FILE = "webhooks.jsonl"
DEV_APP_PORT = 8000  # uvicorn's default, where the dev run's OIDC redirect URI points


def _wait_ready(backend: Backend, token: str, timeout: float = 60) -> hvac.Client:
    """Wait until the dev server answers and accepts the root token."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        client = hvac.Client(url=backend.address, token=token)
        try:
            if client.sys.is_initialized() and client.is_authenticated():
                return client
        except (RequestException, hvac.exceptions.VaultError):
            pass  # not up yet
        time.sleep(1)
    raise ContainerRuntimeError(f"{backend.container} didn't become ready at {backend.address} within {timeout:.0f}s")


def _start(runtime: Runtime, backend: Backend, run: str) -> str:
    """Create a backend's container for `run` with a fresh root token and return it."""
    token = random_token()
    runtime.start(
        ContainerSpec(
            name=backend.container,
            image=backend.image,
            ports=[f"127.0.0.1:{backend.published_port}:{backend.port}"],
            env={backend.root_token_env: token, **dict(backend.extra_env)},
            cap_add=list(backend.cap_add),
            labels={LABEL: run},
        )
    )
    return token


def _remove_run(runtime: Runtime, run: str) -> list[str]:
    """Remove the containers of `run` (by label; the `dev` run also by its pre-label names) and return their names."""
    names = runtime.labelled(LABEL, run)
    if run == DEFAULT_RUN:
        names += [b.container for b in BACKENDS if b.container not in names and runtime.exists(b.container)]
    for name in names:
        runtime.remove(name)
        logger.info("Removed %s", name)
    return names


def _backends(run: str) -> list[Backend]:
    """The backends of `run`: the `dev` run on its fixed ports, any other on free ones."""
    if run == DEFAULT_RUN:
        return list(BACKENDS)
    return [b.for_run(container_name(run, b.service, b.container), free_port()) for b in BACKENDS]


def _start_keycloak(
    runtime: Runtime, idp: keycloak.Keycloak, run: str, redirect_uri: str
) -> tuple[dict, dict[str, str]]:
    """Start Keycloak for `run`, import the realm; returns the `auth` config section and the users' passwords."""
    admin_password = keycloak.random_password()
    logger.info("Starting %s (%s) with %s", idp.container, keycloak.IMAGE, runtime.cli)
    runtime.start(
        ContainerSpec(
            name=idp.container,
            image=keycloak.IMAGE,
            ports=[f"127.0.0.1:{idp.host_port}:{keycloak.PORT}"],
            env={
                "KC_BOOTSTRAP_ADMIN_USERNAME": keycloak.BOOTSTRAP_ADMIN,
                "KC_BOOTSTRAP_ADMIN_PASSWORD": admin_password,
            },
            labels={LABEL: run},
            command=["start-dev"],
        )
    )
    keycloak.wait_ready(idp)
    client_secret = keycloak.random_password()
    passwords = {user: keycloak.random_password() for user in keycloak.usernames()}
    keycloak.import_realm(idp, admin_password, keycloak.realm(redirect_uri, client_secret, passwords))
    logger.info("%s ready at %s (realm %s)", idp.container, idp.address, keycloak.REALM)
    return keycloak.oidc_auth(idp, client_secret, redirect_uri), passwords


def _stop_processes(info: dict) -> None:
    """Stop the processes a run recorded in run.json (by PID only)."""
    for name, pid in info.get("pids", {}).items():
        if stop(pid):
            logger.info("Stopped %s (PID %d)", name, pid)


def _prepare_scratch(scratch: Path) -> bool:
    """Empty `scratch` for a fresh run (only if a run created it) and create it private; False if it can't be used."""
    if scratch.is_dir() and any(scratch.iterdir()):
        if read_run(scratch) is None:
            logger.error("%s isn't empty and has no run.json; choose another --scratch", scratch)
            return False
        _stop_processes(read_run(scratch) or {})
        shutil.rmtree(scratch)  # a fresh run gets a fresh database and logs
    scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    return True


@dataclass(frozen=True)
class Options:
    """What a run starts besides the vaults."""

    auth: str = "none"  # or "oidc": Keycloak
    receiver: bool = False  # a webhook receiver writing <scratch>/webhooks.jsonl
    app: Optional[str] = None  # "source" or "image": start Chronowarden too


def _start_receiver(scratch: Path, port: int) -> int:
    """Start the webhook receiver; returns its PID."""
    process = spawn(
        [sys.executable, "-m", "devenv.receiver", "--port", str(port), "--out", str(scratch / WEBHOOKS_FILE)],
        cwd=REPO,
        log=scratch / "receiver.log",
    )
    wait_listening(port, process, scratch / "receiver.log")
    return process.pid


def _start_app_source(scratch: Path, config_path: Path, port: int) -> int:
    """Start Chronowarden from this checkout with the run's config, working dir and port; returns its PID."""
    log = scratch / "app.log"
    process = spawn(
        [sys.executable, "-m", "uvicorn", "chronowarden:app", "--host", "127.0.0.1", "--port", str(port)]
        + ["--no-proxy-headers"],
        cwd=scratch,
        log=log,
        env={"CHRONOWARDEN_CONFIG": str(config_path)},
    )
    wait_http(f"http://localhost:{port}/api/v1/ready", 60, lambda: process.poll() is None, str(log))
    return process.pid


def _start_app_image(runtime: Runtime, run: str, scratch: Path, port: int) -> str:
    """Start the locally built production image with the scratch dir as /data; returns the container name."""
    name = container_name(run, "app", "chronowarden-dev")
    # Run as the host user: the scratch dir is private to it (podman also has to map it into the container)
    user = ["--user", f"{os.getuid()}:{os.getgid()}"] + (["--userns=keep-id"] if runtime.cli == "podman" else [])
    runtime.start(
        ContainerSpec(
            name=name,
            image=f"localhost/{APP_IMAGE}" if runtime.cli == "podman" else APP_IMAGE,
            env={"CHRONOWARDEN_CONFIG": "/data/config.yaml"},
            labels={LABEL: run},
            volumes=[f"{scratch}:/data"],
            network="host",  # reaches the run's vaults, Keycloak and receiver on localhost, like the browser
            workdir="/data",
            entrypoint="python",
            command=["-m", "uvicorn", "chronowarden:app", "--host", "127.0.0.1", "--port", str(port)]
            + ["--no-proxy-headers"],
            extra_args=user,
        )
    )
    wait_http(f"http://localhost:{port}/api/v1/ready", 90, lambda: runtime.running(name), f"{runtime.cli} logs {name}")
    return name


def setup(
    runtime: Runtime, run: str, scratch: Path | None, config_path: Path, force: bool, options: Options = Options()
) -> int:
    """Start, seed and configure the dev backends (and what `options` asks for) of `run`; returns the exit code."""
    auth = options.auth
    if run == DEFAULT_RUN and (options.receiver or options.app):
        logger.error("--receiver and --app need a named run (--run <name>); the dev run is started by hand")
        return 1
    if scratch is not None:
        if not _prepare_scratch(scratch):
            return 1
        config_path, force = scratch / "config.yaml", True  # the scratch dir belongs to the run
    if not can_write(config_path, force):
        logger.error("%s wasn't written by dev-setup.py; use --force to replace it or --config elsewhere", config_path)
        return 1
    _remove_run(runtime, run)
    dev = run == DEFAULT_RUN
    backends = _backends(run)
    app_port = DEV_APP_PORT if dev else free_port()
    idp = keycloak.Keycloak(container_name(run, "keycloak", "keycloak-dev"), keycloak.DEV_PORT if dev else free_port())
    ports = {b.container: b.published_port for b in backends}
    if auth == "oidc":
        ports[idp.container] = idp.host_port
    receiver_port = free_port()
    if options.receiver:
        ports["receiver"] = receiver_port
    if options.app:
        ports["app"] = app_port
    require_free(ports)
    credentials: dict[Backend, tuple[str, str]] = {}
    tokens: dict[Backend, str] = {}
    for backend in backends:
        logger.info("Starting %s (%s) with %s", backend.container, backend.image, runtime.cli)
        tokens[backend] = _start(runtime, backend, run)
        client = _wait_ready(backend, tokens[backend])
        seed(client)
        credentials[backend] = setup_approle(client)
        logger.info("%s ready at %s", backend.container, backend.address)
    app_url = f"http://localhost:{app_port}"
    auth_config, passwords = None, {}
    if auth == "oidc":
        auth_config, passwords = _start_keycloak(runtime, idp, run, f"{app_url}/api/v1/auth/callback")
    receiver_url = f"http://127.0.0.1:{receiver_port}" if options.receiver else None
    alerting = None
    if receiver_url is not None:
        alerting = {"enabled": True, "default_routes": [{"name": "dev-receiver", "url": f"{receiver_url}/default"}]}
    write_dev_config(config_path, credentials, force=force, auth=auth_config, alerting=alerting)
    logger.info("Wrote %s", config_path)
    urls = {"app": app_url, **{b.config_name: b.address for b in backends}}
    if auth == "oidc":
        urls["keycloak"] = idp.address
    if scratch is not None:
        info = RunInfo(
            run=run,
            scratch=scratch,
            config=config_path,
            containers=[b.container for b in backends] + ([idp.container] if auth == "oidc" else []),
            urls=urls,
            users=passwords,
            root_tokens={b.config_name: tokens[b] for b in backends},
        )
        info.write()  # before starting processes: cleanup finds them even if a later step fails
        route_secret = seed_database(scratch / "chronowarden.db", f"{receiver_url}/owner" if receiver_url else None)
        if route_secret is not None:
            info.signing_secrets["owner-route"] = route_secret
        if receiver_url is not None:
            info.urls["receiver"] = receiver_url
            info.pids["receiver"] = _start_receiver(scratch, receiver_port)
            info.write()
        if options.app == "source":
            info.pids["app"] = _start_app_source(scratch, config_path, app_port)
        elif options.app == "image":
            info.containers.append(_start_app_image(runtime, run, scratch, app_port))
        info.write()
        logger.info("Wrote %s; remove the run with: ./dev-setup.py --cleanup --run %s", scratch / "run.json", run)
        if options.app:
            logger.info("Chronowarden at %s", app_url)
    else:
        logger.info("Run: uv run uvicorn chronowarden:app --reload --port %d", app_port)
    # Printed, not logged: dev-only credentials for poking at the servers by hand
    print("\nRoot tokens (dev only):")
    for backend, token in tokens.items():
        print(f"  {backend.container} {backend.address}: {token}")
    if passwords:
        print(f"Keycloak users at {idp.address} (dev only):")
        for user, password in passwords.items():
            print(f"  {user}: {password}")
    return 0


def cleanup(runtime: Runtime, run: str, scratch: Path | None) -> int:
    """Remove the containers of `run` and, if it has one, its scratch dir; returns the exit code."""
    if not _remove_run(runtime, run):
        logger.info("Run %s has no containers, nothing to remove", run)
    if scratch is not None and scratch.is_dir():
        info = read_run(scratch)
        if info is None:
            logger.error("%s has no run.json; not deleting a directory dev-setup.py didn't create", scratch)
            return 1
        _stop_processes(info)
        shutil.rmtree(scratch)
        logger.info("Removed %s", scratch)
    return 0


def list_runs(runtime: Runtime) -> int:
    """Print every run that has containers, with them; returns the exit code."""
    runs: dict[str, list[str]] = {}
    for name in runtime.labelled(LABEL):
        runs.setdefault(runtime.label(name, LABEL), []).append(name)
    for run, names in sorted(runs.items()):
        print(f"{run}: {', '.join(sorted(names))}")
    if not runs:
        print("No runs")
    return 0


def main() -> int:
    """Parse arguments and set up, clean up or list runs."""
    parser = argparse.ArgumentParser(description="Set up or tear down Chronowarden development environments (runs).")
    parser.add_argument("--run", default=DEFAULT_RUN, help="name of the run (default: dev, on ports 8200/8201)")
    parser.add_argument("--scratch", type=Path, help="the run's working dir (default for runs other than dev: $TMPDIR)")
    parser.add_argument("--cleanup", action="store_true", help="remove the run's containers and scratch dir and exit")
    parser.add_argument("--list", action="store_true", help="list the runs that have containers and exit")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="where the dev run writes its config")
    parser.add_argument("--auth", choices=["none", "oidc"], default="none", help="login: none, or oidc via Keycloak")
    parser.add_argument("--receiver", action="store_true", help="start a webhook receiver (<scratch>/webhooks.jsonl)")
    parser.add_argument(
        "--app", nargs="?", const="source", choices=["source", "image"], help="start Chronowarden: source or image"
    )
    parser.add_argument("--force", action="store_true", help="replace a config not written by dev-setup.py")
    args = parser.parse_args()
    try:
        run = check_name(args.run)
        scratch = args.scratch if args.scratch or run == DEFAULT_RUN else default_scratch(run)
        runtime = Runtime(detect_runtime())
        if args.list:
            return list_runs(runtime)
        if args.cleanup:
            return cleanup(runtime, run, scratch)
        return setup(runtime, run, scratch, args.config, args.force, Options(args.auth, args.receiver, args.app))
    except (ContainerRuntimeError, RunError) as exc:
        print(f"dev-setup: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
