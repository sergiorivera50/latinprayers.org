# The Rosary page: development and ideas

Tracks the design, decisions, and backlog for `/rosary/`. Like the SEO doc, this
file is internal: it is not published (the build only emits `templates/`, `data/`,
`assets/`).

## Decisions (settled with the maintainer)

- **Traditional 15 only.** Joyful, Sorrowful, and Glorious Mysteries. The Luminous
  Mysteries (added 2002) are deliberately omitted, consistent with the site's
  traditional doctrine. (Encoded as a comment on `ROSARY_SETS` in `build.py`.)
- **One rich static page first.** A single reverent `/rosary/` page, fully usable
  with JavaScript disabled. Interactivity (a guided "pray-along") is deferred.
- **Per mystery we show:** Latin + English name, the traditional spiritual fruit,
  a Scripture citation, a 1-2 sentence meditation, and an art placeholder.

## What is implemented (MVP)

- `data/mysteries.csv` (one row per mystery: `set, order, la, en, scripture,
  fruit, meditation`), so mysteries are as editable as prayers.
- `build.py`: `load_mysteries()`, `build_rosary_page()`, a generated inline-SVG
  bead diagram (`rosary_diagram_svg()`), and page-specific `Article` JSON-LD. The
  page is emitted to `dist/rosary/index.html` at `/rosary/`, added to the sitemap,
  and validated by `build.py --check`.
- `templates/rosary.html`: intro (Dominic, Lepanto, Leo XIII, Fatima, indulgences),
  "how to pray" steps that **link to the existing prayer pages**, the three
  mystery sets (`{{mysteries}}`), and the concluding prayers
  (Salve Regina link, the versicle, and the collect in Latin and English).
- `templates/base.html`: the "The Rosary" nav item is now an active link.
- Styles for the page added to `assets/css/style.css`.

## Review items for the maintainer (doctrinal authority)

- **Latin mystery names**: a few have variant forms (e.g. Coronatio Spinea /
  Spinis; Baiulatio / Portatio Crucis). Confirm or adjust in `data/mysteries.csv`.
- **Fruits of the mysteries**: these vary by manual (e.g. the Nativity's fruit is
  given as "holy poverty" or "love of God"). The set used is the common one.
- **Meditations**: authored in the site's register for your review; edit freely.
- **The concluding collect** ("Deus, cuius Unigenitus...") and the Salve Regina
  versicle: standard traditional texts; confirm wording.
- **Day assignments**: now shown per mystery set ("Prayed on ..."); the standalone
  schedule table was removed as redundant.

## Backlog / ideas (not commitments)

- **Guided "pray-along" mode** (JS progressive enhancement): step bead-by-bead,
  showing the current prayer text and the current mystery + meditation, with
  Next/Prev and progress. The static page stays the fallback.
- **"Today's mysteries"** highlight based on the day of the week (JS).
- **Sacred art** per mystery, replacing the numeral placeholders (`.mystery-figure`).
- **Latin audio** with ecclesiastical pronunciation (ties into the site-wide
  audio/pronunciation idea).
- **Per-set sub-pages** (`/rosary/joyful/` etc.) for more depth and SEO, if wanted.
- **HowTo JSON-LD** with explicit `HowToStep`s for the praying sequence (richer
  than the current `Article`), and `BreadcrumbList`.
- **The fifteen promises of the Rosary** and the **Litany of Loreto** as related
  devotions (the Litany could become its own data-driven page).
- **Printable Rosary card** (print stylesheet refinements).
- A **link from the Marian prayers** (and the Fatima Prayer) back to `/rosary/`.
