# CLAUDE.md — Working notes for latinprayers.org

This file is the standing brief for any AI/Claude session working on this repo.
Read it first. Keep it current: when an architectural decision is made, record it
here so future sessions don't re-litigate it.

## What this site is

**latinprayers.org** — that is the *name* of the project, not merely its domain.

**Motto:** *In the defense of Tradition, the Tridentine Mass, and Catholic living.*

A central, reverent repository of **prayers in Latin** (Pater Noster, Ave Maria,
Gloria Patri, …). Its purpose is apostolic: to draw people toward the traditional
branch of Catholicism — the Tridentine (Latin) Mass, Catholic monarchy ideals,
traditional Catholic living and values.

## Editorial doctrine (non-negotiable)

- **Fidelity to Tradition over modern convention.** Present traditional Catholic
  teaching faithfully. Do **not** soften, secularize, or "balance" content to suit
  contemporary or modernist sensibilities, and do not insert editorial moral
  judgements of your own.
- **Authentic texts only.** Use the received traditional Latin texts and faithful
  traditional translations (e.g. Douay–Rheims register: "Holy Ghost," "thy,"
  "world without end"). When unsure of a text, flag it for the maintainer rather
  than improvising. Liturgical/devotional accuracy matters more than polish.
- The maintainer is the doctrinal authority. When a content question is genuinely
  ambiguous, ask — do not guess on matters of faith.
- **House style: no em-dashes.** Do not use the em-dash (`—`) in authored
  prose/content (prayer `context`, `description`, page copy). Recast the sentence
  with a comma, colon, semicolon, or parentheses instead. (En-dashes in numeric or
  scripture ranges such as `6:9–13` are fine and should be kept.)

## Technical doctrine (non-negotiable)

- **Static site. No server, no backend, no database.** Output is plain
  HTML + CSS + JS that runs in any browser straight off the filesystem / GitHub Pages.
- **No frameworks. No runtime dependencies.** No React/Vue/Tailwind/jQuery, no CDN
  libraries. Vanilla everything. JS is for *progressive enhancement only* — every
  page must be fully readable with JS disabled.
