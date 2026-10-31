# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""The two dev backends Chronowarden is tested against, and their seed data."""

import random
import secrets
import string
from dataclasses import dataclass, replace

import hvac

ENGINES = ("apps", "databases", "services")
SECRETS_PER_ENGINE = 5
APPROLE_MOUNT = "chronowarden"

# The policy users grant (README "Vault Permissions"), for the dev engines
POLICY = "\n".join(
    [f'path "{engine}/metadata/*" {{\n  capabilities = ["read", "list", "update"]\n}}' for engine in ENGINES]
    + ['path "sys/mounts" {\n  capabilities = ["read"]\n}']
)


@dataclass(frozen=True)
class Backend:
    """A dev backend: image, ports and how its dev server takes a root token."""

    container: str
    config_name: str
    image: str
    port: int  # inside the container
    root_token_env: str
    severity: str
    extra_env: tuple[tuple[str, str], ...] = ()
    cap_add: tuple[str, ...] = ()
    host_port: int | None = None  # published on 127.0.0.1; defaults to `port`

    @property
    def service(self) -> str:
        """Short name in run container names: `openbao`, `vault`."""
        return self.config_name.removeprefix("dev-")

    @property
    def published_port(self) -> int:
        """The port on the host."""
        return self.port if self.host_port is None else self.host_port

    @property
    def address(self) -> str:
        """Address on the host."""
        return f"http://localhost:{self.published_port}"

    def for_run(self, container: str, host_port: int) -> "Backend":
        """This backend under another container name and host port (for a named run)."""
        return replace(self, container=container, host_port=host_port)


OPENBAO = Backend(
    container="openbao-dev",
    config_name="dev-openbao",
    image="quay.io/openbao/openbao:2.7.1",
    port=8200,
    root_token_env="BAO_DEV_ROOT_TOKEN_ID",
    severity="default",
)
VAULT = Backend(
    container="vault-dev",
    config_name="dev-vault",
    image="docker.io/hashicorp/vault:2.1.2",  # fully qualified: podman has no default registry
    port=8201,
    root_token_env="VAULT_DEV_ROOT_TOKEN_ID",
    severity="critical",
    extra_env=(("VAULT_DEV_LISTEN_ADDRESS", "0.0.0.0:8201"),),
    cap_add=("IPC_LOCK",),
)
BACKENDS = (OPENBAO, VAULT)


def random_token() -> str:
    """A throwaway dev root token (from a CSPRNG, though the server only listens on 127.0.0.1)."""
    return "dev-" + secrets.token_urlsafe(24)


def seed(client: hvac.Client) -> None:
    """
    Fill a fresh dev server: the KV v2 engines with sample secrets.

    Args:
        client: A client authenticated with the root token.
    """
    for engine in ENGINES:
        try:
            client.sys.enable_secrets_engine(backend_type="kv", path=engine, options={"version": "2"})
        except hvac.exceptions.InvalidRequest:
            pass  # already enabled on a reused container
        for i in range(1, SECRETS_PER_ENGINE + 1):
            client.secrets.kv.v2.create_or_update_secret(
                path=f"secret-{i}",
                mount_point=engine,
                secret={"username": f"user{i}", "password": "".join(random.choices(string.ascii_letters, k=16))},
            )


def setup_approle(client: hvac.Client) -> tuple[str, str]:
    """
    Create the Chronowarden policy and an AppRole for it.

    Args:
        client: A client authenticated with the root token.

    Returns:
        (role_id, secret_id).
    """
    client.sys.create_or_update_policy(name="chronowarden", policy=POLICY)
    try:
        client.sys.enable_auth_method("approle", path=APPROLE_MOUNT)
    except hvac.exceptions.InvalidRequest:
        pass  # already enabled on a reused container
    client.auth.approle.create_or_update_approle(
        role_name="chronowarden",
        token_policies=["chronowarden"],
        token_ttl="1h",
        token_max_ttl="24h",
        mount_point=APPROLE_MOUNT,
    )
    role_id = client.auth.approle.read_role_id(role_name="chronowarden", mount_point=APPROLE_MOUNT)["data"]["role_id"]
    secret_id = client.auth.approle.generate_secret_id(role_name="chronowarden", mount_point=APPROLE_MOUNT)["data"][
        "secret_id"
    ]
    return role_id, secret_id
