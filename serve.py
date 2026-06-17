#!/usr/bin/env python3
"""Local development server for latinprayers.org.

Builds the site into dist/ and serves it over HTTP. With --watch, it rebuilds
automatically whenever a source file (data/, templates/, assets/, build.py)
changes — handy while iterating on layout and styling. Standard library only.

Usage:
    python3 serve.py                 # build once, serve dist/ at :8000
    python3 serve.py --port 8080     # serve on a different port
    python3 serve.py --watch         # rebuild on source changes
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import build

ROOT = Path(__file__).resolve().parent
WATCH_DIRS = (build.TEMPLATE_DIR, build.ASSETS_DIR)
WATCH_FILES = (build.DATA_FILE, ROOT / "build.py")


def snapshot() -> dict[Path, float]:
    """Map every watched source file to its modification time."""
    state: dict[Path, float] = {}
    for directory in WATCH_DIRS:
        if directory.is_dir():
            for path in directory.rglob("*"):
                if path.is_file():
                    state[path] = path.stat().st_mtime
    for path in WATCH_FILES:
        if path.is_file():
            state[path] = path.stat().st_mtime
    return state


def safe_build() -> bool:
    """Build, surviving content errors so the watch server stays up."""
    try:
        build.build()
        return True
    except SystemExit as exc:  # build.fail() exits; keep serving the last good build
        sys.stderr.write(f"  build failed ({exc}) — fix the source and save again\n")
        return False


def watch_loop(interval: float = 0.5) -> None:
    last = snapshot()
    while True:
        time.sleep(interval)
        current = snapshot()
        if current != last:
            print("Change detected — rebuilding…")
            safe_build()
            last = current


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and serve latinprayers.org locally.")
    parser.add_argument("--port", type=int, default=8000, help="port to serve on (default: 8000)")
    parser.add_argument("--host", default="127.0.0.1", help="host to bind (default: 127.0.0.1)")
    parser.add_argument("--watch", action="store_true", help="rebuild on source changes")
    args = parser.parse_args()

    print("Building site…")
    if not safe_build() and not build.DIST_DIR.is_dir():
        sys.exit("serve.py: nothing to serve — initial build failed.")

    if args.watch:
        threading.Thread(target=watch_loop, daemon=True).start()
        print("Watching data/, templates/, assets/, build.py for changes…")

    handler = partial(SimpleHTTPRequestHandler, directory=str(build.DIST_DIR))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {build.DIST_DIR.name}/ at http://{args.host}:{args.port}/  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
