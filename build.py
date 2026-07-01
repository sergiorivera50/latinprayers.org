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
MYSTERIES_FILE = ROOT / "data" / "mysteries.csv"
MASS_FILE = ROOT / "data" / "mass.csv"
CATEGORIES_FILE = ROOT / "data" / "categories.csv"
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

# The Rosary. Required columns of data/mysteries.csv, the three traditional sets
# in their fixed order (Latin name + the customary day each is prayed), and small
# numeral maps. The Luminous Mysteries (added 2002) are deliberately omitted:
# this is the traditional 15-decade Dominican Rosary.
REQUIRED_MYSTERY_COLUMNS = ("set", "order", "la", "en", "scripture", "fruit", "meditation")
# (name, Latin name, full day phrase, short day label for the toggle, weekday
# numbers JS uses to open today's set by default — 0=Sunday … 6=Saturday).
ROSARY_SETS = (
    ("Joyful", "Mysteria Gaudiosa", "Mondays and Thursdays", "Mon & Thu", (1, 4)),
    ("Sorrowful", "Mysteria Dolorosa", "Tuesdays and Fridays", "Tue & Fri", (2, 5)),
    ("Glorious", "Mysteria Gloriosa", "Wednesdays, Saturdays, and Sundays", "Wed, Sat & Sun", (3, 6, 0)),
)
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
ORDINAL = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth"}

# The Tridentine Mass. Required columns of data/mass.csv (one row per step of the
# 1962 Ordo Missae, in `order`). `name_la` may be blank for purely descriptive
# steps; every other column must be present and non-empty. The rows are grouped
# for display by `division` (Mass of the Catechumens / of the Faithful / After
# Mass), then by `part`, preserving the order they appear in the file. Roman
# numerals label the eight parts. See docs/mass-page-plan.md for what is modelled
# now and what is deferred (the three axes of variation, the Propers, postures).
REQUIRED_MASS_COLUMNS = ("division", "part", "order", "name_la", "name_en", "summary")
MASS_REQUIRED_NONEMPTY = ("division", "part", "order", "name_en", "summary")
PART_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
# The three forms in display order, used to hide whatever does not occur in the
# form chosen by the selector.
FORM_ORDER = ("low", "sung", "solemn")

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
        "alternateName": "Latin Prayers",
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
    paths.append("/rosary/")
    paths.append("/mass/")
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


def load_mysteries() -> list[dict]:
    """Load the Rosary mysteries from data/mysteries.csv (one row per mystery)."""
    if not MYSTERIES_FILE.is_file():
        fail(f"no data file: {MYSTERIES_FILE.relative_to(ROOT)}")

    with MYSTERIES_FILE.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if rows:
        missing = [c for c in REQUIRED_MYSTERY_COLUMNS if c not in rows[0]]
        if missing:
            fail(f"{MYSTERIES_FILE.name}: missing column(s): {', '.join(missing)}")

    valid_sets = {name for name, *_ in ROSARY_SETS}
    mysteries: list[dict] = []
    for n, row in enumerate(rows, start=2):  # row 1 is the header
        where = f"{MYSTERIES_FILE.name} row {n}"
        cells = {k: (v or "").strip() for k, v in row.items()}
        for col in REQUIRED_MYSTERY_COLUMNS:
            if not cells.get(col):
                fail(f"{where}: missing required column '{col}'")
        if cells["set"] not in valid_sets:
            fail(f"{where}: unknown set '{cells['set']}'")
        try:
            order = int(cells["order"])
        except ValueError:
            fail(f"{where}: 'order' must be an integer, got '{cells['order']}'")
        mysteries.append({
            "set": cells["set"],
            "order": order,
            "la": cells["la"],
            "en": cells["en"],
            "scripture": cells["scripture"],
            "fruit": cells["fruit"],
            "meditation": cells["meditation"],
        })

    if not mysteries:
        fail(f"no mystery data found in {MYSTERIES_FILE.relative_to(ROOT)}")
    return mysteries


