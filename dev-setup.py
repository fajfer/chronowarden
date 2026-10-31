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
import shutil
import sys
import time
from pathlib import Path

import hvac
from requests.exceptions import RequestException

from devenv import keycloak
from devenv.backends import BACKENDS, Backend, random_token, seed, setup_approle
from devenv.config import can_write, write_dev_config
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dev-setup")

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


def _prepare_scratch(scratch: Path) -> bool:
    """Empty `scratch` for a fresh run (only if a run created it) and create it private; False if it can't be used."""
    if scratch.is_dir() and any(scratch.iterdir()):
        if read_run(scratch) is None:
            logger.error("%s isn't empty and has no run.json; choose another --scratch", scratch)
            return False
        shutil.rmtree(scratch)  # a fresh run gets a fresh database and logs
    scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    return True


def setup(runtime: Runtime, run: str, scratch: Path | None, config_path: Path, force: bool, auth: str = "none") -> int:
    """Start, seed and configure the dev backends (and Keycloak for `auth` oidc) of `run`; returns the exit code."""
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
    write_dev_config(config_path, credentials, force=force, auth=auth_config)
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
        logger.info("Wrote %s; remove the run with: ./dev-setup.py --cleanup --run %s", info.write(), run)
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
        if read_run(scratch) is None:
            logger.error("%s has no run.json; not deleting a directory dev-setup.py didn't create", scratch)
            return 1
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
        return setup(runtime, run, scratch, args.config, args.force, args.auth)
    except (ContainerRuntimeError, RunError) as exc:
        print(f"dev-setup: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
