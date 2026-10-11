# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Fuzz parse_date: any string returns a datetime or None, never raises."""

import logging
import sys
from datetime import datetime

import atheris

with atheris.instrument_imports():
    from chronowarden.metadata import format_date, parse_date

logging.disable(logging.CRITICAL)
FORMATS = ["YYYY-MM-DD", "YYYY-DD-MM"]


def TestOneInput(data: bytes) -> None:
    """Parse a fuzzed string; a parsed date must survive a format/parse round trip."""
    fdp = atheris.FuzzedDataProvider(data)
    date_format = fdp.PickValueInList(FORMATS)
    result = parse_date(fdp.ConsumeUnicodeNoSurrogates(64), date_format)
    assert result is None or isinstance(result, datetime)
    if result is not None:
        assert parse_date(format_date(result, date_format), date_format) is not None


def main() -> None:
    """Run the fuzzer."""
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
