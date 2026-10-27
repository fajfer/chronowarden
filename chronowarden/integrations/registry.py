# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Provider types and how to build each from its config entry (ADR-011)."""

from collections.abc import Callable
from typing import Any, Optional

from chronowarden.integrations.base import BaseIntegration

# (backend config entry, CA bundle path or None) -> the integration, or None when a credential can't be resolved
ProviderBuilder = Callable[[Any, Optional[str]], Optional[BaseIntegration]]

_PROVIDERS: dict[str, ProviderBuilder] = {}


def register_provider(provider_type: str, builder: ProviderBuilder) -> None:
    """
    Make a provider type available to `type:` in config.

    Args:
        provider_type: The value of `type:` in a `vaults:` entry, e.g. `vault`.
        builder: Builds the integration from that entry.

    Raises:
        ValueError: If the type is registered already.
    """
    if provider_type in _PROVIDERS:
        raise ValueError(f"Provider type '{provider_type}' is registered already")
    _PROVIDERS[provider_type] = builder


def build_provider(config: Any, ca_bundle: Optional[str]) -> Optional[BaseIntegration]:
    """
    Build the integration for one backend entry, by its `type`.

    Raises:
        KeyError: For a type nothing registered (config validation should have refused it).
    """
    return _PROVIDERS[config.type](config, ca_bundle)


def provider_types() -> list[str]:
    """The registered provider types, sorted."""
    return sorted(_PROVIDERS)
