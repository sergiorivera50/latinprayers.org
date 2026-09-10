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
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "prayers.csv"
MYSTERIES_FILE = ROOT / "data" / "mysteries.csv"
CATEGORIES_FILE = ROOT / "data" / "categories.csv"
ARTICLES_DIR = ROOT / "data" / "articles"
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

# Standalone pages: (url slug / template stem, <title>, meta description).
# Each renders templates/<slug>.html into dist/<slug>/index.html at /<slug>/.
# Content pages that are not prayers, as (slug, title, description). Each needs a
# templates/<slug>.html holding its content block; it is emitted to /<slug>/.
# Empty for now: the Manifesto lived here and has been removed.
STANDALONE_PAGES: tuple[tuple[str, str, str], ...] = ()

# Articles: long-form prose at /articles/, one file per article in data/articles/.
# Prose does not fit the CSV model. esc() makes every character in a CSV cell
# literal, so a link or an emphasis written into a cell renders as visible markup,
# and a whole essay on one CSV line is an unreadable git diff. An article is
# therefore its own file: a 'key: value' header, a line of exactly ---, then a
# body in which A BLOCK THAT BEGINS WITH '<' IS AUTHORED MARKUP AND EVERY OTHER
# BLOCK IS A PARAGRAPH. That single rule is the whole format; it is
# _split_paragraphs (which is how a prayer's 'context' already behaves) plus one
# condition, so there is no markdown parser here and none is wanted.
#
# The body is trusted and not escaped, exactly as templates/rosary.html is
# trusted. What keeps that honest is check_article_body(): the tag stack is
# walked so an unclosed or crossed tag is a build error with a line number, the
# tag vocabulary is a closed allowlist, and the house no-em-dash rule is enforced
# for the first time on any content in this repo.
ARTICLE_REQUIRED_KEYS = ("title", "subtitle", "description", "date")
ARTICLE_OPTIONAL_KEYS = ("image", "image_alt")

# The tag vocabulary an article body may use. A closed set, so the format cannot
# quietly grow into arbitrary HTML one article at a time.
ARTICLE_TAGS = {
    "h2", "h3", "p", "em", "i", "strong", "b", "a", "span", "br",
    "blockquote", "ul", "ol", "li", "figure", "figcaption", "img", "cite", "hr",
}
ARTICLE_VOID_TAGS = {"br", "img", "hr"}

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


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
    out = (
        f'  <link rel="canonical" href="{BASE_URL + path}">\n'
        f"  {site_jsonld()}"
    )
    if path == "/":
        # The display italic is used by one element on one page (the word set in
        # the hero title), so it is preloaded here rather than in base.html,
        # which would put it on every other page's critical path for nothing.
        out = ('  <link rel="preload" as="font" type="font/woff2" '
               'href="/assets/fonts/cormorant-600i.woff2" crossorigin>\n') + out
    return out


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


def write_sitemap(prayers: list[dict], articles: list[dict], dist: Path) -> None:
    """Write sitemap.xml covering the homepage, the prayer index, every prayer,
    and any standalone page. lastmod is the build date for now; a per-prayer date
    can replace it later."""
    today = datetime.date.today().isoformat()
    # (path, lastmod). Everything without a real date of its own still carries
    # the build date, as before; an article carries the date in its own header,
    # which is the only content on the site that knows when it was written.
    urls: list[tuple[str, str]] = [("/", today), ("/prayers/", today)]
    urls += [(f"/prayers/{p['id']}/", today) for p in prayers]
    urls += [(f"/{slug}/", today) for slug, _, _ in STANDALONE_PAGES]
    urls.append(("/rosary/", today))
    urls.append(("/articles/", articles[0]["date"] if articles else today))
    urls += [(f"/articles/{a['id']}/", a["date"]) for a in articles]
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, lastmod in urls:
        out.append(f"  <url><loc>{BASE_URL}{path}</loc><lastmod>{lastmod}</lastmod></url>")
    out.append("</urlset>")
    (dist / "sitemap.xml").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"  wrote dist/sitemap.xml ({len(urls)} urls)")


