#!/usr/bin/env python3
"""Build latinprayers.org: render data/ + templates/ into a static site.

Standard library only — no third-party dependencies, no install step.

The build is emitted into a self-contained ``dist/`` directory: rendered HTML
plus the hand-authored ``assets/`` and the publishing files (``CNAME``,
``.nojekyll``). ``dist/`` is the exact set of files published to GitHub Pages;
it is generated, gitignored, and never committed.

Usage:
    python3 build.py            # build the whole site into dist/
    python3 build.py --check    # validate data + templates only; write nothing
"""

from __future__ import annotations

import csv
import datetime
import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "prayers.csv"
TEMPLATE_DIR = ROOT / "templates"
ASSETS_DIR = ROOT / "assets"
DIST_DIR = ROOT / "dist"

# Files copied verbatim into dist/ if present (publishing metadata).
STATIC_FILES = ("CNAME", ".nojekyll")

BUILD_YEAR = str(datetime.date.today().year)

# CSV column → internal field. 'slug' becomes the prayer id; 'la'/'en' are split
# into line arrays. These columns must be present and non-empty in every row.
REQUIRED_COLUMNS = ("slug", "title", "subtitle", "category", "la", "en")

# Standalone pages: (url slug / template stem, <title>, meta description).
# Each renders templates/<slug>.html into dist/<slug>/index.html at /<slug>/.
STANDALONE_PAGES = (
    (
        "manifesto",
        "Manifesto",
        "The manifesto of latinprayers.org: in the defense of Tradition, the "
        "Tridentine Mass, and Catholic living.",
    ),
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def fail(message: str) -> "NoReturn":  # type: ignore[name-defined]
    sys.stderr.write(f"build.py: error: {message}\n")
    sys.exit(1)


def load_template(name: str) -> str:
    path = TEMPLATE_DIR / name
    if not path.is_file():
        fail(f"missing template: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def render(template: str, **values: str) -> str:
    """Replace {{key}} tokens in a template with the given values."""
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def esc(text: str) -> str:
    return html.escape(text, quote=True)


# --------------------------------------------------------------------------- #
# Data loading & validation
# --------------------------------------------------------------------------- #
def _split_lines(cell: str) -> list[str]:
    """A multi-line CSV cell (one line per row, as edited in a spreadsheet)
    becomes an array of trimmed, non-empty lines."""
    return [line.strip() for line in cell.replace("\r\n", "\n").split("\n") if line.strip()]


def load_prayers() -> list[dict]:
    if not DATA_FILE.is_file():
        fail(f"no data file: {DATA_FILE.relative_to(ROOT)}")

    with DATA_FILE.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if rows:
        missing = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
        if missing:
            fail(f"{DATA_FILE.name}: missing column(s): {', '.join(missing)}")

    prayers: list[dict] = []
    seen_slugs: set[str] = set()
    for n, row in enumerate(rows, start=2):  # row 1 is the header
        where = f"{DATA_FILE.name} row {n}"
        cells = {k: (v or "").strip() for k, v in row.items()}

        for col in REQUIRED_COLUMNS:
            if not cells.get(col):
                fail(f"{where}: missing required column '{col}'")

        slug = cells["slug"]
        if slug in seen_slugs:
            fail(f"{where}: duplicate slug '{slug}'")
        seen_slugs.add(slug)

        order_raw = cells.get("order", "")
        try:
            order = int(order_raw) if order_raw else 1000
        except ValueError:
            fail(f"{where}: 'order' must be an integer, got '{order_raw}'")

        prayers.append({
            "id": slug,
            "title": cells["title"],
            "subtitle": cells["subtitle"],
            "category": cells["category"],
            "order": order,
            "description": cells.get("description", ""),
            "latin": _split_lines(cells["la"]),
            "english": _split_lines(cells["en"]),
        })

    if not prayers:
        fail(f"no prayer data found in {DATA_FILE.relative_to(ROOT)}")
    return prayers


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
# Whole-word "Amen" with its trailing period, wrapped after escaping so it can
# be coloured liturgical red in the stylesheet.
AMEN_RE = re.compile(r"\bAmen\.?")


def render_lines(lines: list[str]) -> str:
    """Render an array of text lines into <br>-separated, escaped HTML."""
    rendered = []
    for line in lines:
        safe = AMEN_RE.sub(r'<span class="amen">\g<0></span>', esc(line))
        rendered.append("        " + safe)
    return "<br>\n".join(rendered)


def build_prayer_page(prayer: dict, base_tpl: str, prayer_tpl: str) -> str:
    description = ""
    if prayer["description"]:
        description = f'<p class="prayer-description">{esc(prayer["description"])}</p>'

    content = render(
        prayer_tpl,
        title=esc(prayer["title"]),
        subtitle=esc(prayer["subtitle"]),
        description=description,
        latin_lines=render_lines(prayer["latin"]),
        english_lines=render_lines(prayer["english"]),
    )

    page_desc = prayer["description"] or f'{prayer["title"]} — {prayer["subtitle"]} in Latin and English.'
    return render(
        base_tpl,
        page_title=esc(f'{prayer["title"]} — {prayer["subtitle"]}'),
        page_description=esc(page_desc),
        content=content,
        year=BUILD_YEAR,
    )


def build_index_page(prayers: list[dict], base_tpl: str, index_tpl: str) -> str:
    # Group by category, preserving first-seen category order; sort within by order.
    categories: dict[str, list[dict]] = {}
    for prayer in prayers:
        categories.setdefault(prayer["category"], []).append(prayer)

    blocks: list[str] = []
    for category, items in categories.items():
        items.sort(key=lambda p: (p["order"], p["title"]))
        links = []
        for p in items:
            links.append(
                '        <li><a class="prayer-link" href="/prayers/{id}/">'
                '<span class="name" lang="la">{title}</span>'
                '<span class="gloss">{subtitle}</span></a></li>'.format(
                    id=esc(p["id"]),
                    title=esc(p["title"]),
                    subtitle=esc(p["subtitle"]),
                )
            )
        blocks.append(
            '<section class="category">\n'
            f'  <h2 class="category-title">{esc(category)}</h2>\n'
            '  <ul class="prayer-list">\n'
            + "\n".join(links)
            + "\n  </ul>\n</section>"
        )

    content = render(index_tpl, categories="\n\n".join(blocks))
    return render(
        base_tpl,
        page_title="Prayers in Latin",
        page_description=(
            "A reverent repository of Catholic prayers in Latin, set beside a "
            "faithful English translation. In the defense of Tradition, the "
            "Tridentine Mass, and Catholic living."
        ),
        content=content,
        year=BUILD_YEAR,
    )


# --------------------------------------------------------------------------- #
# Build orchestration
# --------------------------------------------------------------------------- #
def build() -> int:
    """Render the whole site into a fresh dist/. Returns the prayer count."""
    prayers = load_prayers()
    base_tpl = load_template("base.html")
    prayer_tpl = load_template("prayer.html")
    index_tpl = load_template("index.html")

    # Start from a clean, self-contained output directory.
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    # Copy hand-authored assets and publishing metadata verbatim.
    if ASSETS_DIR.is_dir():
        shutil.copytree(ASSETS_DIR, DIST_DIR / "assets")
    for name in STATIC_FILES:
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, DIST_DIR / name)

    # Render prayer pages as directory indexes (prayers/<id>/index.html) so the
    # public URL is a clean /prayers/<id>/ with no .html suffix.
    prayers_out = DIST_DIR / "prayers"
    for prayer in prayers:
        page_dir = prayers_out / prayer["id"]
        page_dir.mkdir(parents=True)
        out = page_dir / "index.html"
        out.write_text(build_prayer_page(prayer, base_tpl, prayer_tpl), encoding="utf-8")
        print(f"  wrote {out.relative_to(ROOT)}")

    # Render the homepage.
    index_out = DIST_DIR / "index.html"
    index_out.write_text(build_index_page(prayers, base_tpl, index_tpl), encoding="utf-8")
    print(f"  wrote {index_out.relative_to(ROOT)}")

    # Render standalone pages (content held directly in their templates).
    for slug, title, description in STANDALONE_PAGES:
        page_tpl = load_template(f"{slug}.html")
        page_dir = DIST_DIR / slug
        page_dir.mkdir()
        out = page_dir / "index.html"
        out.write_text(
            render(
                base_tpl,
                page_title=esc(title),
                page_description=esc(description),
                content=page_tpl,
                year=BUILD_YEAR,
            ),
            encoding="utf-8",
        )
        print(f"  wrote {out.relative_to(ROOT)}")

    return len(prayers)


def main() -> None:
    if "--check" in sys.argv[1:]:
        prayers = load_prayers()
        templates = ["base.html", "prayer.html", "index.html"]
        templates += [f"{slug}.html" for slug, _, _ in STANDALONE_PAGES]
        for name in templates:
            load_template(name)
        print(f"OK: {len(prayers)} prayer(s) and templates validated.")
        return

    count = build()
    print(f"Done: {count} prayer(s) built into {DIST_DIR.name}/.")


if __name__ == "__main__":
    main()
