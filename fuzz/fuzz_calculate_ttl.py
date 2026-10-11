# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Fuzz calculate_ttl: any updated_time and severity give a date string or None, never raise."""

import logging
import sys

import atheris

with atheris.instrument_imports():
    from chronowarden.config import AppConfig
    from chronowarden.metadata import calculate_ttl, parse_date

logging.disable(logging.CRITICAL)
CONFIGS = [AppConfig(), AppConfig(date_format="YYYY-DD-MM")]


def TestOneInput(data: bytes) -> None:
    """Calculate a TTL from fuzzed input; a result must be a date parse_date reads back."""
    fdp = atheris.FuzzedDataProvider(data)
    config = fdp.PickValueInList(CONFIGS)
    severity = fdp.PickValueInList(["default", "critical", "pci-dss-4.0", "none", fdp.ConsumeUnicodeNoSurrogates(16)])
    result = calculate_ttl(fdp.ConsumeUnicodeNoSurrogates(64), severity, config)
    assert result is None or parse_date(result, config.date_format) is not None


def main() -> None:
    """Run the fuzzer."""
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