def load_mass() -> list[dict]:
    """Load the order of the Tridentine Mass from data/mass.csv (one row per step
    of the Ordo Missae). Rows are returned sorted by `order`."""
    if not MASS_FILE.is_file():
        fail(f"no data file: {MASS_FILE.relative_to(ROOT)}")

    with MASS_FILE.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if rows:
        missing = [c for c in REQUIRED_MASS_COLUMNS if c not in rows[0]]
        if missing:
            fail(f"{MASS_FILE.name}: missing column(s): {', '.join(missing)}")

    steps: list[dict] = []
    seen_orders: set[int] = set()
    for n, row in enumerate(rows, start=2):  # row 1 is the header
        where = f"{MASS_FILE.name} row {n}"
        cells = {k: (v or "").strip() for k, v in row.items()}
        for col in MASS_REQUIRED_NONEMPTY:
            if not cells.get(col):
                fail(f"{where}: missing required column '{col}'")
        try:
            order = int(cells["order"])
        except ValueError:
            fail(f"{where}: 'order' must be an integer, got '{cells['order']}'")
        if order in seen_orders:
            fail(f"{where}: duplicate order '{order}'")
        seen_orders.add(order)
        steps.append({
            "division": cells["division"],
            "part": cells["part"],
            "order": order,
            "name_la": cells.get("name_la", ""),
            "name_en": cells["name_en"],
            "summary": cells["summary"],
            # Optional customary congregational posture (Low Mass), and the
            # High/Sung posture where it differs (blank = same as Low).
            "posture": cells.get("posture", ""),
            "posture_high": cells.get("posture_high", ""),
            # Optional: the celebrant's principal position, and a "Silent" flag on
            # parts said secreto. Both blank is fine.
            "position": cells.get("position", ""),
            "voice": cells.get("voice", ""),
            # Optional: non-empty marks a Proper step (text changes by calendar).
            "proper": cells.get("proper", ""),
            # Optional Form axis: which forms a step occurs in (blank = all), and
            # the notes shown when the Mass is sung / solemn.
            "forms": cells.get("forms", ""),
            "note_sung": cells.get("note_sung", ""),
            "note_solemn": cells.get("note_solemn", ""),
        })

    if not steps:
        fail(f"no mass data found in {MASS_FILE.relative_to(ROOT)}")
    steps.sort(key=lambda s: s["order"])
    return steps


def load_category_descriptions() -> dict[str, str]:
    """Optional one-line description per category, keyed by the exact category
    name used in prayers.csv (data/categories.csv: columns 'category',
    'description'). A missing file, or a category without a row, is fine: the
    category simply renders without a blurb."""
    if not CATEGORIES_FILE.is_file():
        return {}
    with CATEGORIES_FILE.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    descriptions: dict[str, str] = {}
    for row in rows:
        cells = {k: (v or "").strip() for k, v in row.items()}
        category, description = cells.get("category", ""), cells.get("description", "")
        if category and description:
            descriptions[category] = description
    return descriptions


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


# Prayer links inside the Rosary page (e.g. /prayers/pater-noster/). The prayers
# the Rosary leans on get a CTA back to /rosary/; deriving the set from the
# template keeps a single source of truth, so it follows the page automatically.
ROSARY_LINK_RE = re.compile(r"/prayers/([a-z0-9-]+)/")


def rosary_prayer_slugs(rosary_tpl: str) -> set[str]:
    """The slugs of every prayer linked from the Rosary template."""
    return set(ROSARY_LINK_RE.findall(rosary_tpl))


def render_rosary_cta(prayer: dict) -> str:
    """A card at the foot of a prayer page inviting the reader to the Rosary.
    Shown only on prayers the Rosary itself links to (see rosary_prayer_slugs)."""
    return (
        '<aside class="rosary-cta" aria-labelledby="rosary-cta-title">\n'
        '  <p class="rosary-cta-eyebrow">Special devotion</p>\n'
        '  <h2 class="rosary-cta-title" id="rosary-cta-title">Pray the Holy Rosary</h2>\n'
        f'  <p class="rosary-cta-lead">{esc(prayer["subtitle"])} is one of the '
        "prayers of the Holy Rosary. See how it is woven through the mysteries, "
        "and learn to pray the whole devotion.</p>\n"
        '  <a class="rosary-cta-link" href="/rosary/">Pray the Rosary '
        '<span class="rosary-cta-arrow" aria-hidden="true">&rarr;</span></a>\n'
        "</aside>"
    )