# --------------------------------------------------------------------------- #
# Data loading & validation
# --------------------------------------------------------------------------- #
def _split_stanzas(cell: str) -> list[list[str]]:
    """A multi-line CSV cell becomes a list of stanzas, each a list of lines.

    A blank line within the cell separates one stanza from the next; single
    newlines separate the lines within a stanza. A cell that has no blank line
    yields a single stanza, so a prayer renders exactly as before until stanza
    breaks are introduced into its ``la``/``en`` text."""
    text = cell.replace("\r\n", "\n").strip()
    if not text:
        return []
    return [
        [ln.strip() for ln in stanza.split("\n") if ln.strip()]
        for stanza in re.split(r"\n\s*\n", text)
        if stanza.strip()
    ]


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
            "latin": _split_stanzas(cells["la"]),
            "english": _split_stanzas(cells["en"]),
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
# Articles: one long-form piece per file in data/articles/
# --------------------------------------------------------------------------- #
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# A bare '&' that does not open a character reference: invalid HTML, and the
# easiest thing to type by accident when writing prose.
BARE_AMP_RE = re.compile(r"&(?!#\d+;|#x[0-9a-fA-F]+;|[a-zA-Z][a-zA-Z0-9]{1,31};)")


class _ArticleTagChecker(HTMLParser):
    """Walk an article body's tag stack so an unclosed, crossed, or disallowed
    tag is reported with the line number it occurs on in the source file."""

    def __init__(self, where: str, first_body_line: int) -> None:
        super().__init__(convert_charrefs=False)
        self.where = where
        # NB: NOT self.offset. ParserBase uses that name for the column, and
        # shadowing it silently corrupts every line number this class reports.
        self.first_body_line = first_body_line
        self.stack: list[tuple[str, int]] = []
        self.problems: list[str] = []

    def _line(self) -> int:
        return self.getpos()[0] + self.first_body_line - 1

    def handle_starttag(self, tag, attrs):
        if tag not in ARTICLE_TAGS:
            self.problems.append(
                f"{self.where} line {self._line()}: <{tag}> is not allowed in an "
                f"article body (allowed: {', '.join(sorted(ARTICLE_TAGS))})"
            )
            return
        if tag not in ARTICLE_VOID_TAGS:
            self.stack.append((tag, self._line()))

    def handle_endtag(self, tag):
        if tag in ARTICLE_VOID_TAGS:
            return
        if not self.stack:
            self.problems.append(f"{self.where} line {self._line()}: stray </{tag}>")
            return
        open_tag, open_line = self.stack[-1]
        if open_tag != tag:
            self.problems.append(
                f"{self.where} line {self._line()}: </{tag}> closes out of order; "
                f"<{open_tag}> opened on line {open_line} is still open"
            )
            return
        self.stack.pop()

    def finish(self) -> list[str]:
        self.close()
        for tag, line in self.stack:
            self.problems.append(f"{self.where} line {line}: <{tag}> is never closed")
        return self.problems


def check_article_body(body: str, where: str, first_body_line: int) -> list[str]:
    """Every problem in one article body, each located by source line."""
    checker = _ArticleTagChecker(where, first_body_line)
    checker.feed(body)
    problems = checker.finish()

    for n, line in enumerate(body.split("\n"), start=first_body_line):
        if BARE_AMP_RE.search(line):
            problems.append(f"{where} line {n}: bare '&' in text; write '&amp;'")
        if "—" in line:
            problems.append(
                f"{where} line {n}: em-dash in authored prose (house style forbids "
                f"it); recast with a comma, colon, semicolon, or parentheses"
            )
        # render() is a successive str.replace over the same string, so a literal
        # {{...}} surviving into the body would be substituted by the outer
        # base.html render. build_article_page passes content last, which already
        # prevents it; this refuses it at the source so the guarantee is visible.
        if "{{" in line:
            problems.append(
                f"{where} line {n}: '{{{{' is a template token delimiter and may "
                f"not appear in an article body"
            )
    return problems


