#!/usr/bin/env -S uv run
# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Start the local OpenBao and HashiCorp Vault dev servers, seed them, and write a config.yaml for them (#78)."""

import argparse
import logging
import sys
import time
from pathlib import Path

import hvac
from requests.exceptions import RequestException

from devenv.backends import BACKENDS, Backend, random_token, seed, setup_approle
from devenv.config import can_write, write_dev_config
from devenv.runtime import ContainerRuntimeError, ContainerSpec, Runtime, detect_runtime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dev-setup")


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


def _start(runtime: Runtime, backend: Backend) -> str:
    """(Re)create a backend's container with a fresh root token and return it."""
    if runtime.exists(backend.container):
        logger.info("Replacing %s", backend.container)
        runtime.remove(backend.container)
    token = random_token()
    runtime.start(
        ContainerSpec(
            name=backend.container,
            image=backend.image,
            ports=[f"127.0.0.1:{backend.port}:{backend.port}"],
            env={backend.root_token_env: token, **dict(backend.extra_env)},
            cap_add=list(backend.cap_add),
        )
    )
    return token


def setup(runtime: Runtime, config_path: Path, force: bool) -> int:
    """Start, seed and configure both dev backends; returns the exit code."""
    if not can_write(config_path, force):
        logger.error("%s wasn't written by dev-setup.py; use --force to replace it or --config elsewhere", config_path)
        return 1
    credentials: dict[Backend, tuple[str, str]] = {}
    tokens: dict[Backend, str] = {}
    for backend in BACKENDS:
        logger.info("Starting %s (%s) with %s", backend.container, backend.image, runtime.cli)
        tokens[backend] = _start(runtime, backend)
        client = _wait_ready(backend, tokens[backend])
        seed(client)
        credentials[backend] = setup_approle(client)
        logger.info("%s ready at %s", backend.container, backend.address)
    write_dev_config(config_path, credentials, force=force)
    logger.info("Wrote %s; run: uv run uvicorn chronowarden:app --reload", config_path)
    # Printed, not logged: dev-only root tokens for poking at the servers by hand
    print("\nRoot tokens (dev only):")
    for backend, token in tokens.items():
        print(f"  {backend.container} {backend.address}: {token}")
    return 0


def cleanup(runtime: Runtime) -> int:
    """Remove both dev containers; returns the exit code."""
    for backend in BACKENDS:
        if runtime.exists(backend.container):
            runtime.remove(backend.container)
            logger.info("Removed %s", backend.container)
        else:
            logger.info("%s does not exist, nothing to remove", backend.container)
    return 0


def main() -> int:
    """Parse arguments and run setup or cleanup."""
    parser = argparse.ArgumentParser(description="Set up or tear down the Chronowarden development vaults.")
    parser.add_argument("--cleanup", action="store_true", help="remove the dev containers and exit")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="where to write the config")
    parser.add_argument("--force", action="store_true", help="replace a config not written by dev-setup.py")
    args = parser.parse_args()
    try:
        runtime = Runtime(detect_runtime())
        return cleanup(runtime) if args.cleanup else setup(runtime, args.config, args.force)
    except ContainerRuntimeError as exc:
        print(f"dev-setup: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