def build_prayer_page(
    prayer: dict, base_tpl: str, prayer_tpl: str, rosary_slugs: set[str]
) -> str:
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

    rosary_cta = render_rosary_cta(prayer) if prayer["id"] in rosary_slugs else ""

    content = render(
        prayer_tpl,
        title=esc(prayer["title"]),
        subtitle=esc(prayer["subtitle"]),
        description=description,
        latin_lines=render_lines(prayer["latin"]),
        english_lines=render_lines(prayer["english"]),
        context=context,
        source=source,
        rosary_cta=rosary_cta,
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


def build_index_page(
    prayers: list[dict], base_tpl: str, index_tpl: str, descriptions: dict[str, str]
) -> str:
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
        desc = descriptions.get(category, "")
        desc_html = f'  <p class="category-desc">{esc(desc)}</p>\n' if desc else ""
        blocks.append(
            '<section class="category">\n'
            f'  <h2 class="category-title">{esc(category)}</h2>\n'
            f"{desc_html}"
            '  <ul class="prayer-list">\n'
            + "\n".join(links)
            + "\n  </ul>\n</section>"
        )

    content = render(index_tpl, categories="\n\n".join(blocks))
    return render(
        base_tpl,
        page_title="Latin Prayers with English Translations",
        page_description=(
            "Latin prayers with faithful English translations: the Pater Noster, "
            "Ave Maria, Salve Regina, the Rosary, and other traditional Catholic "
            "prayers."
        ),
        content=content,
        year=BUILD_YEAR,
        head_extra=head_extra("/"),
    )


def rosary_jsonld() -> str:
    """Page-specific Article JSON-LD for the Rosary page."""
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "How to Pray the Holy Rosary",
        "name": "The Holy Rosary",
        "description": (
            "The traditional Holy Rosary: how to pray it, and the Joyful, "
            "Sorrowful, and Glorious Mysteries in Latin and English."
        ),
        "inLanguage": "en",
        "about": "The Holy Rosary",
        "url": BASE_URL + "/rosary/",
        "isPartOf": {"@type": "WebSite", "name": "latinprayers.org", "url": BASE_URL + "/"},
        "publisher": {"@type": "Organization", "name": "latinprayers.org"},
    }
    return (
        '<script type="application/ld+json">'
        + json.dumps(data, ensure_ascii=False)
        + "</script>"
    )


def mystery_image(set_slug: str, order: int) -> str | None:
    """Web path to a mystery's illustration if one has been added under
    assets/img/mysteries/<set>-<order>.<ext>, else None (a placeholder shows).
    Lets art be dropped in per mystery without touching the build."""
    for ext in ("webp", "jpg", "jpeg", "png"):
        rel = f"img/mysteries/{set_slug}-{order}.{ext}"
        if (ASSETS_DIR / rel).is_file():
            return "/assets/" + rel
    return None