def _split_front_matter(text: str, where: str) -> tuple[dict[str, str], str, int]:
    """Split 'key: value' header lines from the body at a line of exactly ---.
    Returns (metadata, body, first body line number). No YAML, no dependency."""
    lines = text.replace("\r\n", "\n").split("\n")
    meta: dict[str, str] = {}
    for n, line in enumerate(lines, start=1):
        if line.strip() == "---":
            missing = [k for k in ARTICLE_REQUIRED_KEYS if not meta.get(k)]
            if missing:
                fail(f"{where}: missing header field(s): {', '.join(missing)}")
            return meta, "\n".join(lines[n:]), n + 1
        if not line.strip():
            continue
        if ":" not in line:
            fail(f"{where} line {n}: header line is not 'key: value', and the "
                 f"header has not been closed by a line containing only ---")
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        known = ARTICLE_REQUIRED_KEYS + ARTICLE_OPTIONAL_KEYS
        if key not in known:
            fail(f"{where} line {n}: unknown header field '{key}'. "
                 f"Known fields: {', '.join(known)}")
        if key in meta:
            fail(f"{where} line {n}: duplicate header field '{key}'")
        meta[key] = value
    fail(f"{where}: the header is never closed (no line containing only ---)")


def render_article_body(body: str) -> str:
    """Blocks separated by blank lines. A block starting with '<' is authored
    markup and passes through untouched; every other block is one paragraph,
    its lines flowed together so prose may be wrapped freely in the source."""
    text = body.replace("\r\n", "\n").strip()
    blocks: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        if block.startswith("<"):
            blocks.append("      " + block.replace("\n", "\n      "))
        else:
            flowed = " ".join(s for s in (ln.strip() for ln in block.split("\n")) if s)
            blocks.append(f"      <p>{flowed}</p>")
    return "\n\n".join(blocks)


def load_articles() -> list[dict]:
    """Load every article in data/articles/, newest first. An empty or absent
    directory is fine: the section simply has nothing in it yet."""
    if not ARTICLES_DIR.is_dir():
        return []

    articles: list[dict] = []
    for path in sorted(ARTICLES_DIR.glob("*.html")):
        where = f"data/articles/{path.name}"
        slug = path.stem
        if not SLUG_RE.match(slug):
            fail(f"{where}: filename must be kebab-case; it becomes the URL")

        meta, body, first_line = _split_front_matter(
            path.read_text(encoding="utf-8"), where
        )
        if not ISO_DATE_RE.match(meta["date"]):
            fail(f"{where}: 'date' must be YYYY-MM-DD, got '{meta['date']}'")
        try:
            date = datetime.date.fromisoformat(meta["date"])
        except ValueError:
            fail(f"{where}: 'date' is not a real date: '{meta['date']}'")
        if meta.get("image") and not meta.get("image_alt"):
            fail(f"{where}: an 'image' also needs an 'image_alt' describing it")

        problems = check_article_body(body, where, first_line)
        if problems:
            fail("article body:\n  " + "\n  ".join(problems))

        articles.append({
            "id": slug,
            "title": meta["title"],
            "subtitle": meta["subtitle"],
            "description": meta["description"],
            "date": meta["date"],
            # "2 September 2026". Built by hand rather than with strftime, whose
            # no-pad day directive (%-d) is not portable.
            "date_human": f"{date.day} {MONTHS[date.month - 1]} {date.year}",
            "image": meta.get("image", ""),
            "image_alt": meta.get("image_alt", ""),
            "html": render_article_body(body),
        })

    # Newest first; the slug breaks ties so the order is stable across builds.
    articles.sort(key=lambda a: (a["date"], a["id"]), reverse=True)
    return articles


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
# A versicle / response line: "V. Angelus Domini…" / "R. et concepit…". Only a
# marker at the very start of a line counts, so an ordinary sentence is never
# caught. The marker is rubricated in the markup (see `.vr` in style.css), the
# same treatment the Rosary page gives its versicles.
VERSICLE_RE = re.compile(r"^[VR]\.(?=\s|$)")


