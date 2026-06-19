# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the (HashiCorp/OpenBao) Vault integration."""

import json
from unittest.mock import MagicMock, patch

from hvac.exceptions import InvalidRequest, VaultError
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
