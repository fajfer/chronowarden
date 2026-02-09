#!/usr/bin/env -S uv run
# /// script
# dependencies = ["hvac>=2.3.0", "pyyaml>=6.0.0"]
# ///
# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""
Development setup script for Chronowarden.

This script ensures that development Vault instances are running and
creates a config.yaml with extracted tokens for local development.
"""

import logging
import random
import re
import string
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import hvac

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Container configurations
CONTAINERS = {
    "openbao-dev": {
        "image": "quay.io/openbao/openbao:2.5.0",
        "ports": ["127.0.0.1:8200:8200"],
        "name": "openbao-dev",
        "token_pattern": r"Root Token:\s*([a-zA-Z0-9._-]+)",
        "ready_pattern": r"OpenBao server started",
    },
    "dev-vault-1.21.3": {
        "image": "hashicorp/vault:1.21.3",
        "ports": ["127.0.0.1:8201:8201"],
        "name": "dev-vault-1.21.3",
        "env": ["VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8201"],
        "cap_add": ["IPC_LOCK"],
        "token_pattern": r"Root Token:\s*([a-zA-Z0-9._-]+)",
        "ready_pattern": r"Vault server started",
    },
    "dev-vault-1.20.1": {
        "image": "hashicorp/vault:1.20.1",
        "ports": ["127.0.0.1:8202:8202"],
        "name": "dev-vault-1.20.1",
        "env": ["VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8202"],
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


def create_dev_config(approle_credentials: dict[str, tuple[str, str]]) -> None:
    """Create a development config.yaml with AppRole authentication."""
    config_path = Path("config.yaml")

    config = {
        "vaults": [
            {
                "name": "dev-openbao",
                "address": "http://localhost:8200",
                "auth_method": "approle",
                "role_id": approle_credentials.get("openbao-dev", ("", ""))[0],
                "secret_id": approle_credentials.get("openbao-dev", ("", ""))[1],
                "verify_ssl": False,
                "severity": "default",
            },
            {
                "name": "dev-vault-1.21.3",
                "address": "http://localhost:8201",
                "auth_method": "approle",
                "role_id": approle_credentials.get("dev-vault-1.21.3", ("", ""))[0],
                "secret_id": approle_credentials.get("dev-vault-1.21.3", ("", ""))[1],
                "verify_ssl": False,
                "severity": "critical",
            },
            {
                "name": "dev-vault-1.20.1",
                "address": "http://localhost:8202",
                "auth_method": "approle",
                "role_id": approle_credentials.get("dev-vault-1.20.1", ("", ""))[0],
                "secret_id": approle_credentials.get("dev-vault-1.20.1", ("", ""))[1],
                "verify_ssl": False,
                "severity": "default",
            },
        ]
    }

    import yaml
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Created development config at {config_path}")


def generate_random_string(length: int = 16) -> str:
    """Generate a random string for passwords."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(random.choice(chars) for _ in range(length))


def generate_random_username() -> str:
    """Generate a random username."""
    adjectives = ["happy", "clever", "bright", "swift", "calm", "brave", "wise", "cool", "wild", "bold"]
    nouns = ["tiger", "eagle", "wolf", "fox", "bear", "lion", "hawk", "shark", "panda", "dragon"]
    return f"{random.choice(adjectives)}_{random.choice(nouns)}_{random.randint(100, 999)}"


def generate_random_url() -> str:
    """Generate a random URL."""
    protocols = ["https"]
    domains = ["example.com", "test.org", "demo.net", "app.io", "service.dev"]
    paths = ["/api", "/admin", "/dashboard", "/portal", "/console", "/app"]
    return f"{random.choice(protocols)}://{random.choice(domains)}{random.choice(paths)}"


def create_chronowarden_policy(client: hvac.Client) -> None:
    """Create the chronowarden policy in the vault."""
    policy = """
# Read, list, and update metadata for all KV v2 mounts
# Chronowarden manages custom_metadata fields (chronowarden_ttl, chronowarden_severity, chronowarden_enabled)
path "secret/metadata/*" {
  capabilities = ["read", "list", "update"]
}

path "apps/metadata/*" {
  capabilities = ["read", "list", "update"]
}

path "databases/metadata/*" {
  capabilities = ["read", "list", "update"]
}

path "services/metadata/*" {
  capabilities = ["read", "list", "update"]
}

# Allow listing mount points for engine discovery
path "sys/mounts" {
  capabilities = ["read"]
}
"""
    client.sys.create_or_update_policy(
        name="chronowarden",
        policy=policy,
    )
    logger.info("  Created chronowarden policy")