def render_line(line: str) -> str:
    """Escape one line of prayer text, rubricating a leading V./R. marker."""
    marker = VERSICLE_RE.match(line)
    if not marker:
        return esc(line)
    return f'<span class="vr">{marker.group(0)}</span>{esc(line[marker.end():])}'


def render_stanzas(stanzas: list[list[str]]) -> str:
    """Render stanzas as separate ``<p class="prayer-stanza">`` blocks; the lines
    within a stanza are joined by ``<br>``. A single stanza (a prayer with no
    blank line in its source text) renders as one paragraph, as before."""
    blocks = []
    for stanza in stanzas:
        lines = "<br>\n".join("        " + render_line(line) for line in stanza)
        # A stanza opening on a versicle marks itself so the Latin drop-cap can
        # stand down: a two-line rubricated "V" would read as the opening word
        # of the prayer rather than as the versicle sign.
        css = "prayer-stanza"
        if stanza and VERSICLE_RE.match(stanza[0]):
            css += " has-versicle"
        blocks.append(f'      <p class="{css}">\n{lines}\n      </p>')
    return "\n".join(blocks)


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
        '  <a class="rosary-cta-link" href="/rosary/">Pray the Rosary'
        '<svg class="rosary-cta-arrow" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true">'
        '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg></a>\n'
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
        latin_stanzas=render_stanzas(prayer["latin"]),
        english_stanzas=render_stanzas(prayer["english"]),
        # Row-track count for the side-by-side subgrid: one row per stanza, so the
        # Latin and English stanzas line up across the gutter (see style.css).
        stanza_rows=str(max(len(prayer["latin"]), len(prayer["english"]), 1)),
        context=context,
        source=source,
        rosary_cta=rosary_cta,
    )

    page_desc = prayer["description"] or f'{prayer["title"]}, {prayer["subtitle"]} in Latin and English.'
    return render(
        base_tpl,
        root_attr="",
        page_title=esc(f'{prayer["title"]}, {prayer["subtitle"]}'),
        page_description=esc(page_desc),
        content=content,
        year=BUILD_YEAR,
        head_extra=head_extra(f'/prayers/{prayer["id"]}/'),
    )


def build_home_page(prayers: list[dict], base_tpl: str, index_tpl: str) -> str:
    """The root page: the hero band and the chapter sections, one per
    destination. It holds no prayer data of its own — the collection lives at
    /prayers/ (build_prayers_page) — but the collection's chapter states its
    size, and that count is taken from the data so it can never drift."""
    content = render(
        index_tpl,
        prayer_count=str(len(prayers)),
        category_count=str(len({p["category"] for p in prayers})),
        # The landing page carries the copyright inside its last band rather than
        # in the site footer (which it hides), so it needs the year of its own.
        year=BUILD_YEAR,
    )
    return render(
        base_tpl,
        # Marks the root element itself, so the rules that make this route what it
        # is (no scrollbar, dark canvas, the masthead riding on the band) are
        # matched before the browser paints. Keyed off `.hero` they could not be:
        # :has() cannot match an element that has not been parsed, so the page
        # painted once as an ordinary scrolling page, scrollbar and all, and then
        # corrected itself — the flash of a scrollbar appearing and vanishing.
        root_attr=' class="home"',
        page_title="Traditional Catholic Prayers in Latin",
        page_description=(
            "Traditional Catholic prayers in Latin with faithful English "
            "translations, and the fifteen mysteries of the Holy Rosary. "
            "In the defense of Tradition and the Tridentine Mass."
        ),
        content=content,
        year=BUILD_YEAR,
        head_extra=head_extra("/"),
    )


