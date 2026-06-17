# SPDX-FileCopyrightText: 2025-2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Tests for the (HashiCorp/OpenBao) Vault integration."""

import json
from unittest.mock import MagicMock

from hvac.exceptions import VaultError
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

        assert result == {"healthy": False, "error": "Connection failed"}
