# SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Base integration interface for secret engines."""

from typing import Any, Optional

from pydantic import BaseModel


class BaseIntegration(BaseModel):
    """Abstract base class for secret engine integrations."""

    def connect(self) -> bool:
        """
        Establish connection to the secret backend.

        Returns:
            bool: True if connection successful, False otherwise.
        """
        pass

    def disconnect(self) -> None:
        """Close connection to the secret backend."""
        pass

    def get_secret(self, path: str, key: Optional[str] = None) -> Optional[dict[str, Any]]:
        """
        Retrieve a secret from the backend.

        Args:
            path: Path to the secret.
            key: Optional specific key within the secret.

        Returns:
            The secret data or None if not found.
        """
        pass

    def list_secrets(self, path: str) -> list[str]:
        """
        List secrets at the given path.

        Args:
            path: Path to list secrets from.

        Returns:
            List of secret names/paths.
        """
        pass

    def is_connected(self) -> bool:
        """
        Check if the integration is connected.

        Returns:
            bool: True if connected, False otherwise.
        """
        pass

    def get_secret_metadata(self, path: str) -> Optional[dict[str, Any]]:
        """
        Get metadata about a secret (creation time, version, etc.).

        Args:
            path: Path to the secret.

        Returns:
            Metadata dictionary or None if not found.
        """
        pass
