# SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
#
# SPDX-License-Identifier: EUPL-1.2

"""
A local webhook receiver for dev runs: answers 200 and appends every request to a JSON Lines file.

Run as `python -m devenv.receiver --port <port> --out <file>`; dev-setup.py starts it for `--receiver`.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


def record(path: Path, request_path: str, headers: dict[str, str], body: bytes) -> None:
    """Append one request to `path` as a JSON line (body as text, undecodable bytes replaced)."""
    entry = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "path": request_path,
        "headers": headers,
        "body": body.decode("utf-8", errors="replace"),
    }
    with path.open("a") as file:
        file.write(json.dumps(entry) + "\n")


def make_server(port: int, out: Path) -> HTTPServer:
    """A server on 127.0.0.1:`port` (0 = any free port) recording to `out`."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (http.server's naming)
            length = int(self.headers.get("Content-Length") or 0)
            record(out, self.path, dict(self.headers), self.rfile.read(length))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            pass  # the JSON Lines file is the log

    return HTTPServer(("127.0.0.1", port), Handler)


def main() -> int:
    """Serve until killed."""
    parser = argparse.ArgumentParser(description="Record webhook requests to a JSON Lines file.")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    make_server(args.port, args.out).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
