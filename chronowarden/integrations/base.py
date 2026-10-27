# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""The interface every secret provider implements (ADR-011); metadata only, never secret values (ADR-004)."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseIntegration(ABC):
    """
    A connection to one secret backend.

    A provider missing any abstract member can't be instantiated. Metadata is returned in the KV v2 shape sync
    reads: `custom_metadata` (the backend's per-secret key/value metadata), `created_time`, `updated_time`,
    `current_version` and `versions` (version number → `created_time`, `deletion_time`, `destroyed`).
    """

    @property
    @abstractmethod
    def address(self) -> str:
        """Where the backend is, as shown to operators (URL or resource name)."""

    @property
    @abstractmethod
    def last_error(self) -> Optional[str]:
        """The message of the last connection failure, if any."""

    @property
    @abstractmethod
    def last_error_kind(self) -> Optional[str]:
        """`auth` (not retried), `offline`, `vault` or `unexpected` (retried by the reconnect loop), or None."""

    @abstractmethod
    def connect(self) -> bool:
        """
        Authenticate and connect; blocking.

        Returns:
            True if connected; otherwise `last_error` and `last_error_kind` say why.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Drop the connection and forget any session credentials."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the connection and its credentials still work; blocking, never raises."""

    @abstractmethod
    def list_secrets(self, path: str, mount_point: Optional[str] = None, strict: bool = False) -> list[str]:
        """
        List secret names under a path; names ending in `/` are folders.

        Args:
            path: Folder to list ("" for the top).
            mount_point: The engine (Vault mount, key vault, project) to list in, instead of the default.
            strict: Raise on errors instead of returning [], so a failed listing never looks like deleted secrets.

        Returns:
            Names relative to `path`.
        """

    @abstractmethod
    def get_secret_metadata(self, path: str, mount_point: Optional[str] = None) -> Optional[dict[str, Any]]:
        """
        Read a secret's metadata (see the class docstring for the shape); never its value.

        Returns:
            The metadata, or None if the secret doesn't exist or can't be read.
        """

    @abstractmethod
    def write_secret_metadata(
        self, path: str, custom_metadata: dict[str, str], mount_point: Optional[str] = None
    ) -> bool:
        """
        Merge `chronowarden_*` keys into a secret's custom metadata, keeping every other key (ADR-006).

        Returns:
            True if written.
        """

    @abstractmethod
    def discover_engines(self) -> list[dict[str, Any]]:
        """
        The engines this backend holds secrets in.

        Returns:
            One dict per engine with at least `path` (passed as `mount_point`) and `type`.
        """

    @abstractmethod
    def check_health(self) -> dict[str, Any]:
        """
        Backend health for operators.

        Returns:
            At least `healthy` (bool); `error` when unhealthy.
        """
