#!/usr/bin/env python3
"""Prayer Studio — a local-development-only editor for data/prayers.csv.

This module is DEVELOPMENT ONLY and cannot reach the published site. build.py
copies exactly three things into dist/ (assets/, CNAME, .nojekyll); the studio's
markup lives in studio/ at the repo root, outside assets/, and this module is
never imported by build.py. There is no path from here to latinprayers.org.

It is mounted by serve.py under /_studio/ when serve.py is run with --studio,
and it refuses any request that does not come from the loopback interface.

The CSV stays the source of truth. Every save re-reads data/prayers.csv from
disk, applies the one row the client asked to change, and writes the whole file
back through the stdlib csv module — so the 33 prayers you did not touch are
re-emitted byte-for-byte and never show up in the git diff. Writes are atomic
(tempfile + os.replace) and take a timestamped backup first; git remains the
real undo.

Standard library only, like the rest of the toolchain.
"""

from __future__ import annotations

import contextlib
import csv
import datetime
import difflib
import io
import json
import os
import re
import shutil
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

import build

ROOT = Path(__file__).resolve().parent
STUDIO_DIR = ROOT / "studio"
DATA_FILE = build.DATA_FILE
BACKUP_DIR = ROOT / "data" / ".studio-backups"
BACKUP_KEEP = 20

MOUNT = "/_studio"

# One build at a time. serve.py's --watch thread and a studio save can both ask
# for a rebuild, and build() wipes dist/ with rmtree before writing it; two at
# once would have one build deleting the other's output mid-write. serve.py
# acquires this same lock, which is why the lock lives here rather than there.
BUILD_LOCK = threading.Lock()

COLUMNS = ("slug", "title", "subtitle", "category", "order", "description",
           "la", "en", "context", "source", "source_url")
REQUIRED = build.REQUIRED_COLUMNS  # slug, title, subtitle, category, la, en

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EM_DASH = "—"
PROSE_COLUMNS = ("title", "subtitle", "description", "context", "source")

# The badge appears on the prayer routes only: /prayers/ and /prayers/<slug>/.
# The studio edits prayers, so that is where a way into it belongs; on the
# landing page, the Rosary or the 404 it would be a permanent ornament with
# nothing behind it. Group 1 is the slug, or None for the index.
STUDIO_ROUTE_RE = re.compile(r"^/prayers/(?:([a-z0-9-]+)/)?$")

# A corner tab slipped into those pages on their way out of serve.py, so that
# spotting a typo while reading and fixing it are one click apart. It is not in
# dist/: the built HTML on disk never contains it, so there is nothing to strip
# before publishing and nothing to forget.
BADGE_CSS = (
    "#lp-studio-badge{position:fixed;left:14px;bottom:14px;z-index:99999;"
    "display:flex;align-items:center;gap:6px;padding:7px 12px;border-radius:20px;"
    "font:550 12.5px/1.2 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
    "letter-spacing:0;color:#fff;background:#2563eb;border:1px solid #1d4ed8;"
    "text-decoration:none;box-shadow:0 2px 10px rgba(16,24,40,.35);opacity:.82;"
    "transition:opacity .15s,transform .15s}"
    "#lp-studio-badge:hover{opacity:1;transform:translateY(-1px);color:#fff}"
    "@media print{#lp-studio-badge{display:none}}"
)


def badge_html(path: str) -> str:
    """The badge markup for this route, or "" if the route does not carry one."""
    match = STUDIO_ROUTE_RE.match(path)
    if match is None:
        return ""
    slug = match.group(1)
    href = f"{MOUNT}/#{slug}" if slug else f"{MOUNT}/"
    label = "Edit this prayer" if slug else "Prayer Studio"
    return (f'<style id="lp-studio-style">{BADGE_CSS}</style>'
            f'<a id="lp-studio-badge" href="{href}" '
            f'title="Local development only — not part of the published site">'
            f'<span aria-hidden="true">\u270e</span>{label}</a>')


def inject_badge(html: str, path: str) -> str:
    badge = badge_html(path)
    if not badge or "</body>" not in html:
        return html
    return html.replace("</body>", badge + "</body>", 1)


MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


