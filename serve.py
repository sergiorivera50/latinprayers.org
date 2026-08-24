#!/usr/bin/env python3
"""Local development server for latinprayers.org.

Builds the site into dist/ and serves it over HTTP. With --watch, it rebuilds
automatically whenever a source file (data/, templates/, assets/, build.py)
changes — handy while iterating on layout and styling. Standard library only.

Usage:
    python3 serve.py                 # build once, serve dist/ at :8000
    python3 serve.py --port 8080     # serve on a different port
    python3 serve.py --watch         # rebuild on source changes
    python3 serve.py --no-studio     # leave the prayer editor unmounted

The Prayer Studio is mounted at /_studio/ by default, because a local dev server
for this site is a thing you run in order to work on the content. It is left off
when the bind address is not loopback (the editor writes to data/prayers.csv, so
it is not offered to the network) and can be turned off explicitly.
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
import studio

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
    """Build, surviving content errors so the watch server stays up.

    Holds studio.BUILD_LOCK because a studio save can ask for a rebuild at the
    same moment this watcher does, and build() wipes dist/ before writing it."""
    try:
        with studio.BUILD_LOCK:
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
    parser.add_argument("--no-studio", action="store_true",
                        help="do not mount the prayer editor (it is mounted by default)")
    args = parser.parse_args()

    # The studio writes to data/prayers.csv, so it is never offered to the
    # network. Binding elsewhere (say 0.0.0.0, to check the site on a phone) is
    # still perfectly reasonable, so that turns the editor off rather than
    # refusing to start. The handler re-checks per request regardless.
    loopback = args.host in ("127.0.0.1", "::1", "localhost")
    with_studio = not args.no_studio and loopback

    print("Building site…")
    if not safe_build() and not build.DIST_DIR.is_dir():
        sys.exit("serve.py: nothing to serve — initial build failed.")

    if args.watch:
        threading.Thread(target=watch_loop, daemon=True).start()
        print("Watching data/, templates/, assets/, build.py for changes…")

    base = studio.StudioHandler if with_studio else SimpleHTTPRequestHandler
    handler = partial(base, directory=str(build.DIST_DIR))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {build.DIST_DIR.name}/ at http://{args.host}:{args.port}/  (Ctrl-C to stop)")
    if with_studio:
        print(f"Prayer Studio at http://{args.host}:{args.port}{studio.MOUNT}/  "
              f"(local only, edits {studio.DATA_FILE.name})")
    elif not loopback:
        print(f"Prayer Studio not mounted: {args.host} is not loopback.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
