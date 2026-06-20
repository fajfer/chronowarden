# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the (HashiCorp/OpenBao) Vault integration."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from hvac.exceptions import Forbidden, InvalidRequest, VaultError
from requests.models import Response

from chronowarden.integrations.vault import VaultIntegration


def _make_response(status_code: int, json_data: dict) -> Response:
    """Build a request.Response with a JSON body, mirroring Vault's behaviour."""
    response = Response()
    response.status_code = status_code
    response._content = json.dumps(json_data).encode("utf-8")
    return response


class TestCheckHealth:
    """Tests for the VaultIntegration.check_health() method."""

    def _integration(self) -> VaultIntegration:
        return VaultIntegration(address="http://example.com:8200")

    def test_not_connected(self) -> None:
        """Health check without a client reports not connected."""
        integration = self._integration()
        assert integration.check_health() == {"healthy": False, "error": "Not connected"}

    def test_returns_dict_payload(self) -> None:
        """A parsed dict payload (HTTP 200 path) is mapped to the health fields."""
        integration = self._integration()
        integration._client = MagicMock()
        integration._client.sys.read_health_status.return_value = {
            "initialized": True,
            "sealed": False,
            "version": "1.16.0",
        }

        result = integration.check_health()

        assert result == {
            "healthy": True,
            "initialized": True,
            "sealed": False,
            "version": "1.16.0",
        }

    def test_returns_raw_response_on_standby(self) -> None:
        """Regression: hvac returns a raw Response for non-200 (e.g. standby) nodes.

        Previously this raised ''AttributeError: 'Response' object has no attribute 'get''.
        and surfaced as a 500 Internal Server Error in the API.
        """
        integration = self._integration()
        integration._client = MagicMock()
        integration._client.sys.read_health_status.return_value = _make_response(
            429,
            {
                "initialized": True,
                "sealed": False,
                "version": "1.16.0",
            },
        )

        result = integration.check_health()

        assert result == {
            "healthy": True,
            "initialized": True,
            "sealed": False,
            "version": "1.16.0",
        }

    def test_returns_raw_response_when_sealed(self) -> None:
        """A sealed node (HTTP 503) is reported via the raw Response path."""
        integration = self._integration()
        integration._client = MagicMock()
        integration._client.sys.read_health_status.return_value = _make_response(
            503,
            {
                "initialized": True,
                "sealed": True,
                "version": "1.16.0",
            },
        )

        result = integration.check_health()

        assert result["healthy"] is True
        assert result["sealed"] is True

    def test_vault_error_is_Handled(self) -> None:
        """If hvac raises VaultError (e.g. connection failure), it is caught and reported."""
        integration = self._integration()
        integration._client = MagicMock()
        integration._client.sys.read_health_status.side_effect = VaultError("Connection failed")

        result = integration.check_health()

        assert result["healthy"] is False
        assert result["error"].startswith("Connection failed")


class TestConnect:
    """Tests for the VaultIntegration.connect() method."""

    def test_approle_invalid_credentials_are_reported_as_auth_error(self) -> None:
        """Invalid AppRole credentials are captured as an authentication failure."""
        integration = VaultIntegration(
            address="http://localhost:8202",
            auth_method="approle",
            role_id="rid",
            secret_id="sid",
            approle_mount_point="chronowarden",
        )
        mock_client = MagicMock()
        mock_client.auth.approle.login.side_effect = InvalidRequest(
            "invalid role or secret ID",
            method="post",
            url="http://localhost:8202/v1/auth/chronowarden/login",
        )

        with patch("chronowarden.integrations.vault.hvac.Client", return_value=mock_client):
            connected = integration.connect()

        assert connected is False
        assert integration.last_error_kind == "auth"
        assert integration.last_error is not None
        assert "invalid role_id or secret_id" in integration.last_error


class TestPermissionDeniedLogging:
    """Regression tests for 403 handling.

    A permission denied (HTTP 403) from Vault must be caught, downgraded to a
    safe return value, and logged with an actionable, policy-oriented message
    naming the mount ad the missing capability.
    """

    def _integration(self) -> VaultIntegration:
        return VaultIntegration(address="http://example.com:8200")

    def test_list_secrets_forbidden(self, caplog: pytest.LogCaptureFixture) -> None:
        """list_secrets returns [] and logs the missing 'list' capability"""
        integration = self._integration()
        integration._client = MagicMock()
        integration._client.secrets.kv.v2.list_secrets.side_effect = Forbidden("Permission denied")

        with caplog.at_level(logging.ERROR):
            secrets = integration.list_secrets("", mount_point="apps")

        assert secrets == []
        assert "Permission denied listing secrets" in caplog.text
        assert "apps/metadata" in caplog.text

    def test_get_secret_metadata_forbidden(self, caplog: pytest.LogCaptureFixture) -> None:
        """get_secret_metadata returns None and logs the missing 'read' capability"""
        integration = self._integration()
        integration._client = MagicMock()
        integration._client.secrets.kv.v2.read_secret_metadata.side_effect = Forbidden("Permission denied")

        with caplog.at_level(logging.ERROR):
            metadata = integration.get_secret_metadata("db", mount_point="apps")

        assert metadata is None
        assert "Permission denied reading metadata" in caplog.text
        assert "apps/metadata" in caplog.text

    def test_write_secret_metadata_forbidden(self, caplog: pytest.LogCaptureFixture) -> None:
        """write_secret_metadata returns False and logs the missing 'update' capability"""
        integration = self._integration()
        integration._client = MagicMock()
        integration._client.secrets.kv.v2.update_metadata.side_effect = Forbidden("Permission denied")

        with caplog.at_level(logging.ERROR):
            result = integration.write_secret_metadata("db", {"chronowarden_severity": "critical"}, mount_point="apps")

        assert result is False
        assert "Permission denied writing metadata" in caplog.text
        assert "apps/metadata" in caplog.text

    def test_discover_engines_forbidden(self, caplog: pytest.LogCaptureFixture) -> None:
        """discover_engines returns [] and logs the missing 'read' capability on sys/mounts"""
        integration = self._integration()
        integration._client = MagicMock()
        integration._client.sys.list_mounted_secrets_engines.side_effect = Forbidden("Permission denied")

        with caplog.at_level(logging.ERROR):
            engines = integration.discover_engines()

        assert engines == []
        assert "Permission denied discovering secret engines" in caplog.text
        assert "sys/mounts" in caplog.text


class TestListSecretsNullKeys:
    """Regression tests for Vault returning null for the 'keys' field."""

    def _integration(self) -> VaultIntegration:
        return VaultIntegration(address="http://example.com:8200")

    def test_list_secrets_null_keys_returns_empty_list(self) -> None:
        """list_secrets returns [] when Vault API responds with null for 'keys'."""
        integration = self._integration()
        integration._client = MagicMock()
        integration._client.secrets.kv.v2.list_secrets.return_value = {"data": {"keys": None}}

        secrets = integration.list_secrets("some/path", mount_point="apps")

        assert secrets == []
