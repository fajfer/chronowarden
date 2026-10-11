#!/bin/bash -eu
# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

# The builder runs Python 3.11 while the project declares 3.12+; the fuzzed code imports and runs on 3.11.
# Install exactly the runtime versions from uv.lock, then the package itself without the version check.
pip3 install --require-hashes -r .clusterfuzzlite/requirements.txt
uv export --no-dev --no-emit-project --no-hashes --frozen --quiet > /tmp/locked.txt
uv pip install --system --python python3 -r /tmp/locked.txt
pip3 install --no-deps --ignore-requires-python .

for fuzzer in fuzz/fuzz_*.py; do
  compile_python_fuzzer "$fuzzer"
done
