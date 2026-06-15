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

import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "prayers"
TEMPLATE_DIR = ROOT / "templates"
ASSETS_DIR = ROOT / "assets"
DIST_DIR = ROOT / "dist"

# Files copied verbatim into dist/ if present (publishing metadata).
STATIC_FILES = ("CNAME", ".nojekyll")

REQUIRED_FIELDS = ("id", "title", "subtitle", "category", "latin", "english")


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
def load_prayers() -> list[dict]:
    if not DATA_DIR.is_dir():
        fail(f"no data directory: {DATA_DIR.relative_to(ROOT)}")

    prayers: list[dict] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            prayer = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"{path.name}: invalid JSON: {exc}")

        for field in REQUIRED_FIELDS:
            if field not in prayer or prayer[field] in ("", [], None):
                fail(f"{path.name}: missing required field '{field}'")

        if prayer["id"] != path.stem:
            fail(f"{path.name}: id '{prayer['id']}' must match filename stem '{path.stem}'")

        if not isinstance(prayer["latin"], list) or not isinstance(prayer["english"], list):
            fail(f"{path.name}: 'latin' and 'english' must be arrays of lines")

        prayer.setdefault("order", 1000)
        prayer.setdefault("description", "")
        prayers.append(prayer)

    if not prayers:
        fail(f"no prayer data found in {DATA_DIR.relative_to(ROOT)}")
    return prayers


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_lines(lines: list[str]) -> str:
    """Render an array of text lines into <br>-separated, escaped HTML."""
    return "<br>\n".join("        " + esc(line) for line in lines)


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

    return len(prayers)


def main() -> None:
    if "--check" in sys.argv[1:]:
        prayers = load_prayers()
        for name in ("base.html", "prayer.html", "index.html"):
            load_template(name)
        print(f"OK: {len(prayers)} prayer(s) and templates validated.")
        return

    count = build()
    print(f"Done: {count} prayer(s) built into {DIST_DIR.name}/.")


if __name__ == "__main__":
    main()