def setup_approle(client: hvac.Client) -> tuple[str, str]:
    """
    Set up AppRole authentication and return (role_id, secret_id).
    
    Returns:
        Tuple of (role_id, secret_id) for AppRole authentication
    """
    # Enable AppRole auth method
    try:
        client.sys.enable_auth_method("approle")
        logger.info("  Enabled AppRole auth method")
    except hvac.exceptions.InvalidRequest:
        logger.info("  AppRole auth method already enabled")

    # Create the AppRole
    client.auth.approle.create_or_update_approle(
        role_name="chronowarden",
        token_policies=["chronowarden"],
        token_ttl="1h",
        token_max_ttl="24h",
        secret_id_ttl="0",
        secret_id_num_uses=0,
        bind_secret_id=True,
    )
    logger.info("  Created chronowarden AppRole")

    # Get role_id
    role_id = client.auth.approle.read_role_id(role_name="chronowarden")["data"]["role_id"]
    
    # Generate secret_id
    secret_id_response = client.auth.approle.generate_secret_id(role_name="chronowarden")
    secret_id = secret_id_response["data"]["secret_id"]
    
    logger.info(f"  Generated AppRole credentials (role_id: {role_id[:8]}...)")
    
    return role_id, secret_id


def login_with_approle(address: str, role_id: str, secret_id: str) -> Optional[str]:
    """
    Login to Vault using AppRole and return the client token.
    
    Returns:
        Client token string or None on failure
    """
    try:
        client = hvac.Client(url=address, verify=False)
        login_response = client.auth.approle.login(
            role_id=role_id,
            secret_id=secret_id,
        )
        token = login_response["auth"]["client_token"]
        logger.info(f"  Successfully logged in with AppRole (token: {token[:8]}...)")
        return token
    except Exception:
        logger.exception("Failed to login with AppRole")
        return None


def populate_vault(vault_name: str, address: str, token: str) -> None:
    """Populate a vault with secret engines and secrets."""
    logger.info(f"Populating {vault_name}...")

    try:
        client = hvac.Client(url=address, token=token, verify=False)
        if not client.is_authenticated():
            logger.error(f"Failed to authenticate to {vault_name}")
            return

        # Define 3 secret engines
        engines = ["apps", "databases", "services"]

        for engine in engines:
            # Enable KV v2 secrets engine
            try:
                client.sys.enable_secrets_engine(
                    backend_type="kv",
                    path=engine,
                    options={"version": "2"},
                )
                logger.info(f"  Enabled secret engine: {engine}")
            except hvac.exceptions.InvalidRequest:
                logger.info(f"  Secret engine {engine} already exists, skipping")

            # Create 5 secrets in each engine
            for i in range(1, 6):
                secret_path = f"secret-{i}"
                secret_data = {
                    "username": generate_random_username(),
                    "password": generate_random_string(),
                    "url": generate_random_url(),
                }

                client.secrets.kv.v2.create_or_update_secret(
                    path=secret_path,
                    secret=secret_data,
                    mount_point=engine,
                )
                logger.info(f"    Created secret: {engine}/{secret_path}")

        logger.info(f"Successfully populated {vault_name} with {len(engines)} engines and {len(engines) * 5} secrets")

    except Exception:
        logger.exception(f"Error populating {vault_name}")


def main():
    """Main setup function."""
    logger.info("Setting up Chronowarden development environment...")

    root_tokens = {}
    approle_credentials: dict[str, tuple[str, str]] = {}

    vault_addresses = {
        "openbao-dev": "http://localhost:8200",
        "dev-vault-1.21.3": "http://localhost:8201",
        "dev-vault-1.20.1": "http://localhost:8202",
    }

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

        # Extract root token
        root_token = extract_token_from_logs(container_name, config["token_pattern"])
        if root_token:
            root_tokens[container_name] = root_token

    # Populate vaults with test data and set up AppRole
    logger.info("Setting up vaults with AppRole authentication...")

    for container_name, root_token in root_tokens.items():
        if root_token and container_name in vault_addresses:
            address = vault_addresses[container_name]
            
            # Populate vault with secrets
            populate_vault(container_name, address, root_token)
            
            # Set up AppRole authentication
            try:
                client = hvac.Client(url=address, token=root_token, verify=False)
                if not client.is_authenticated():
                    logger.error(f"Failed to authenticate to {container_name}")
                    continue
                
                # Create policy and AppRole
                create_chronowarden_policy(client)
                role_id, secret_id = setup_approle(client)
                approle_credentials[container_name] = (role_id, secret_id)
                logger.info(f"AppRole credentials stored for {container_name}")
                    
            except Exception:
                logger.exception(f"Error setting up AppRole for {container_name}")

    # Create config with AppRole credentials
    create_dev_config(approle_credentials)

    logger.info("\n" + "="*70)
    logger.info("Development setup complete!")
    logger.info("="*70)
    logger.info("\nRoot tokens (for emergency access only):")
    for container_name, root_token in root_tokens.items():
        logger.info(f"  {container_name}: {root_token}")
    logger.info("\nConfig file created with AppRole credentials for secure access.")
    logger.info("Vaults configured with auth_method: approle (direct role_id/secret_id).")
    logger.info("You can now run: uv run uvicorn chronowarden:app --reload")
    logger.info("="*70 + "\n")


if __name__ == "__main__":
    main()