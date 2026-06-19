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
import json
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

# Absolute site origin (no trailing slash). The single source of truth for every
# absolute URL the build emits: canonical links, the sitemap, and JSON-LD.
BASE_URL = "https://latinprayers.org"

# Short site description, reused in the WebSite JSON-LD.
SITE_DESCRIPTION = (
    "Traditional Catholic prayers in Latin set beside a faithful English "
    "translation, with notes on each prayer's history, origin, and use."
)

# CSV column → internal field. 'slug' becomes the prayer id; 'la'/'en' are split
# into line arrays. These columns must be present and non-empty in every row.
REQUIRED_COLUMNS = ("slug", "title", "subtitle", "category", "la", "en")

# Standalone pages: (url slug / template stem, <title>, meta description).
# Each renders templates/<slug>.html into dist/<slug>/index.html at /<slug>/.
STANDALONE_PAGES = (
    # Manifesto is written but not yet publishing-ready (WIP): its source stays
    # in templates/manifesto.html, but it is neither built nor linked. To
    # publish, uncomment this entry and restore the nav link in base.html.
    # (
    #     "manifesto",
    #     "Manifesto",
    #     "The manifesto of latinprayers.org: in the defense of Tradition, the "
    #     "Tridentine Mass, and Catholic living.",
    # ),
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
# SEO helpers: canonical links, structured data, robots.txt, sitemap.xml
# --------------------------------------------------------------------------- #
def site_jsonld() -> str:
    """Site-wide WebSite + Organization JSON-LD (publisher identity), emitted on
    every indexable page. Built with json.dumps so the markup is always valid
    and correctly escaped."""
    data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "latinprayers.org",
        "url": BASE_URL + "/",
        "inLanguage": "en",
        "description": SITE_DESCRIPTION,
        "publisher": {
            "@type": "Organization",
            "name": "latinprayers.org",
            "url": BASE_URL + "/",
            "logo": {
                "@type": "ImageObject",
                "url": BASE_URL + "/assets/img/sacred-heart.png",
            },
        },
    }
    return (
        '<script type="application/ld+json">'
        + json.dumps(data, ensure_ascii=False)
        + "</script>"
    )


def head_extra(path: str | None) -> str:
    """Per-page <head> additions, indented two spaces to match base.html.

    `path` is the site-absolute path of the page (e.g. "/prayers/ave-maria/"):
    it yields a self-referencing canonical link plus the site-wide JSON-LD.
    Pass None for the 404 page, which stands in for many unknown URLs and so is
    marked noindex with no canonical."""
    if path is None:
        return '  <meta name="robots" content="noindex">'
    return (
        f'  <link rel="canonical" href="{BASE_URL + path}">\n'
        f"  {site_jsonld()}"
    )


def write_robots(dist: Path) -> None:
    """Write robots.txt: allow all, allow the major AI crawlers explicitly, and
    point to the sitemap. The AI-bot allowances are a deliberate, documented
    choice to maximise reach (see docs/seo-audit-and-plan.md)."""
    lines = ["User-agent: *", "Allow: /", "", "# AI and answer-engine crawlers (explicitly allowed)"]
    for bot in ("GPTBot", "OAI-SearchBot", "ClaudeBot", "anthropic-ai",
                "PerplexityBot", "Google-Extended", "CCBot"):
        lines += [f"User-agent: {bot}", "Allow: /", ""]
    lines.append(f"Sitemap: {BASE_URL}/sitemap.xml")
    (dist / "robots.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("  wrote dist/robots.txt")


def write_sitemap(prayers: list[dict], dist: Path) -> None:
    """Write sitemap.xml covering the homepage, every prayer, and any standalone
    page. lastmod is the build date for now; a per-prayer date can replace it
    later."""
    today = datetime.date.today().isoformat()
    paths = ["/"]
    paths += [f"/prayers/{p['id']}/" for p in prayers]
    paths += [f"/{slug}/" for slug, _, _ in STANDALONE_PAGES]
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for p in paths:
        out.append(f"  <url><loc>{BASE_URL}{p}</loc><lastmod>{today}</lastmod></url>")
    out.append("</urlset>")
    (dist / "sitemap.xml").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"  wrote dist/sitemap.xml ({len(paths)} urls)")


# --------------------------------------------------------------------------- #
# Data loading & validation
# --------------------------------------------------------------------------- #
def _split_lines(cell: str) -> list[str]:
    """A multi-line CSV cell (one line per row, as edited in a spreadsheet)
    becomes an array of trimmed, non-empty lines."""
    return [line.strip() for line in cell.replace("\r\n", "\n").split("\n") if line.strip()]