def build_rosary_page(mysteries: list[dict], base_tpl: str, rosary_tpl: str) -> str:
    by_set: dict[str, list[dict]] = {}
    for m in mysteries:
        by_set.setdefault(m["set"], []).append(m)

    # The mysteries render as one tabbed card: a toggle (Joyful / Sorrowful /
    # Glorious) over three panels, each a wide card with a set image on the left
    # and its five mysteries on the right. Every panel is present in the markup
    # (fully readable with no JS); main.js turns the toggle on and opens today's
    # set. data-days carries the weekday numbers it keys the default off.
    tabs: list[str] = []
    panels: list[str] = []
    for name, _latin, _days, short, weekdays in ROSARY_SETS:
        slug = name.lower()
        wd = ",".join(str(d) for d in weekdays)
        tabs.append(
            f'    <a class="mysteries-tab" id="tab-{slug}" href="#panel-{slug}" '
            f'aria-controls="panel-{slug}" data-days="{wd}">'
            f'<span class="mysteries-tab-name">{esc(name)}</span>'
            f'<span class="mysteries-tab-days">{esc(short)}</span></a>'
        )

        items = sorted(by_set.get(name, []), key=lambda m: m["order"])
        cards = []
        for m in items:
            num = m["order"]
            ordinal = ORDINAL.get(num, "")
            img = mystery_image(slug, num)
            if img:
                figure = f'<img src="{img}" alt="{esc(m["en"])}" loading="lazy">'
            else:
                figure = (
                    '<div class="placeholder" aria-hidden="true">'
                    f'<span>{esc(m["en"])}</span></div>'
                )
            cards.append(
                f'          <li class="decade-card" id="decade-{slug}-{num}" '
                f'aria-label="{esc(ordinal)} {esc(name)} Mystery: {esc(m["en"])}">\n'
                f'            <figure class="decade-figure">{figure}</figure>\n'
                '            <div class="decade-body">\n'
                f'              <p class="decade-eyebrow">{esc(ordinal)} {esc(name)} Mystery</p>\n'
                f'              <h4 class="mystery-name">{esc(m["en"])}</h4>\n'
                f'              <p class="mystery-ref">{esc(m["scripture"])}'
                f'<span class="mystery-sep" aria-hidden="true">/</span>'
                f'<span class="mystery-fruit">{esc(m["fruit"])}</span></p>\n'
                f'              <p class="mystery-med">{esc(m["meditation"])}</p>\n'
                "            </div>\n"
                "          </li>"
            )

        panels.append(
            f'    <article class="mysteries-panel" id="panel-{slug}" '
            f'aria-labelledby="tab-{slug}" data-set="{slug}">\n'
            '      <div class="decade-carousel">\n'
            f'        <ol class="decade-track" aria-label="The {esc(name)} Mysteries">\n'
            + "\n".join(cards)
            + "\n        </ol>\n"
            "      </div>\n"
            "    </article>"
        )

    mysteries_html = (
        '<section class="mysteries" aria-labelledby="mysteries-title">\n'
        '  <h2 class="rosary-h2" id="mysteries-title">The Fifteen Mysteries</h2>\n'
        "  <p class=\"mysteries-lead\">For each day of the week, the Church sets before us one of "
        "the three sets of mysteries to contemplate. Choose a set to read its five "
        "mysteries, with their Scripture and spiritual fruits.</p>\n"
        '  <div class="mysteries-tabs" aria-label="The three sets of mysteries">\n'
        + "\n".join(tabs)
        + "\n  </div>\n"
        '  <div class="mysteries-panels" id="mysteries">\n'
        + "\n".join(panels)
        + "\n  </div>\n"
        "</section>"
    )

    content = render(rosary_tpl, mysteries=mysteries_html)
    page_desc = (
        "How to pray the traditional Holy Rosary, with the Joyful, Sorrowful, "
        "and Glorious Mysteries in Latin and English, their Scripture and fruits."
    )
    return render(
        base_tpl,
        page_title="The Holy Rosary",
        page_description=page_desc,
        content=content,
        year=BUILD_YEAR,
        head_extra=head_extra("/rosary/") + "\n  " + rosary_jsonld(),
    )


def mass_jsonld() -> str:
    """Page-specific Article JSON-LD for the Tridentine Mass page."""
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "The Order of the Tridentine Mass",
        "name": "The Tridentine Mass",
        "description": (
            "The order of the traditional Latin Mass according to the 1962 "
            "Missale Romanum: the Mass of the Catechumens and the Mass of the "
            "Faithful, step by step."
        ),
        "inLanguage": "en",
        "about": "The Tridentine Mass",
        "url": BASE_URL + "/mass/",
        "isPartOf": {"@type": "WebSite", "name": "latinprayers.org", "url": BASE_URL + "/"},
        "publisher": {"@type": "Organization", "name": "latinprayers.org"},
    }
    return (
        '<script type="application/ld+json">'
        + json.dumps(data, ensure_ascii=False)
        + "</script>"
    )