- **Self-hosted fonts are allowed; third-party font CDNs are not.** The two faces
  (Cormorant Garamond for display headings, EB Garamond for reading text) live as
  committed `.woff2` files in `assets/fonts/`, declared via `@font-face` in
  `style.css` and preloaded in `base.html`. Nothing is fetched from Google Fonts or
  any CDN at runtime, so this stays within "everything centralized in this repo."
  Subsets are split by `unicode-range` (latin / latin-ext) so the extended face is
  fetched only when an extended glyph actually appears (today's content needs none).
- **A build step is allowed, but only at build time.** Content lives once in
  `data/`; `build.py` (Python 3, **standard library only** — nothing to `pip install`)
  renders it through `templates/` into committed static HTML. The published output
  has zero build artifacts and zero JS frameworks.
- **Everything is centralized in this repo.** No external services, no user-generated
  content, no third-party content fetched at runtime.
- **Purity and precision over speed.** MVP-driven and iterative, yes — ship a small
  working prototype and refine it — but no spaghetti. Keep things clean, small, and
  legible. Avoid large refactors in a single session.

## Repository layout

Only source is committed. The rendered HTML is **never committed** — it is built
on every push by GitHub Actions and published from the `dist/` artifact.

```
/
├── data/
│   ├── prayers.csv       # SOURCE OF TRUTH — one row per prayer
│   ├── mysteries.csv     # the fifteen Rosary mysteries (one row each)
│   └── categories.csv    # optional one-line blurb per homepage category
├── templates/
│   ├── base.html         # outer HTML shell (header, footer, <head>)
│   ├── index.html        # the root landing page (hero + chapter sections)
│   ├── prayers.html      # the prayer index (search + category lists) at /prayers/
│   └── prayer.html       # single-prayer content block
├── assets/
│   ├── css/style.css     # hand-authored styles
│   ├── fonts/            # self-hosted woff2 (Cormorant Garamond, EB Garamond)
│   └── js/main.js        # hand-authored, minimal, optional-enhancement only
├── build.py              # the generator (stdlib only) — emits dist/
├── serve.py              # local dev server: build + serve dist/ (stdlib only)
├── dist/                 # GENERATED output, gitignored — the published site
├── .github/workflows/
│   └── deploy.yml        # CI: build on push to main, deploy dist/ to Pages
├── CNAME                 # custom domain (copied into dist/ by build.py)
├── .nojekyll             # disable Jekyll (copied into dist/ by build.py)
├── .gitignore
├── README.md
└── CLAUDE.md             # this file
```

**`dist/` is disposable.** `build.py` wipes and regenerates it from scratch each
run. It contains the rendered HTML plus copies of `assets/`, `CNAME`, and
`.nojekyll`, making it the exact, self-contained set of files served to the world.
Never hand-edit anything in `dist/`; edit the source and rebuild.

## The content model (a prayer)

All prayers live in a single spreadsheet, `data/prayers.csv` — **one row per
prayer**. It is plain UTF-8 CSV, so it opens and saves as a normal sheet in Excel
or Google Sheets, and `build.py` parses it with the stdlib `csv` module (no
dependency). Columns (header row, in order):

| column        | meaning                                                              |
|---------------|----------------------------------------------------------------------|
| `slug`        | kebab-case id; must be unique. Becomes the URL `/prayers/<slug>/`.   |
| `title`       | Latin title (the primary heading).                                   |
| `subtitle`    | common English name.                                                 |
| `category`    | grouping for the index.                                              |
| `order`       | integer sort key within category (lower = first); blank → 1000.      |
| `description` | 1–2 sentences of context; optional (may be blank).                   |
| `la`          | Latin text — **one line per line**, line breaks *inside the cell*. A **blank line** marks a **stanza break**. |
| `en`          | faithful English translation, line-aligned with `la` (same lines and same stanza breaks). |
| `context`     | longer prose on history/origin/use; optional. **Paragraphs** split on blank lines within the cell. Renders as the "About this prayer" section below the text. |
| `source`      | optional label override for the link text. Blank → the link shows the route from `source_url` with the scheme stripped (e.g. `fisheaters.com/prayers.html`). |
| `source_url`  | optional URL of the translation source. When present, a muted "Translation source" link is shown just below (outside) the text card. Both blank → no line. |

- `slug`, `title`, `subtitle`, `category`, `la`, `en` are required and non-empty.
- `la` and `en` hold **multiple lines within a single cell** (Alt/Option+Enter in
  a spreadsheet). `build.py` splits each cell on newlines into the line array, so
  the two columns still align line-by-line. Keep them parallel (same logical lines)
  where the translation allows.
- A **blank line within a cell separates stanzas.** `build.py` groups the lines
  into stanzas (splitting on blank lines) and renders each stanza as its own
  `<p class="prayer-stanza">`, so a long prayer reads in its received stanzas
  rather than as one wall of text. A cell with no blank line is a single stanza and
  renders exactly as before. Put the **same stanza breaks in `la` and `en`** so the
  two columns stay parallel. Break points should follow the prayer's traditional
  structure (metrical stanzas for hymns, the credal articles for the Creeds, the
  movements of a canticle, the salutation/petition seam of a short prayer); truly
  atomic prayers (Signum Crucis, Gloria Patri, Requiem) are left whole.
- **Versicles and responses are rubricated automatically.** A line that *begins*
  with `V.` or `R.` (followed by a space) has its marker wrapped in
  `<span class="vr">` and set in liturgical red, the same treatment the Rosary
  page gives its versicles. Nothing to mark up by hand: write the line plainly in
  the CSV and `build.py` finds it. A `V.` anywhere other than the start of a line
  is left alone. When a stanza *opens* on a versicle, the Latin drop-cap stands
  down for that prayer (see `.has-versicle` in `style.css`), since capitalising
  the `V` of the marker would read as the prayer's first word.
- Column names `la`/`en` are the ISO 639-1 codes; markup tags them `lang="la"` /
  `lang="en"`.
- Display is **Latin + English side-by-side** (collapses to stacked on small screens).

## Reference: translation sources (for vetting prayer text)

When adding or checking a prayer's English, these were found useful. The site uses
the **traditional Douay register** ("Holy Ghost," "world without end," "amongst
women"); **keep that form even when a source has modernized it.** Most mainstream
sites have changed "Holy Ghost" → "Holy Spirit" and "amongst" → "among," so prefer
the traditional sources for exact-match citations.

- **[fisheaters.com/prayers.html](https://fisheaters.com/prayers.html)** — traditional Catholic prayer collection; preserves the traditional forms ("amongst women," "trespasses"). Currently cited as the `source` for the three common prayers.
- **[catholicity.com](https://www.catholicity.com/prayer/prayers.html)** — matches the traditional Pater Noster and Ave Maria verbatim (incl. "amongst women").
- **[ourcatholicprayers.com](https://www.ourcatholicprayers.com/Latin-Prayers.html)** and **[prayinglatin.com](https://www.prayinglatin.com/prayers-of-the-rosary-in-latin/)** — Latin + English, traditional wording.
- **[EWTN — Rosary in English & Latin](https://www.ewtn.com/catholicism/teachings/prayers-of-the-rosary-in-english-and-latin-164)** — authoritative, but modernized ("Holy Spirit," "among women").
- **Vatican** — Compendium of the Catechism, appendix of common prayers (vatican.va): authoritative Latin, modernized English.
- **Baltimore Catechism** (hosted as PDF on fisheaters) — classic pre-conciliar reference.

## How to build and preview

```bash
python3 build.py          # build the site into dist/
python3 build.py --check  # validate data + templates only, write nothing

python3 serve.py          # build once, then serve dist/ at http://localhost:8000
python3 serve.py --watch  # also rebuild automatically when source files change
python3 serve.py --port 8080
```

`build.py` reads `data/prayers.csv`, validates every row, and renders the static
site into `dist/`. **Do not commit `dist/`** — it is gitignored and rebuilt by CI.

## How to add a prayer (the common task)

1. Open `data/prayers.csv` (in Excel/Google Sheets or any editor) and add **one
   row** following the columns above. Put each verse on its own line within the
   `la`/`en` cells. Use authentic traditional Latin and a faithful traditional
   English translation.
2. Preview with `python3 serve.py --watch` and review the rendered page.
3. Commit **only** `data/prayers.csv` (and any template/asset changes). Never the HTML.
4. Push to `main`; CI builds and publishes.

## Populating many prayers: work incrementally, one row at a time

When adding prayers in bulk, **add them to `data/prayers.csv` one row at a time, not
in a single large dump.** For each prayer: obtain its text from a recommended
traditional source and verify the wording, append that one row, run
`python3 build.py --check`, then move to the next. Do **not** fetch or draft a dozen
prayers and then write them all back from memory in one pass.

Why: these are sacred texts where accuracy is the whole point. One row at a time
keeps every text verifiable on its own, isolates any error to a single row, and
avoids relying on recall to reproduce many texts at once.

Append programmatically with the stdlib `csv` module (read the existing file, add
the one new row, write it back); this keeps multi-line `la`/`en` cells and embedded
quotes correctly escaped. Never hand-edit the CSV's quoting. Because the prior rows
are re-read from disk rather than retyped, earlier work is never disturbed.

A note on sourcing: `WebFetch` will often refuse to echo a source page that carries
a site-level copyright notice, even for public-domain liturgical text. Verify
wording with small, targeted questions (one or two short prayers at a time), or by
asking it to confirm and correct a text you supply, rather than asking it to
reproduce a whole page.

## Standalone pages (e.g. the Manifesto)

Pages that aren't prayers (Manifesto, and later About/etc.) are plain content
templates rendered through `base.html`. To add one: create `templates/<slug>.html`
holding the content block, then register it in the `STANDALONE_PAGES` tuple in
`build.py` as `(slug, title, description)`. It is emitted to `dist/<slug>/index.html`
and served at the clean URL `/<slug>/`. Link to it with an absolute path
(`/<slug>/`). Image placeholders use `<div class="placeholder">` with a fixed
`aspect-ratio`; replace each with an `<img>` (in `assets/img/`) when the art exists.

## Deployment

Push to `main` → GitHub Actions (`.github/workflows/deploy.yml`) runs `python3
build.py` and publishes the `dist/` artifact to GitHub Pages. `CNAME` (copied into
`dist/`) binds the site to `latinprayers.org`.

**One-time setup required:** in repo *Settings → Pages*, set **Source = "GitHub
Actions"** (not "Deploy from a branch"). DNS is configured at Cloudflare (apex
`A`/`AAAA` records to GitHub Pages IPs, `www` `CNAME` to `<user>.github.io`).

## Page structure: the root page is a landing page, not the index

**The prayer index lives at `/prayers/`, not at `/`.** This was a deliberate
split, so it does not need re-deciding:

- **`/`** (`templates/index.html`) is a landing page: a full-screen hero band of
  the Crucifixion carrying only its title, then `.chapters` — **one full-width
  section per destination**, not a row of cards. Each `.chapter` breaks out of
  `.wrap` to the viewport edges and is built the way the hero is: its picture is
  its **ground**, a real `<img class="chapter-bg">` under a scrim, never a framed
  object beside the text (`.chapter--band` + `.chapter--dark`). The scrim is
  horizontal, carrying the text on one side and leaving the picture lit on the
  other; `.chapter--reverse` mirrors it so consecutive bands alternate which
  side the words hold. On phones the text runs full width, so the scrim becomes
  an even veil. Each band carries a `.chapter-list` glimpse of what it links to
  (a few prayers; the three sets of mysteries) above its call to action.
  **Every band is at least one viewport tall (`100svh`).** The wheel is taken
  over and given weight on **every route**, not only this one (`initFloatScroll`
  in `main.js`): the weight is how the site scrolls, not a trick the landing page
  does, and nothing on the site scrolls inside the page (the one `overflow-x:
  auto` track, the Mysteries tabs, is horizontal, and sideways wheels are let
  through), so taking the wheel over cannot make anything unreachable.
  The wheel no longer moves the page directly: each notch adds to a target the
  page then chases, closing a share of the remaining gap every frame
  (`FLOAT_PULL`), so the page travels on for a moment after the fingers stop and
  coasts to rest by itself. The share is per 60Hz frame and is scaled by the
  frame's real duration, so the feel does not depend on the monitor's refresh
  rate. Nothing is committed and nothing is squared up: the reader may stop
  anywhere, including halfway between two bands (off the landing page there are
  no bands and nothing to land on: the weight is simply how the page moves).
  Between glides the loop is not
  running at all, so anything else that moves the page (a scrollbar drag, a
  keyboard, an anchor jump) simply wins, and the next gesture reads the position
  back off the page rather than hauling it to where the loop last left it.
  There is **no CSS scroll-snap** on this page, and **no magnet** onto the
  nearest band's top: two things pulling at one scroll position fight each other,
  and a tug at the end of every glide reads as the page correcting the reader.
  Two designs were built and removed, recorded here so they are not re-attempted:
  turning a screen at a time (one gesture committing the whole move to the next
  band, with a momentum lock and a settle delay) which read as a snap the reader
  could not stop inside; and cross-fading the bands in a pinned stack, a great
  deal of machinery for an effect that fought ordinary reading. One trap is worth
  keeping in mind for anything here ever driven from script: `scroll-behavior:
  smooth` is set on the root and `window.scrollTo(x, y)` OBEYS it, so a script
  writing the scroll every frame has the browser easing toward the script's
  easing and never arriving — the loop sets it to `auto` while it drives and
  restores it after.
  **It only ever runs on a pointer-driven desktop window.** `takeover()` in
  `initFloatScroll` asks four questions LIVE, on every event rather than once at
  load, since a window gets resized, a phone rotated and a keyboard detached under
  pages that are already open: `pointer: coarse` (a touch flick already carries its
  own momentum and its own rubber-band, and taking the gesture over replaces both
  with a worse copy, so this is a mouse-and-trackpad idea), `max-width: 48rem`
  (the phone layout, which `pointer: coarse` alone would miss on a narrow laptop
  window), `max-height: 34rem`, and `prefers-reduced-motion`. Note `rem` in a media
  query means 16px, not the root's 18px, so 48rem is 768px in both the CSS
  breakpoint and this guard, and the two agree by construction.
- **The words fade with the band that carries them.** `initTextFade` in `main.js`
  holds each text block on the landing page (`.hero-title` and every
  `.chapter-body`) at full strength while it is near the middle of the screen and
  fades it out as it leaves, in either direction, on a smoothstep between
  `FADE_HOLD` and `FADE_EDGE`. The measure is the gap from the middle of the
  screen to the block's **nearest edge**, not the distance between the two
  centres: a block taller than half the screen (a chapter body on a phone, where
  the bands stack) straddles the middle for as long as it is being read, and
  centre-to-centre would fade it out from under the reader. Unlike the wheel
  takeover this runs everywhere, touch included, since it is about what is on
  screen rather than about how the page is being driven; `prefers-reduced-motion`
  turns it off, asked live, and puts any part-faded text back. One trap: a CSS
  animation outranks an inline style, and `.hero-title` carries `hero-rise` with
  `animation-fill-mode: both`, so its fill would keep overriding the fade even
  after the entrance had ended. The entrance is therefore left alone while the
  title is still at rest and full, and stood down (hurried to its end, then
  `animation: none`) at the first moment the fade wants something else from it.
- **The masthead pins itself and condenses once the page moves.** `initStickyHeader`
  in `main.js` puts two classes on `<html>`: `hdr` (the enhancement is running)
  and `hdr-stuck` (the page has moved past `HEADER_ON`, and back open below
  `HEADER_OFF` — two thresholds, because a bar that flips at a single line
  flutters for anyone resting on it). Everything about how it looks is in
  `style.css` under `.hdr`: the bar goes `sticky` on ordinary routes and `fixed`
  on the two that ride on top of a band (`.home` and `body:has(.page-band)`,
  which are already out of the flow and so cannot stick). Condensing takes the
  Sacred Heart mark down to 2rem and the wordmark a size, folds the motto away
  with a max-height, drops the nav's `New` badge (an announcement for someone
  arriving, not something to carry down the page), and swaps the bar's ground
  from `--masthead` to `--masthead-veil` behind a blur, since pinned it is over
  the reading rather than above it. The veil is not `--masthead` thinned but a
  lighter, warmer grey-brown: a near-black slab crossing ivory paper is the
  harshest edge on the site. It resolves to about `#5c5752` over the paper where
  `backdrop-filter` is unsupported and holds 6.3:1 for ivory type there, so there
  is no `@supports` gate; the nav links firm up from their resting 0.74 alpha to
  full ivory while pinned, because at 0.74 they measure 4.3:1 on that ground, a
  shade under what small caps need.
  **A third class, `hdr-paper`, says which surface the bar is crossing.** A dark
  veil is right over a photograph and wrong over the reading, and the same page
  is both: a prayer opens on its band and runs onto ivory a screen later. So
  `initStickyHeader` asks on every frame whether the bar's own lower edge is
  still inside one of the site's dark grounds (`.hero`, `.chapter`, `.page-band`)
  and, when it is not, the bar stops being chrome laid over the page and becomes
  the page's surface instead: the same frosting in the paper's colour with the
  paper's ink on it (ink 15.4:1, `--ink-soft` for the nav 5.7:1, `--gold-deep` on
  hover 5.5:1; worst case with a dark prayer card passing under the blur, 12.6:1
  and 4.7:1). It is a live question, not a route rule. **The veil is mixed from
  `--ivory`, not `--surface`, and that alone is not enough:** body's radial pool
  of light is `background-attachment: fixed`, so it never scrolls away — it sits
  at the top of the viewport permanently, right under the pinned bar, making the
  backdrop there about `#fefcf6` rather than the flat `#f6f1e7` the rest of the
  page shows. Anything translucent pinned to the top of this site reads lighter
  than its own colour for that reason. `saturate()` also comes off for this
  state: on a warm near-neutral it only pushes the paper creamier. Two specificity traps live
  in that block, both commented in place: the paper background needs an `html`
  prefix to outweigh the `body:has(.page-band)` stuck rule (the prayer pages are
  exactly the ones that run onto paper), and both hover colours have to be
  restated, or the bar keeps its new colours and loses its hover.
  Because every rule hangs off `hdr`, a page with no JS keeps the plain
  scroll-away bar it always had. It is off below 48rem, asked live: a two-row
  masthead pinned to the top of a phone is a third of the screen spent on
  navigation. Two things to know if it is touched. The overlay routes set a
  z-index of their own further down the file, so the fixed rule repeats
  `z-index: 30` (at equal specificity the later rule would win and leave the bar
  on 2). And a masthead that stays put means in-page links land underneath it,
  so every `scroll-margin-top` on the site adds `var(--anchor-clear)`, which is
  `0` at `:root` and the condensed bar's height under `.hdr`.
- **Route-level rules hang off a class on `<html>`, not `:has()`.** `build.py`
  fills `{{root_attr}}` in `base.html`, and the landing page alone gets
  `class="home"`; everything that makes that route what it is (no scrollbar, dark
  canvas, the masthead riding on the band, no footer) is keyed off it. It used to
  be keyed off `body:has(.hero)`, and that is a trap: **`:has()` cannot match an
  element that has not been parsed yet**, so those rules only began applying once
  the middle of the document arrived. The page painted first as an ordinary
  scrolling page and then corrected itself, which showed as a flash of scrollbar
  appearing and vanishing on entry. A class on the root element is there before
  the first paint. (`body:has(.page-band)` on the prayer pages has the same
  latency; it has not bitten because those pages change no widths, but the same
  fix applies if it ever does.)
- **Every route keeps its scrollbar, and it must stay that way.** Hiding it on the
  landing page alone made that route ~15px wider than the rest, and three separate
  faults all traced back to that one asymmetry: the masthead shifting half a
  scrollbar between routes, a strip of bare canvas down the right where the bands
  could not reach (a merely *invisible* bar still holds space no content can paint
  into), and a flash on entry as the bar came and went. `scrollbar-gutter: stable`
  cannot rescue any of it: a bar of no width has no gutter to hold open (measured).
  The only reliable cure is that all routes agree. Do not reintroduce the split:
  the machinery it needs (a JS-measured `--sbw`, a compensating pad on the
  masthead) is more than the look is worth. Only the bar's **colour** varies, on
  `.home`, which is layout-neutral. `scrollbar-gutter: stable` stays on the root
  for the remaining case: a page too short to scroll has no bar at all. Verify
  with `.site-header .wrap`'s left edge, which must read the same on every route.
- **Clean URLs.** Each prayer is emitted as `dist/prayers/<id>/index.html` and served
  at `/prayers/<id>/` (no `.html` suffix). The homepage is `/`. All in-page links and
  asset references use **absolute paths from root** (`/`, `/prayers/<id>/`,
  `/assets/...`). This relies on the site being served from the domain root — true
  for the apex custom domain and for `serve.py`. (Consequence: opening a built file
  directly via `file://` won't load assets; always preview with `serve.py`.)
- Latin gets `lang="la"`, English gets `lang="en"` in markup.
- Never hand-edit generated files; edit the source (`data/`, `templates/`, `assets/`)
  and rebuild.
- Prefer adding to the data/template layer over special-casing individual pages.

## Roadmap / ideas parking lot

(Not commitments — a place to record ideas so they aren't lost.)

- Category index pages; search/filter on the homepage (JS progressive enhancement).
- Ecclesiastical-Latin pronunciation guides / audio.
- Sections beyond prayers: the Tridentine Mass (Ordinary, propers), the Rosary,
  Litanies, the Divine Office, catechetical/essay content on Tradition.
- Copy-to-clipboard and print-friendly stylesheet.
- **SEO / discoverability.** A full audit and prioritized plan lives in
  [`docs/seo-audit-and-plan.md`](docs/seo-audit-and-plan.md). The P0 build-time
  foundations are implemented in `build.py`: `robots.txt` (with AI-crawler policy),
  generated `sitemap.xml`, canonical links from a single `BASE_URL`, site-wide
  `WebSite`/`Organization` JSON-LD, and a noindex `404.html`. Still open (P1/P2):
  Open Graph cards, per-prayer `CreativeWork`/`BreadcrumbList` JSON-LD, an About
  page, `llms.txt`, title/description tuning, and the `www`-to-apex 301 (DNS).