def build_prayers_page(
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
        root_attr="",
        page_title="Latin Prayers with English Translations",
        page_description=(
            "Latin prayers with faithful English translations: the Pater Noster, "
            "Ave Maria, Salve Regina, the Rosary, and other traditional Catholic "
            "prayers."
        ),
        content=content,
        year=BUILD_YEAR,
        head_extra=head_extra("/prayers/"),
    )


def article_jsonld(article: dict) -> str:
    """Per-article Article JSON-LD. There is no byline on this site, so the
    author is the publisher: an institutional voice, stated honestly rather than
    invented. dateModified is not tracked separately yet and equals the date."""
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article["title"],
        "description": article["description"],
        "datePublished": article["date"],
        "dateModified": article["date"],
        "inLanguage": "en",
        "url": f'{BASE_URL}/articles/{article["id"]}/',
        "author": {"@type": "Organization", "name": "latinprayers.org", "url": BASE_URL + "/"},
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
    return ('<script type="application/ld+json">'
            + json.dumps(data, ensure_ascii=False) + "</script>")


def build_article_page(article: dict, base_tpl: str, article_tpl: str) -> str:
    figure = ""
    if article["image"]:
        figure = (
            '<figure class="article-figure">\n'
            f'    <img src="{esc(article["image"])}" alt="{esc(article["image_alt"])}" loading="lazy">\n'
            "  </figure>"
        )

    content = render(
        article_tpl,
        title=esc(article["title"]),
        subtitle=esc(article["subtitle"]),
        date=esc(article["date"]),
        date_human=esc(article["date_human"]),
        figure=figure,
        # The body is authored markup and goes in last. render() replaces one key
        # after another over the same string, so anything substituted before the
        # body would be re-scanned inside it (a literal {{year}} in an article
        # would silently become the build year). check_article_body() also
        # refuses '{{' at the source, so this holds from both ends.
        body=article["html"],
    )
    return render(
        base_tpl,
        root_attr="",
        page_title=esc(article["title"]),
        page_description=esc(article["description"]),
        year=BUILD_YEAR,
        head_extra=head_extra(f'/articles/{article["id"]}/') + "\n  " + article_jsonld(article),
        content=content,
    )


def build_articles_page(articles: list[dict], base_tpl: str, articles_tpl: str) -> str:
    if articles:
        cards = "\n".join(
            f'    <li class="article-card">\n'
            f'      <a class="article-card-link" href="/articles/{esc(a["id"])}/">\n'
            f'        <time class="article-card-date" datetime="{esc(a["date"])}">'
            f'{esc(a["date_human"])}</time>\n'
            f'        <h2 class="article-card-title">{esc(a["title"])}</h2>\n'
            f'        <p class="article-card-subtitle">{esc(a["subtitle"])}</p>\n'
            f'        <p class="article-card-desc">{esc(a["description"])}</p>\n'
            f"      </a>\n"
            f"    </li>"
            for a in articles
        )
        listing = f'  <ul class="article-list">\n{cards}\n  </ul>'
    else:
        listing = (
            '  <p class="article-empty">The first articles are being written. '
            "In the meantime, the prayers themselves carry notes on their history "
            'and use: <a href="/prayers/">browse the prayers</a>.</p>'
        )

    content = render(articles_tpl, listing=listing)
    return render(
        base_tpl,
        root_attr="",
        page_title="Articles on Tradition and Catholic Living",
        page_description=(
            "Writings on the traditional Faith: the Latin tongue of the Church, "
            "the Tridentine Mass, and Catholic living."
        ),
        year=BUILD_YEAR,
        head_extra=head_extra("/articles/"),
        content=content,
    )