def group_forms(group_steps: list[dict]) -> str:
    """The data-forms value for a group of steps (a part or a division): the
    comma list of forms it occurs in, or "" when it occurs in all of them. Any
    step that applies to every form makes the whole group apply to every form."""
    appears: set[str] = set()
    for s in group_steps:
        if not s["forms"]:
            return ""
        appears |= set(s["forms"].split(","))
    return ",".join(f for f in FORM_ORDER if f in appears)


def build_mass_page(steps: list[dict], base_tpl: str, mass_tpl: str) -> str:
    """Render the order of the Mass: the ordered steps grouped by division and
    then by part. Every step renders as a row (a continuous step number, the
    Latin and English names, and a short summary), so the page is a single
    static outline of the Ordo Missae, fully readable with no JavaScript."""
    # Group by division, then by part, both preserving first-seen order (the
    # rows are already sorted by `order`, so this follows the Mass's sequence).
    divisions: list[tuple[str, list[tuple[str, list[dict]]]]] = []
    for step in steps:
        if not divisions or divisions[-1][0] != step["division"]:
            divisions.append((step["division"], []))
        parts = divisions[-1][1]
        if not parts or parts[-1][0] != step["part"]:
            parts.append((step["part"], []))
        parts[-1][1].append(step)

    part_no = 0
    blocks: list[str] = []
    for division, parts in divisions:
        part_html: list[str] = []
        for part_name, part_steps in parts:
            part_no += 1
            numeral = PART_ROMAN.get(part_no, str(part_no))
            items: list[str] = []
            for s in part_steps:
                name_la = (
                    f'<span class="ordo-step-la" lang="la">{esc(s["name_la"])}</span>'
                    if s["name_la"] else ""
                )
                # Optional customary posture tag. Two values are rendered (Low and
                # High); the Form selector shows one (High falls back to Low when
                # they match). Each carries its own colour-keyed dot.
                data_posture = posture = ""
                if s["posture"]:
                    low = esc(s["posture"])
                    high = esc(s["posture_high"] or s["posture"])
                    data_posture = f' data-posture="{low}"'
                    posture = (
                        '          <span class="ordo-step-posture">'
                        f'<span class="ordo-posture-val posture-low" data-posture="{low}" '
                        f'aria-label="Customary posture: {low}">{low}</span>'
                        f'<span class="ordo-posture-val posture-high" data-posture="{high}" '
                        f'aria-label="Customary posture at sung Mass: {high}">{high}</span>'
                        "</span>\n"
                    )
                # Optional meta line: the principal position, a "said silently"
                # flag on the secreto parts, and a chip marking Proper steps.
                meta = ""
                if s["position"] or s["voice"] or s["proper"]:
                    bits = []
                    if s["position"]:
                        bits.append(f'<span class="ordo-step-pos">{esc(s["position"])}</span>')
                    if s["voice"] == "Silent":
                        bits.append('<span class="ordo-step-silent">said silently</span>')
                    sep = '<span class="ordo-step-sep" aria-hidden="true">·</span>'
                    proper_chip = (
                        '<span class="ordo-step-proper">Proper of the day</span>'
                        if s["proper"] else ""
                    )
                    meta = (
                        '            <p class="ordo-step-meta">'
                        + sep.join(bits)
                        + proper_chip
                        + "</p>\n"
                    )
                # Form-axis notes: note_sung shows at sung & Solemn Mass,
                # note_solemn only at Solemn. All show with no JS; the selector
                # filters them. data-forms restricts a step to certain forms.
                fn = []
                if s["note_sung"]:
                    fn.append(
                        '              <p class="ordo-form-note" data-form-note="sung">'
                        '<span class="ordo-form-label">Sung</span>'
                        f'{esc(s["note_sung"])}</p>'
                    )
                if s["note_solemn"]:
                    fn.append(
                        '              <p class="ordo-form-note" data-form-note="solemn">'
                        '<span class="ordo-form-label">Solemn</span>'
                        f'{esc(s["note_solemn"])}</p>'
                    )
                form_notes = (
                    '            <div class="ordo-step-forms">\n'
                    + "\n".join(fn) + "\n            </div>\n"
                ) if fn else ""
                data_forms = f' data-forms="{esc(s["forms"])}"' if s["forms"] else ""
                items.append(
                    f'        <li class="ordo-step" id="ordo-{s["order"]}"{data_posture}{data_forms}>\n'
                    # The number is a CSS counter so hidden steps don't leave a gap.
                    '          <span class="ordo-step-num" aria-hidden="true"></span>\n'
                    '          <div class="ordo-step-body">\n'
                    '            <p class="ordo-step-name">'
                    f'{name_la}'
                    f'<span class="ordo-step-en">{esc(s["name_en"])}</span></p>\n'
                    f"{meta}"
                    f'            <p class="ordo-step-summary">{esc(s["summary"])}</p>\n'
                    f"{form_notes}"
                    "          </div>\n"
                    f"{posture}"
                    "        </li>"
                )
            part_forms = group_forms(part_steps)
            part_attr = f' data-forms="{part_forms}"' if part_forms else ""
            part_html.append(
                f'      <section class="ordo-part"{part_attr}>\n'
                '        <h4 class="ordo-part-title">'
                f'<span class="ordo-part-num" aria-hidden="true">{numeral}</span>'
                f'{esc(part_name)}</h4>\n'
                '        <ol class="ordo-steps">\n'
                + "\n".join(items)
                + "\n        </ol>\n"
                "      </section>"
            )
        # A division is hidden when none of its steps occur in the chosen form
        # (e.g. "After Mass" at sung/Solemn), so no empty heading is left behind.
        div_steps = [s for _name, ps in parts for s in ps]
        div_forms = group_forms(div_steps)
        div_attr = f' data-forms="{div_forms}"' if div_forms else ""
        blocks.append(
            f'    <div class="ordo-division"{div_attr}>\n'
            f'      <h3 class="ordo-division-title">{esc(division)}</h3>\n'
            + "\n".join(part_html)
            + "\n    </div>"
        )

    order_html = (
        '<section class="ordo" aria-labelledby="ordo-title">\n'
        '  <h2 class="mass-h2" id="ordo-title">The Order of Mass</h2>\n'
        '  <p class="ordo-lead">The Mass unfolds in two great divisions: the Mass '
        "of the Catechumens, the liturgy of prayer and the word, and the Mass of "
        "the Faithful, the offering of the Sacrifice itself. The steps marked "
        '<span class="ordo-proper-key">Proper of the day</span> change with the '
        "calendar; the rest are the Ordinary, the same at every Mass.</p>\n"
        '  <p class="ordo-posture-note">The posture beside each step '
        '(<span class="posture-key" data-posture="Stand">stand</span>, '
        '<span class="posture-key" data-posture="Sit">sit</span>, '
        '<span class="posture-key" data-posture="Kneel">kneel</span>) is the '
        "customary one for the form chosen above. At Low Mass the faithful kneel "
        "for much of the Mass; at sung and Solemn Mass they follow the sacred "
        "ministers, standing more and sitting when the priest sits. Lay postures "
        "were never strictly prescribed and vary from place to place; when in "
        "doubt, follow those around you.</p>\n"
        # A handwritten hint pointing at the selector. It is a normal-flow sibling
        # of the sticky pill, so it stays at the start position and scrolls away
        # (never sticky). Decorative, and shown only when JS reveals the selector.
        '  <div class="form-hint" aria-hidden="true">\n'
        '    <span class="form-hint-text">choose the form</span>\n'
        '    <svg class="form-hint-arrow" viewBox="0 0 50 62" fill="none">\n'
        '      <path class="form-hint-stroke" d="M3 6 C 30 2, 46 20, 29 48"/>\n'
        '      <path class="form-hint-stroke" d="M20 41 L 29 53 L 38 40"/>\n'
        "    </svg>\n"
        "  </div>\n"
        # Form selector: hidden until main.js reveals it, so with no JS every
        # form's notes stay visible below. Choosing a form filters those notes.
        '  <div class="form-select-wrap">\n'
        '    <div class="form-select" role="group" aria-label="Choose the form of Mass to follow" hidden>\n'
        '      <button type="button" class="form-option" data-form="low" aria-pressed="true">Low</button>\n'
        '      <button type="button" class="form-option" data-form="sung" aria-pressed="false">Sung</button>\n'
        '      <button type="button" class="form-option" data-form="solemn" aria-pressed="false">Solemn</button>\n'
        "    </div>\n"
        "  </div>\n"
        + "\n".join(blocks)
        + "\n</section>"
    )

    content = render(mass_tpl, order_of_mass=order_html)
    page_desc = (
        "The order of the traditional Latin (Tridentine) Mass according to the "
        "1962 Missale Romanum: the Mass of the Catechumens and the Mass of the "
        "Faithful, set out step by step."
    )
    return render(
        base_tpl,
        page_title="The Tridentine Mass",
        page_description=page_desc,
        content=content,
        year=BUILD_YEAR,
        head_extra=head_extra("/mass/") + "\n  " + mass_jsonld(),
    )


