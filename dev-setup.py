#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""
Development setup script for Chronowarden.

This script ensures that development Vault instances are running and
creates a config.yaml with extracted tokens for local development.
"""

import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Container configurations
CONTAINERS = {
    "openbao-dev": {
        "image": "quay.io/openbao/openbao",
        "ports": ["127.0.0.1:8200:8200"],
        "name": "openbao-dev",
        "token_pattern": r"Root Token:\s*([a-zA-Z0-9._-]+)",
        "ready_pattern": r"OpenBao server started",
    },
    "dev-vault": {
        "image": "hashicorp/vault",
        "ports": ["127.0.0.1:8201:8201"],
        "name": "dev-vault",
        "env": ["VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8201"],
        "cap_add": ["IPC_LOCK"],
        "token_pattern": r"Root Token:\s*([a-zA-Z0-9._-]+)",
        "ready_pattern": r"Vault server started",
    },
}


def run_command(cmd: list[str], capture_output: bool = False) -> tuple[Optional[str], bool]:
    """Run a shell command and return (output, success)."""
    try:
        result = subprocess.run(cmd, capture_output=capture_output, text=True, check=True)
        output = result.stdout if capture_output else None
        return output, True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)}")
        logger.error(f"Error: {e}")
        if e.stdout:
            logger.error(f"Stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"Stderr: {e.stderr}")
        return None, False


def is_container_running(name: str) -> bool:
    """Check if a Docker container is running."""
    result, success = run_command(["docker", "ps", "--filter", f"name={name}", "--format", "{{.Names}}"], capture_output=True)
    return success and name in (result or "")


def start_container(config: dict) -> bool:
    """Start a Docker container with the given configuration."""
    name = config["name"]
    cmd = [
        "docker", "run",
        "-d",
        "--name", name,
    ]

    # Add ports
    for port in config.get("ports", []):
        cmd.extend(["-p", port])

    # Add environment variables
    for env in config.get("env", []):
        cmd.extend(["-e", env])

    # Add capabilities
    for cap in config.get("cap_add", []):
        cmd.extend(["--cap-add", cap])

    # Add image
    cmd.append(config["image"])

    logger.info(f"Starting container {name}...")
    if run_command(cmd, capture_output=False)[1]:  # Check success
        return True
    return False


def wait_for_container_ready(name: str, ready_pattern: str, timeout: int = 60) -> bool:
    """Wait for a container to be ready by checking logs for a pattern."""
    logger.info(f"Waiting for {name} to be ready (timeout: {timeout}s)...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        logs, success = run_command(["docker", "logs", name], capture_output=True)
        if success and logs and re.search(ready_pattern, logs, re.MULTILINE):
            logger.info(f"{name} is ready!")
            return True
        time.sleep(2)  # Check every 2 seconds instead of 1

    logger.error(f"{name} did not become ready within {timeout} seconds")
    return False


def extract_token_from_logs(name: str, token_pattern: str) -> Optional[str]:
    """Extract token from container logs using regex pattern."""
    logs, success = run_command(["docker", "logs", name], capture_output=True)
    if not success or not logs:
        return None

    match = re.search(token_pattern, logs, re.MULTILINE)
    if match:
        token = match.group(1)
        logger.info(f"Extracted token for {name}: {token[:8]}...")
        return token

    logger.warning(f"Could not extract token from {name} logs")
    return None


def create_dev_config(tokens: dict[str, str]) -> None:
    """Create a development config.yaml with extracted tokens."""
    config_path = Path("config.yaml")

    config = {
        "vaults": [
            {
                "name": "dev-openbao",
                "address": "http://localhost:8200",
                "token": tokens.get("openbao-dev", "REPLACE_WITH_ACTUAL_TOKEN"),
                "mount_path": "secret",
                "verify_ssl": False,
            },
            {
                "name": "dev-vault",
                "address": "http://localhost:8201",
                "token": tokens.get("dev-vault", "REPLACE_WITH_ACTUAL_TOKEN"),
                "mount_path": "secret",
                "verify_ssl": False,
            },
        ]
    }

    import yaml
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Created development config at {config_path}")


def main():
    """Main setup function."""
    logger.info("Setting up Chronowarden development environment...")

    tokens = {}

    for container_name, config in CONTAINERS.items():
        logger.info(f"Checking {container_name}...")

        container_was_started = False
        if not is_container_running(container_name):
            logger.info(f"{container_name} is not running, starting it...")
            if not start_container(config):
                logger.error(f"Failed to start {container_name}")
                sys.exit(1)
            container_was_started = True
        else:
            logger.info(f"{container_name} is already running")

        # Wait for readiness (longer timeout if we just started it)
        readiness_timeout = 45 if container_was_started else 30
        if not wait_for_container_ready(container_name, config["ready_pattern"], readiness_timeout):
            logger.error(f"{container_name} failed readiness check")
            sys.exit(1)

        # Extract token
        token = extract_token_from_logs(container_name, config["token_pattern"])
        if token:
            tokens[container_name] = token

    # Create config
    create_dev_config(tokens)

    logger.info("Development setup complete!")
    logger.info("You can now run: uv run uvicorn chronowarden:app --reload")


if __name__ == "__main__":
    main()