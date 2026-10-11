# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Fuzz load_config: any file content gives an AppConfig or a ConfigError, nothing else."""

import logging
import os
import sys
import tempfile

import atheris

with atheris.instrument_imports():
    from chronowarden.config import AppConfig, ConfigError, load_config

logging.disable(logging.CRITICAL)
os.environ.pop("CHRONOWARDEN_THEME", None)
CONFIG_FILE = os.path.join(tempfile.mkdtemp(prefix="fuzz-config-"), "config.yaml")


def TestOneInput(data: bytes) -> None:
    """Load fuzzed bytes as the config file."""
    with open(CONFIG_FILE, "wb") as config_file:
        config_file.write(data)
    try:
        assert isinstance(load_config(CONFIG_FILE), AppConfig)
    except ConfigError:
        pass


def main() -> None:
    """Run the fuzzer."""
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