def _split_paragraphs(cell: str) -> list[str]:
    """A multi-line CSV cell becomes a list of paragraphs, split on blank lines.
    Lines within a paragraph are joined into one flowing paragraph, so prose may
    be wrapped freely in the spreadsheet cell."""
    text = cell.replace("\r\n", "\n").strip()
    if not text:
        return []
    paragraphs = re.split(r"\n\s*\n", text)
    return [
        " ".join(seg for seg in (ln.strip() for ln in para.split("\n")) if seg)
        for para in paragraphs
        if para.strip()
    ]


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
            "context": cells.get("context", ""),
            "source": cells.get("source", ""),
            "source_url": cells.get("source_url", ""),
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

    # Optional richer context (history, origin, liturgical use) rendered as a
    # prose section of one or more paragraphs beneath the prayer text.
    context = ""
    paragraphs = _split_paragraphs(prayer["context"])
    if paragraphs:
        body = "\n".join(f"      <p>{esc(p)}</p>" for p in paragraphs)
        context = (
            '<section class="prayer-context" aria-labelledby="prayer-context-title">\n'
            '      <h2 class="prayer-context-title" id="prayer-context-title">'
            "About this prayer</h2>\n"
            f"{body}\n"
            "    </section>"
        )

    # Optional muted "translation source" line at the foot of the text card.
    # `source` is the visible label; `source_url`, if present, makes it a link.
    source = ""
    if prayer["source_url"]:
        url = prayer["source_url"]
        # Show the full route by default (only the scheme stripped); `source`
        # overrides the link text when a friendlier label is wanted.
        display = prayer["source"] or re.sub(r"^https?://", "", url)
        link = (
            f'<a href="{esc(url)}" '
            f'target="_blank" rel="noopener noreferrer">{esc(display)}</a>'
        )
        source = f'<p class="prayer-source">Translation source: {link}</p>'
    elif prayer["source"]:
        source = f'<p class="prayer-source">Translation source: {esc(prayer["source"])}</p>'

    content = render(
        prayer_tpl,
        title=esc(prayer["title"]),
        subtitle=esc(prayer["subtitle"]),
        description=description,
        latin_lines=render_lines(prayer["latin"]),
        english_lines=render_lines(prayer["english"]),
        context=context,
        source=source,
    )

    page_desc = prayer["description"] or f'{prayer["title"]}, {prayer["subtitle"]} in Latin and English.'
    return render(
        base_tpl,
        page_title=esc(f'{prayer["title"]}, {prayer["subtitle"]}'),
        page_description=esc(page_desc),
        content=content,
        year=BUILD_YEAR,
        head_extra=head_extra(f'/prayers/{prayer["id"]}/'),
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
            # Lowercased haystack for the optional client-side filter (main.js):
            # Latin name, English gloss, and category, so a query can match any.
            search = esc(f'{p["title"]} {p["subtitle"]} {category}'.lower())
            links.append(
                '        <li data-search="{search}"><a class="prayer-link" href="/prayers/{id}/">'
                '<span class="name" lang="la">{title}</span>'
                '<span class="gloss">{subtitle}</span></a></li>'.format(
                    search=search,
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
        head_extra=head_extra("/"),
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
                head_extra=head_extra(f"/{slug}/"),
            ),
            encoding="utf-8",
        )
        print(f"  wrote {out.relative_to(ROOT)}")

    # robots.txt and sitemap.xml, generated so their URLs derive from BASE_URL.
    write_robots(DIST_DIR)
    write_sitemap(prayers, DIST_DIR)

    # Custom 404 page. GitHub Pages serves /404.html for unknown paths; it is
    # marked noindex (it stands in for many URLs) and carries no canonical.
    not_found_tpl = load_template("404.html")
    (DIST_DIR / "404.html").write_text(
        render(
            base_tpl,
            page_title="Page Not Found",
            page_description="The page you sought is not here.",
            content=not_found_tpl,
            year=BUILD_YEAR,
            head_extra=head_extra(None),
        ),
        encoding="utf-8",
    )
    print("  wrote dist/404.html")

    return len(prayers)


def main() -> None:
    if "--check" in sys.argv[1:]:
        prayers = load_prayers()
        templates = ["base.html", "prayer.html", "index.html", "404.html"]
        templates += [f"{slug}.html" for slug, _, _ in STANDALONE_PAGES]
        for name in templates:
            load_template(name)
        print(f"OK: {len(prayers)} prayer(s) and templates validated.")
        return

    count = build()
    print(f"Done: {count} prayer(s) built into {DIST_DIR.name}/.")


if __name__ == "__main__":
    main()
