# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Chronowarden against real OpenBao and HashiCorp Vault dev servers (#78). Run with: pytest -m integration."""

import time
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import hvac
import pytest
from requests.exceptions import RequestException
from testcontainers.core.container import DockerContainer

from chronowarden.config import AppConfig
from chronowarden.database import Database
from chronowarden.integrations.vault import VaultIntegration
from chronowarden.metadata import detect_changes
from devenv.backends import APPROLE_MOUNT, BACKENDS, Backend, random_token, seed, setup_approle

pytestmark = pytest.mark.integration


class Running(NamedTuple):
    """A started backend: root client and Chronowarden's AppRole integration."""

    backend: Backend
    root: hvac.Client
    integration: VaultIntegration


def _wait(address: str, token: str, timeout: float = 60) -> hvac.Client:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        client = hvac.Client(url=address, token=token)
        try:
            if client.is_authenticated():
                return client
        except (RequestException, hvac.exceptions.VaultError):
            pass
        time.sleep(0.5)
    raise TimeoutError(f"{address} didn't come up")


@pytest.fixture(scope="module", params=BACKENDS, ids=[b.container for b in BACKENDS])
def running(request: pytest.FixtureRequest) -> Iterator[Running]:
    backend: Backend = request.param
    token = random_token()
    container = DockerContainer(backend.image).with_env(backend.root_token_env, token).with_exposed_ports(backend.port)
    for key, value in backend.extra_env:
        container = container.with_env(key, value)
    if backend.cap_add:
        container = container.with_kwargs(cap_add=list(backend.cap_add))
    with container:
        address = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(backend.port)}"
        root = _wait(address, token)
        seed(root)
        role_id, secret_id = setup_approle(root)
        integration = VaultIntegration(
            address=address,
            auth_method="approle",
            role_id=role_id,
            secret_id=secret_id,
            approle_mount_point=APPROLE_MOUNT,
            verify_ssl=False,
        )
        assert integration.connect(), integration.last_error
        yield Running(backend, root, integration)


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "test.db")
    database.connect()
    yield database
    database.close()


def _sync(running: Running, db: Database) -> None:
    detect_changes(running.integration, running.backend.config_name, AppConfig(), db)


def _metadata(running: Running, engine: str, path: str) -> dict:
    return running.root.secrets.kv.v2.read_secret_metadata(path=path, mount_point=engine)["data"]


def test_discovers_the_seeded_engines(running: Running) -> None:
    paths = {engine["path"] for engine in running.integration.discover_engines()}
    assert {"apps", "databases", "services"} <= paths


def test_sync_keeps_other_metadata_and_settings(running: Running, db: Database) -> None:
    """Regression for 0.6.3: writing chronowarden_* keys must not wipe other keys or delete_version_after."""
    running.root.secrets.kv.v2.update_metadata(
        path="secret-1", mount_point="apps", custom_metadata={"owner_team": "payments"}, delete_version_after="720h"
    )
    _sync(running, db)
    metadata = _metadata(running, "apps", "secret-1")
    assert metadata["custom_metadata"]["owner_team"] == "payments"
    assert metadata["custom_metadata"]["chronowarden_severity"] == "default"
    assert metadata["delete_version_after"].startswith("720h")


def test_deleted_secret_is_marked_removed_and_comes_back(running: Running, db: Database) -> None:
    _sync(running, db)
    running.root.secrets.kv.v2.delete_metadata_and_all_versions(path="secret-5", mount_point="services")
    _sync(running, db)
    entry = db.get_secret_metadata(running.backend.config_name, "services", "secret-5")
    assert entry is not None and entry.removed_at is not None
    running.root.secrets.kv.v2.create_or_update_secret(path="secret-5", mount_point="services", secret={"k": "v"})
    _sync(running, db)
    entry = db.get_secret_metadata(running.backend.config_name, "services", "secret-5")
    assert entry is not None and entry.removed_at is None


def test_privileged_write_merges(running: Running, db: Database) -> None:
    _sync(running, db)
    assert running.integration.write_secret_metadata(
        "secret-2", {"chronowarden_privileged": "true"}, mount_point="apps"
    )
    _sync(running, db)
    entry = db.get_secret_metadata(running.backend.config_name, "apps", "secret-2")
    assert entry is not None and entry.privileged
    assert _metadata(running, "apps", "secret-2")["custom_metadata"]["chronowarden_severity"] == "default"


def test_rotation_is_observed(running: Running, db: Database) -> None:
    _sync(running, db)
    running.root.secrets.kv.v2.create_or_update_secret(path="secret-3", mount_point="databases", secret={"k": "new"})
    _sync(running, db)
    events = db.list_audit_events(event_type="secret.version", secret_path="secret-3", engine_id="databases")
    assert events, "a new version is recorded as a rotation"