# --------------------------------------------------------------------------- #
# The CSV, read and written
# --------------------------------------------------------------------------- #
def read_table() -> tuple[list[str], list[dict]]:
    """The CSV as (fieldnames, rows-of-plain-strings).

    Rows keep the file's own column set rather than COLUMNS, so a file that has
    grown a column is round-tripped intact instead of silently reshaped.
    """
    with DATA_FILE.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or COLUMNS)
        rows = [{k: (row.get(k) or "") for k in fields} for row in reader]
    return fields, rows


def csv_text(fields: list[str], rows: list[dict]) -> str:
    """Rows back to CSV text. These settings are not arbitrary: reading
    data/prayers.csv and writing it straight back this way reproduces the file
    byte-for-byte (verified), which is what keeps untouched prayers out of the
    diff. lineterminator='\\n' matters — csv defaults to '\\r\\n'."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _backup() -> None:
    """Copy the current CSV aside before overwriting it, keeping the last few."""
    if not DATA_FILE.is_file():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    # Milliseconds, not seconds: two saves inside the same second are ordinary
    # (fix a typo, save, spot another), and a second-resolution stamp had the
    # later backup silently overwrite the earlier one.
    now = datetime.datetime.now()
    stamp = f"{now:%Y%m%d-%H%M%S}-{now.microsecond // 1000:03d}"
    shutil.copy2(DATA_FILE, BACKUP_DIR / f"prayers-{stamp}.csv")
    for stale in sorted(BACKUP_DIR.glob("prayers-*.csv"))[:-BACKUP_KEEP]:
        stale.unlink()


def write_table(fields: list[str], rows: list[dict]) -> None:
    """Replace the CSV atomically, so a crash mid-write cannot truncate it."""
    text = csv_text(fields, rows)
    _backup()
    handle, tmp = tempfile.mkstemp(dir=str(DATA_FILE.parent),
                                   prefix=".prayers-", suffix=".csv")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, DATA_FILE)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def unified_diff(before: str, after: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile="data/prayers.csv", tofile="data/prayers.csv (after save)",
        n=2,
    ))


# --------------------------------------------------------------------------- #
# Field-level diffing
# --------------------------------------------------------------------------- #
# A whole prayer is one CSV line, so a line diff of the file says only "this
# prayer changed" and leaves you to spot the difference by eye across a hundred
# characters of Latin. These functions diff the row field by field, and within a
# field word by word, which is the question actually being asked at save time:
# what am I about to change? The raw CSV diff is still produced and still shown,
# because it is the literal bytes being written; this is the readable view of it.

WORD_RE = re.compile(r"\S+\s*")


def _word_parts(before: str, after: str) -> tuple[list, list]:
    """Two runs of ['equal'|'del'|'add', text] pairs, one per side.

    Split on words rather than characters: a character diff of Latin picks out
    single letters inside words and reads as noise."""
    a, b = WORD_RE.findall(before), WORD_RE.findall(after)
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    left: list = []
    right: list = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        chunk_a, chunk_b = "".join(a[i1:i2]), "".join(b[j1:j2])
        if tag == "equal":
            left.append(["equal", chunk_a])
            right.append(["equal", chunk_b])
        else:
            if chunk_a:
                left.append(["del", chunk_a])
            if chunk_b:
                right.append(["add", chunk_b])
    return left, right


def _line_diff(a: list[str], b: list[str]) -> list[dict]:
    """A line diff of one multi-line cell, with two lines of context.

    Unchanged runs collapse to a 'gap' rather than reprinting a thirty-line
    context cell to show that one word moved. A replacement of equal length is
    paired up line for line and word-diffed, which is what a reworded line of a
    translation actually looks like."""
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    out: list[dict] = []
    end = 0
    for group in matcher.get_grouped_opcodes(2):
        skipped = group[0][1] - end
        if skipped > 0:
            out.append({"type": "gap", "count": skipped})
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                out += [{"type": "equal", "text": line} for line in a[i1:i2]]
            elif tag == "replace" and (i2 - i1) == (j2 - j1):
                for left_line, right_line in zip(a[i1:i2], b[j1:j2]):
                    before_parts, after_parts = _word_parts(left_line, right_line)
                    out.append({"type": "pair", "beforeParts": before_parts,
                                "afterParts": after_parts})
            else:
                out += [{"type": "del", "text": line} for line in a[i1:i2]]
                out += [{"type": "add", "text": line} for line in b[j1:j2]]
            end = i2
    remaining = len(a) - end
    if out and remaining > 0:
        out.append({"type": "gap", "count": remaining})
    return out


def field_changes(before: dict | None, after: dict | None,
                  fields: list[str]) -> list[dict]:
    """Every column whose value differs, described so the client can render it.

    `before` is None for a create and `after` is None for a delete, so the same
    view serves all three operations."""
    changes: list[dict] = []
    for name in fields:
        old = ((before or {}).get(name) or "").replace("\r\n", "\n")
        new = ((after or {}).get(name) or "").replace("\r\n", "\n")
        if old == new:
            continue
        # An absent cell is no lines, not one empty line: splitting "" would put
        # a phantom blank line into a created prayer's diff.
        old_lines = old.split("\n") if old else []
        new_lines = new.split("\n") if new else []
        change = {"name": name,
                  "added": before is None,
                  "removed": after is None,
                  "wasEmpty": not old.strip(),
                  "isEmpty": not new.strip()}
        if len(old_lines) <= 1 and len(new_lines) <= 1:
            change["kind"] = "inline"
            change["beforeParts"], change["afterParts"] = _word_parts(old, new)
        else:
            change["kind"] = "block"
            change["lines"] = _line_diff(old_lines, new_lines)
        changes.append(change)
    return changes


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _known_categories() -> set[str]:
    return set(build.load_category_descriptions())


def check_row(row: dict, rows: list[dict], index: int,
              categories: set[str]) -> dict:
    """Errors block a save; warnings never do.

    The errors are exactly what build.py's load_prayers() would refuse (plus the
    slug shape, since the slug becomes a URL). The warnings are editorial: house
    style, la/en parallelism, and the things that quietly render as nothing.
    """
    errors: list[str] = []
    warnings: list[str] = []
    cells = {k: (v or "").strip() for k, v in row.items()}

    for col in REQUIRED:
        if not cells.get(col):
            errors.append(f"“{col}” is required and is empty.")

    slug = cells.get("slug", "")
    if slug:
        if not SLUG_RE.match(slug):
            errors.append(
                "“slug” must be kebab-case (lowercase letters, digits, single "
                "hyphens) — it becomes the URL /prayers/<slug>/."
            )
        twin = next((i for i, r in enumerate(rows)
                     if i != index and (r.get("slug") or "").strip() == slug), None)
        if twin is not None:
            errors.append(f"duplicate slug — CSV row {twin + 2} already uses “{slug}”.")

    order_raw = cells.get("order", "")
    order: int | None = None
    if order_raw:
        try:
            order = int(order_raw)
        except ValueError:
            errors.append(f"“order” must be a whole number, got “{order_raw}”.")

    # la / en parallelism. The same splitter build.py uses, imported rather than
    # copied: the studio's idea of a stanza must be the site's, or this lies.
    la = build._split_stanzas(cells.get("la", ""))
    en = build._split_stanzas(cells.get("en", ""))
    if la and en:
        if len(la) != len(en):
            warnings.append(
                f"Latin has {len(la)} stanza(s), English has {len(en)}. They "
                "render side by side, so the stanza breaks should match."
            )
        else:
            for n, (a, b) in enumerate(zip(la, en), start=1):
                if len(a) != len(b):
                    warnings.append(
                        f"stanza {n}: {len(a)} Latin line(s) against "
                        f"{len(b)} English. The columns will not stay aligned."
                    )

    for col in PROSE_COLUMNS:
        if EM_DASH in cells.get(col, ""):
            warnings.append(f"“{col}” contains an em-dash; house style bans it.")

    category = cells.get("category", "")
    if category and categories and category not in categories:
        warnings.append(
            f"“{category}” has no row in data/categories.csv, so the index will "
            "show it without a blurb."
        )

    if order is not None and category:
        clash = next((r for i, r in enumerate(rows) if i != index
                      and (r.get("category") or "").strip() == category
                      and (r.get("order") or "").strip() == order_raw), None)
        if clash:
            warnings.append(
                f"order {order} is already used by “{clash.get('slug')}” in this "
                "category; their order on the index is then arbitrary."
            )

    if not cells.get("description"):
        warnings.append("no description — the index entry will have no summary line.")
    if not cells.get("context"):
        warnings.append("no context — the page will have no “About this prayer”.")

    source, source_url = cells.get("source", ""), cells.get("source_url", "")
    if source and not source_url:
        warnings.append("“source” is set but “source_url” is empty, so no link is shown at all.")
    if source_url and not source_url.startswith(("http://", "https://")):
        warnings.append("“source_url” does not start with http:// or https://.")

    return {"errors": errors, "warnings": warnings}


def check_all(rows: list[dict]) -> list[dict]:
    categories = _known_categories()
    return [check_row(row, rows, i, categories) for i, row in enumerate(rows)]


# --------------------------------------------------------------------------- #
# Applying an edit
# --------------------------------------------------------------------------- #
class StudioError(Exception):
    """A request that cannot be honoured; the message goes back as JSON."""


def apply_op(fields: list[str], rows: list[dict], op: str, slug: str,
             row: dict | None) -> list[dict]:
    """Return a new row list with the one requested change applied.

    `slug` identifies the row as it currently stands on disk, so renaming a slug
    is an ordinary update rather than a delete-and-create.
    """
    index = next((i for i, r in enumerate(rows)
                  if (r.get("slug") or "").strip() == slug), None)

    if op == "create":
        if row is None:
            raise StudioError("create needs a row.")
        new = {k: str(row.get(k, "") or "") for k in fields}
        if any((r.get("slug") or "").strip() == new["slug"].strip() for r in rows):
            raise StudioError(f"a prayer with the slug “{new['slug']}” already exists.")
        return rows + [new]

    if index is None:
        raise StudioError(f"no prayer with the slug “{slug}” is in the CSV.")

    if op == "delete":
        return rows[:index] + rows[index + 1:]

    if op == "update":
        if row is None:
            raise StudioError("update needs a row.")
        updated = list(rows)
        updated[index] = {k: str(row.get(k, "") or "") for k in fields}
        return updated

    raise StudioError(f"unknown operation “{op}”.")


def rebuild() -> dict:
    """Run the real build, turning build.fail()'s SystemExit into a result.

    build.fail() calls sys.exit, which serve.py already has to catch for the same
    reason; here it must become a JSON message rather than killing the server.
    """
    with BUILD_LOCK:
        noise = io.StringIO()
        try:
            with contextlib.redirect_stdout(noise):
                count = build.build()
            return {"ok": True, "message": f"Built {count} prayers into dist/."}
        except SystemExit as exc:
            return {"ok": False, "message": str(exc) or "build failed"}
        except Exception as exc:  # a template typo, a permissions problem…
            return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}


def state() -> dict:
    fields, rows = read_table()
    categories = sorted({(r.get("category") or "").strip() for r in rows if r.get("category")}
                        | _known_categories())
    return {
        "fields": fields,
        "rows": rows,
        "checks": check_all(rows),
        "categories": categories,
        "dataFile": str(DATA_FILE.relative_to(ROOT)),
    }


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class StudioHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler for dist/, plus the /_studio routes in front."""

    # ---- plumbing ---------------------------------------------------------
    def _rest(self) -> str | None:
        """The path under the mount point, or None if this is not a studio URL."""
        path = urlparse(self.path).path
        if path == MOUNT:
            return "\x00redirect"
        if path.startswith(MOUNT + "/"):
            return path[len(MOUNT) + 1:]
        return None

    def _is_local(self) -> bool:
        return self.client_address[0] in ("127.0.0.1", "::1")

    def _send(self, body: bytes, ctype: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send(body, "application/json; charset=utf-8", status)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise StudioError(f"malformed request body: {exc}") from exc

    def _asset(self, name: str) -> None:
        path = (STUDIO_DIR / name).resolve()
        if STUDIO_DIR.resolve() not in path.parents or not path.is_file():
            return self._json({"error": f"no such studio file: {name}"}, 404)
        self._send(path.read_bytes(), MIME.get(path.suffix, "application/octet-stream"))

    # ---- dispatch ---------------------------------------------------------
    def _site_page(self) -> Path | None:
        """The built HTML file this request resolves to, if it resolves to one.

        Used only to slip the studio badge in on the way out. Anything that is
        not a plain .html hit (an asset, a directory that still needs its 301, a
        miss) returns None and is handed back to SimpleHTTPRequestHandler
        untouched, so none of its behaviour has to be reimplemented here."""
        path = urlparse(self.path).path
        if not path.endswith(("/", ".html")):
            return None
        target = Path(self.translate_path(path))
        if target.is_dir():
            if not path.endswith("/"):
                return None  # let super() issue the redirect
            target = target / "index.html"
        return target if target.is_file() and target.suffix == ".html" else None

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler's naming)
        rest = self._rest()
        if rest is None:
            page = self._site_page() if self._is_local() else None
            if page is None:
                return super().do_GET()
            html = inject_badge(page.read_text(encoding="utf-8"),
                                urlparse(self.path).path)
            return self._send(html.encode("utf-8"), "text/html; charset=utf-8")
        if rest == "\x00redirect":
            self.send_response(301)
            self.send_header("Location", MOUNT + "/")
            self.end_headers()
            return
        if not self._is_local():
            return self._json({"error": "the studio is loopback-only."}, 403)
        try:
            if rest == "":
                return self._asset("index.html")
            if rest in ("studio.css", "studio.js"):
                return self._asset(rest)
            if rest == "api/state":
                return self._json(state())
            return self._json({"error": f"no studio route /{rest}"}, 404)
        except StudioError as exc:
            return self._json({"error": str(exc)}, 400)
        except Exception as exc:
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def do_POST(self) -> None:  # noqa: N802
        rest = self._rest()
        if rest is None:
            return self._json({"error": "not found"}, 404)
        if not self._is_local():
            return self._json({"error": "the studio is loopback-only."}, 403)
        try:
            if rest == "api/rebuild":
                return self._json(rebuild())
            if rest in ("api/diff", "api/save"):
                return self._edit(commit=(rest == "api/save"))
            return self._json({"error": f"no studio route /{rest}"}, 404)
        except StudioError as exc:
            return self._json({"error": str(exc)}, 400)
        except Exception as exc:
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    # ---- the one interesting handler --------------------------------------
    def _edit(self, commit: bool) -> None:
        """Preview or perform one edit.

        Both paths re-read the CSV from disk and apply a single change to it, so
        the client never gets to hand back the other prayers. /api/diff is the
        same code without the write, which is what makes the preview honest: the
        diff shown is produced by the bytes that would be written.
        """
        payload = self._body()
        op = str(payload.get("op") or "")
        slug = str(payload.get("slug") or "")
        row = payload.get("row")
        if row is not None and not isinstance(row, dict):
            raise StudioError("“row” must be an object.")

        fields, rows = read_table()
        before = csv_text(fields, rows)
        proposed = apply_op(fields, rows, op, slug, row)
        after = csv_text(fields, proposed)

        target = str((row or {}).get("slug") or slug).strip()
        index = next((i for i, r in enumerate(proposed)
                      if (r.get("slug") or "").strip() == target), None)
        check = ({"errors": [], "warnings": []} if index is None
                 else check_row(proposed[index], proposed, index, _known_categories()))

        # The row as it stands on disk, against the row as proposed. Either side
        # is None for a create or a delete, which field_changes() understands.
        was = next((r for r in rows if (r.get("slug") or "").strip() == slug), None)
        now = None if op == "delete" else (proposed[index] if index is not None else None)

        result = {
            "op": op,
            "diff": unified_diff(before, after),
            "fields": field_changes(was, now, fields),
            "slug": target,
            "errors": check["errors"],
            "warnings": check["warnings"],
            "rowCount": {"before": len(rows), "after": len(proposed)},
        }

        if not commit:
            return self._json(result)

        if check["errors"]:
            raise StudioError("refusing to save: " + " ".join(check["errors"]))
        if before == after:
            result["saved"] = False
            result["build"] = {"ok": True, "message": "Nothing changed; nothing written."}
            result["state"] = state()
            return self._json(result)

        write_table(fields, proposed)
        result["saved"] = True
        result["build"] = rebuild()
        result["state"] = state()
        return self._json(result)