# The numbered how-to steps, read back out of the rendered markup. Parsing what
# we just wrote keeps the page itself the single source of truth for the steps,
# so the HowTo data cannot drift from what a reader actually sees.
ROSARY_STEPS_RE = re.compile(r'<ol class="rosary-steps">(.*?)</ol>', re.S)
LIST_ITEM_RE = re.compile(r"<li>(.*?)</li>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def rosary_steps(rosary_tpl: str) -> list[str]:
    """Plain-text of each step in the Rosary template's ordered list."""
    block = ROSARY_STEPS_RE.search(rosary_tpl)
    if not block:
        return []
    steps = []
    for item in LIST_ITEM_RE.findall(block.group(1)):
        text = html.unescape(TAG_RE.sub("", item))
        text = " ".join(text.split())
        if text:
            steps.append(text)
    return steps


def rosary_jsonld(steps: list[str]) -> str:
    """Page-specific JSON-LD for the Rosary page: what the page is (Article),
    what it teaches (HowTo, built from the steps on the page), and where it sits
    (BreadcrumbList).

    A note for whoever revisits this: the HowTo will not produce a rich result.
    Google retired HowTo rich results in 2023. It is here because it states the
    page's purpose unambiguously to search engines and to the LLM crawlers the
    SEO plan cares about, not because it earns a carousel."""
    today = datetime.date.today().isoformat()
    page_url = BASE_URL + "/rosary/"
    description = (
        "How to pray the traditional Holy Rosary in Latin: the order of "
        "prayers, and the fifteen Joyful, Sorrowful, and Glorious Mysteries "
        "with their Scripture and fruits."
    )
    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "How to Pray the Rosary in Latin",
        "name": "The Holy Rosary",
        "description": description,
        "inLanguage": "en",
        "about": {"@type": "Thing", "name": "Rosary"},
        "url": page_url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": page_url},
        "image": BASE_URL + "/assets/img/lepanto.webp",
        "dateModified": today,
        "isPartOf": {"@type": "WebSite", "name": "latinprayers.org", "url": BASE_URL + "/"},
        "publisher": {"@type": "Organization", "name": "latinprayers.org"},
    }
    howto = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": "How to Pray the Rosary in Latin",
        "description": description,
        "inLanguage": "en",
        "url": page_url,
        "supply": [{"@type": "HowToSupply", "name": "A set of Rosary beads"}],
        "step": [
            {"@type": "HowToStep", "position": i, "text": text, "url": f"{page_url}#step-{i}"}
            for i, text in enumerate(steps, start=1)
        ],
    }
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Prayers", "item": BASE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "The Rosary", "item": page_url},
        ],
    }
    blocks = [article, breadcrumb]
    if steps:
        blocks.insert(1, howto)
    return "\n  ".join(
        '<script type="application/ld+json">'
        + json.dumps(block, ensure_ascii=False)
        + "</script>"
        for block in blocks
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
                f'              <p class="decade-eyebrow">{esc(ordinal)} Mystery</p>\n'
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
        # The set rail sits inside the panels container, not before it: with JS
        # it is docked into the card's own top-right corner, and this is the
        # element it is positioned against. It still precedes the panels it
        # labels, and with no JS it simply renders above them as a plain row.
        '  <div class="mysteries-panels" id="mysteries">\n'
        '    <div class="mysteries-tabs" aria-label="The three sets of mysteries">\n'
        + "\n".join(tabs)
        + "\n    </div>\n"
        + "\n".join(panels)
        + "\n  </div>\n"
        "</section>"
    )

    content = render(rosary_tpl, mysteries=mysteries_html)
    page_desc = (
        "How to pray the traditional Holy Rosary in Latin: the order of prayers "
        "step by step, and the Joyful, Sorrowful, and Glorious Mysteries with "
        "their Scripture and fruits."
    )
    # The <title> carries the phrase a reader actually searches for; the page's
    # own display heading stays "The Holy Rosary" (see rosary.html).
    return render(
        base_tpl,
        root_attr="",
        page_title="How to Pray the Rosary in Latin",
        page_description=page_desc,
        content=content,
        year=BUILD_YEAR,
        head_extra=head_extra("/rosary/") + "\n  " + rosary_jsonld(rosary_steps(rosary_tpl)),
    )


