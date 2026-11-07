# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""Files only their owner may read: the dev config, run.json and dev credentials."""

import os
from pathlib import Path


def write_private(path: Path, text: str) -> Path:
    """Write `text` to `path` with mode 0600, never through a symlink; an existing file is truncated and narrowed."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(text)
    path.chmod(0o600)  # an existing file keeps its mode through O_TRUNC
    return path