# --------------------------------------------------------------------------- #
# Build orchestration
# --------------------------------------------------------------------------- #
def build() -> int:
    """Render the whole site into a fresh dist/. Returns the prayer count."""
    prayers = load_prayers()
    mysteries = load_mysteries()
    mass_steps = load_mass()
    category_descriptions = load_category_descriptions()
    base_tpl = load_template("base.html")
    prayer_tpl = load_template("prayer.html")
    index_tpl = load_template("index.html")
    rosary_tpl = load_template("rosary.html")
    mass_tpl = load_template("mass.html")

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
    rosary_slugs = rosary_prayer_slugs(rosary_tpl)
    prayers_out = DIST_DIR / "prayers"
    for prayer in prayers:
        page_dir = prayers_out / prayer["id"]
        page_dir.mkdir(parents=True)
        out = page_dir / "index.html"
        out.write_text(
            build_prayer_page(prayer, base_tpl, prayer_tpl, rosary_slugs),
            encoding="utf-8",
        )
        print(f"  wrote {out.relative_to(ROOT)}")

    # Render the homepage.
    index_out = DIST_DIR / "index.html"
    index_out.write_text(
        build_index_page(prayers, base_tpl, index_tpl, category_descriptions),
        encoding="utf-8",
    )
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

    # The Rosary: its own data-driven page at /rosary/.
    rosary_dir = DIST_DIR / "rosary"
    rosary_dir.mkdir()
    (rosary_dir / "index.html").write_text(
        build_rosary_page(mysteries, base_tpl, rosary_tpl), encoding="utf-8"
    )
    print("  wrote dist/rosary/index.html")

    # The Tridentine Mass: its own data-driven page at /mass/.
    mass_dir = DIST_DIR / "mass"
    mass_dir.mkdir()
    (mass_dir / "index.html").write_text(
        build_mass_page(mass_steps, base_tpl, mass_tpl), encoding="utf-8"
    )
    print("  wrote dist/mass/index.html")

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
        mysteries = load_mysteries()
        mass_steps = load_mass()
        templates = ["base.html", "prayer.html", "index.html", "404.html", "rosary.html", "mass.html"]
        templates += [f"{slug}.html" for slug, _, _ in STANDALONE_PAGES]
        for name in templates:
            load_template(name)
        print(
            f"OK: {len(prayers)} prayer(s), {len(mysteries)} mystery(ies), "
            f"{len(mass_steps)} mass step(s), and templates validated."
        )
        return

    count = build()
    print(f"Done: {count} prayer(s) built into {DIST_DIR.name}/.")


if __name__ == "__main__":
    main()