# --------------------------------------------------------------------------- #
# Build orchestration
# --------------------------------------------------------------------------- #
def build() -> int:
    """Render the whole site into a fresh dist/. Returns the prayer count."""
    prayers = load_prayers()
    mysteries = load_mysteries()
    articles = load_articles()
    category_descriptions = load_category_descriptions()
    base_tpl = load_template("base.html")
    prayer_tpl = load_template("prayer.html")
    index_tpl = load_template("index.html")
    prayers_tpl = load_template("prayers.html")
    rosary_tpl = load_template("rosary.html")
    article_tpl = load_template("article.html")
    articles_tpl = load_template("articles.html")

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

    # The prayer index, at /prayers/. It shares the directory the individual
    # prayer pages are written into above, which is why this comes after them:
    # dist/prayers/index.html sits alongside dist/prayers/<id>/index.html and the
    # two never collide, since one is a file and the others are directories.
    prayers_out.mkdir(parents=True, exist_ok=True)
    prayers_index = prayers_out / "index.html"
    prayers_index.write_text(
        build_prayers_page(prayers, base_tpl, prayers_tpl, category_descriptions),
        encoding="utf-8",
    )
    print(f"  wrote {prayers_index.relative_to(ROOT)}")

    # Articles, at /articles/ and /articles/<slug>/. Emitted in the prayer
    # route's order for the same reason: the children are written first with
    # parents=True, then the index file is written alongside them into the
    # directory they created, so a file and its sibling directories never
    # collide. (The STANDALONE_PAGES emit below uses a bare mkdir() and could
    # not host children this way.)
    articles_out = DIST_DIR / "articles"
    for article in articles:
        page_dir = articles_out / article["id"]
        page_dir.mkdir(parents=True)
        out = page_dir / "index.html"
        out.write_text(
            build_article_page(article, base_tpl, article_tpl), encoding="utf-8"
        )
        print(f"  wrote {out.relative_to(ROOT)}")

    articles_out.mkdir(parents=True, exist_ok=True)
    articles_index = articles_out / "index.html"
    articles_index.write_text(
        build_articles_page(articles, base_tpl, articles_tpl), encoding="utf-8"
    )
    print(f"  wrote {articles_index.relative_to(ROOT)}")

    # Render the homepage.
    index_out = DIST_DIR / "index.html"
    index_out.write_text(build_home_page(prayers, base_tpl, index_tpl), encoding="utf-8")
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
                root_attr="",
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

    # robots.txt and sitemap.xml, generated so their URLs derive from BASE_URL.
    write_robots(DIST_DIR)
    write_sitemap(prayers, articles, DIST_DIR)

    # Custom 404 page. GitHub Pages serves /404.html for unknown paths; it is
    # marked noindex (it stands in for many URLs) and carries no canonical.
    not_found_tpl = load_template("404.html")
    (DIST_DIR / "404.html").write_text(
        render(
            base_tpl,
            root_attr="",
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
        articles = load_articles()
        templates = ["base.html", "prayer.html", "index.html", "prayers.html",
                     "404.html", "rosary.html", "article.html", "articles.html"]
        templates += [f"{slug}.html" for slug, _, _ in STANDALONE_PAGES]
        for name in templates:
            load_template(name)
        print(f"OK: {len(prayers)} prayer(s), {len(mysteries)} mystery(ies), "
              f"{len(articles)} article(s), and templates validated.")
        return

    count = build()
    print(f"Done: {count} prayer(s) built into {DIST_DIR.name}/.")


if __name__ == "__main__":
    main()
