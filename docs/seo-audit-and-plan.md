# SEO and Generative-Engine (LLM) Audit and Plan — latinprayers.org

Status: analysis and plan only. Nothing in this document is implemented yet.
Date: 2026-06-19. Scope: the whole site as built into `dist/` (34 prayers across
9 categories, plus the homepage).

**Implementation status (updated 2026-06-19):** the P0 build-time foundations are
now in place in `build.py`: `robots.txt` (with the AI-crawler policy), a generated
`sitemap.xml`, self-referencing canonical links derived from a single `BASE_URL`,
site-wide `WebSite` + `Organization` JSON-LD, and a custom noindex `404.html`.
Still open: the `www`-to-apex 301 (a Cloudflare/DNS step, not in this repo),
Search Console and Bing verification, and the P1/P2 items below (Open Graph cards,
per-prayer `CreativeWork`/`BreadcrumbList` JSON-LD, title and description tuning,
the About page, `llms.txt`, related links, category pages, FAQ blocks, and Core
Web Vitals polish).

This report is internal working documentation. It is not published: `build.py`
only emits `templates/`, `data/`, and `assets/`, so a file under `docs/` never
reaches `dist/`.

A guiding constraint runs through every recommendation: the site's technical
doctrine (static output, no frameworks, no runtime dependencies, a stdlib-only
`build.py`, progressive enhancement, no content fetched at runtime). Everything
proposed here is achievable at build time as plain HTML/XML/text. The one place
where SEO best practice rubs against the doctrine is third-party analytics, and
that tension is called out explicitly in the Measurement section.

---

## 1. Executive summary

**The content is the strength; the technical and discoverability layer is the
gap.** The prayers now carry authentic bilingual text, original context prose,
and outbound source citations. That is exactly the kind of unique, trustworthy,
well-structured material that both classic search and AI answer engines reward.
What is missing is almost entirely machine-facing plumbing that tells crawlers
and language models what the pages are, that they exist, and which URL is
canonical.

Highest-leverage work, in order:

1. **Crawl and indexation foundations** (P0): `robots.txt`, `sitemap.xml`, a
   self-referencing `<link rel="canonical">`, and a custom `404.html`. Cheap,
   build-time, and a prerequisite for everything else.
2. **Structured data (JSON-LD)** (P0/P1): `WebSite` + `Organization` site-wide,
   `BreadcrumbList` and a `CreativeWork` per prayer. This is the single biggest
   differentiator for both Google rich results and LLM extraction.
3. **Social and title/description metadata** (P1): Open Graph + Twitter cards,
   a sharable default image, and sharper title/description templates that target
   the real queries ("X in Latin and English").
4. **GEO / LLM readiness** (P1): an explicit AI-crawler policy in `robots.txt`,
   an `/llms.txt` site map for models, a concise definitional first sentence per
   page, and optional FAQ blocks.
5. **E-E-A-T** (P1): a published About page establishing mission, editorial
   standards, and sourcing methodology. Religious content is held to a high
   trust bar; the site already cites sources, but it does not yet state who
   stands behind it or how texts are vetted.
6. **Core Web Vitals** (P2): dimension the hero image, set LCP priority, lazy
   below-the-fold images, reconsider `background-attachment: fixed` on mobile.

None of this requires JavaScript, a framework, or a runtime dependency.

---

## 2. Current-state audit

### What is already good

- **Clean, semantic, stable URLs**: `/` and `/prayers/<slug>/` with no `.html`
  suffix; kebab-case ASCII slugs. Stable URLs matter a great deal for both link
  equity and LLM citation.
- **Apex custom domain over HTTPS** (`latinprayers.org` via `CNAME`, GitHub
  Pages + Cloudflare). TLS and a real domain are baseline trust signals.
- **Valid head basics on every page**: `charset`, `viewport` (mobile-friendly),
  a unique `<title>` (`{page} · latinprayers.org`), a unique
  `<meta name="description">`, favicon and apple-touch-icon, one stylesheet.
- **One `<h1>` per page**, sensible heading order (index: `h1` then category
  `h2`s; prayer: `h1` title, then `h2` "About this prayer").
- **Language signalling**: `<html lang="en">`, with Latin runs tagged
  `lang="la"` inline. Correct and useful.
- **Accessibility that doubles as SEO**: skip link, descriptive `aria-label`s,
  meaningful `alt` on the hero image, decorative brand mark with empty `alt`.
- **Genuinely unique, deep content**: side-by-side Latin/English plus original
  "About this prayer" prose and a cited translation source. This is rare in the
  niche and is the site's competitive moat.
- **Fast by construction**: system-font stack (no web-font request), one small
  CSS file, effectively no JS. A strong starting point for Core Web Vitals.

### What is present but weak

| Area | Current state | Issue |
|---|---|---|
| Title tags | `{title}, {subtitle} · latinprayers.org` | Does not target "in Latin / English" queries; long ones (e.g. Veni Sancte Spiritus) overflow the SERP snippet. |
| Meta descriptions | Reuse the short `description` field | Some are very short (~60 chars), leaving snippet space and keywords unused. |
| Prayer `<h1>` | Latin title only | English name sits in a `<p>`; fine, but the primary English query term is not in the H1. |
| Internal linking | Index links to all prayers; prayer pages link only back to `/` | No related-prayer links, no category anchors, no category landing pages. Shallow link graph. |
| Breadcrumb | A single "All prayers" backlink | Not a true Home > Category > Prayer trail; no `BreadcrumbList` markup. |
| Images | Hero `christ.webp` has no `width`/`height` | Layout shift (CLS) risk; no `fetchpriority`/preload for the LCP image. |
| `main.js` | Empty placeholder | Fine, but no on-site search means no `WebSite` SearchAction and a harder time as the catalogue grows. |

### What is missing entirely

- `robots.txt` (confirmed absent in repo and `dist/`).
- `sitemap.xml` (absent).
- `404.html` custom error page (absent; GitHub Pages will serve its generic 404).
- `<link rel="canonical">` on any page.
- Open Graph and Twitter Card metadata; no sharable preview image.
- Any structured data (no JSON-LD anywhere).
- `theme-color`, web app manifest (optional).
- `llms.txt` and any explicit AI-crawler policy.
- An About / authorship page and machine-readable publisher identity.
- Search Console / Bing Webmaster verification and a sitemap submission.

---

## 3. Gap analysis and recommendations

### A. Indexability and crawl foundations (P0)

1. **`robots.txt`** at the site root, generated by `build.py` (or added to
   `STATIC_FILES`). Allow everything, declare the sitemap, and state an explicit
   AI-bot policy (see GEO section for the bot list and rationale).
2. **`sitemap.xml`** generated from the prayer list and any standalone pages,
   with `<lastmod>`. `build.py` already holds every URL, so this is a short loop.
   Start with the build date as `lastmod`; later, track per-prayer modification
   (a `lastmod` column or git history) for true freshness signalling.
3. **Canonical tags**: add `<link rel="canonical" href="{absolute-url}">` to
   every page from a single `BASE_URL = "https://latinprayers.org"` constant.
   This protects against duplicate-URL dilution (apex vs `www`, trailing slash,
   stray query strings) and is the URL an LLM will cite.
4. **Host canonicalization**: decide the apex (`latinprayers.org`) is canonical
   and ensure `www.latinprayers.org` 301-redirects to it (a Cloudflare redirect
   rule, or GitHub Pages' built-in behaviour). Document the decision.
5. **Custom `404.html`**: GitHub Pages serves a top-level `404.html` for unknown
   paths. A branded 404 that links back to the index keeps users (and crawlers)
   on the site and looks professional.

### B. Title and description strategy (P1)

The real demand is queries like "pater noster in latin", "hail mary latin and
english", "salve regina translation". Templated titles should capture them
without overflowing (~60 characters including the brand suffix is the practical
SERP limit).

- **Prayer title template** (choose by length): prefer
  `{title} ({subtitle}) in Latin & English · latinprayers.org`; when that
  exceeds ~60 chars, drop the qualifier to `{title}, {subtitle} · latinprayers.org`.
  Consider giving `build.py` a dedicated `meta_title` it can shorten, rather than
  reusing the on-page heading.
- **Meta description template**: aim for 150 to 160 characters, lead with the
  English name and the Latin/English hook, then the one-line context. Example
  pattern: `The {subtitle} ({title}) in Latin with a faithful traditional English
  translation. {first context sentence}`.
- Keep the existing house rules (Douay register, no em-dashes, en-dashes only in
  numeric/scripture ranges) in all generated metadata.

### C. Structured data / JSON-LD (P0 for site-wide, P1 for per-prayer)

This is the highest-value addition after the crawl foundations. JSON-LD is plain
text injected at build time, fully doctrine-compatible, and is read by Google
(rich results, knowledge graph) and by LLM extractors.

- **Site-wide, in `base.html`**: a `WebSite` node (name, url, inLanguage) and an
  `Organization`/publisher node (name, logo = `sacred-heart.png`). Add a
  `potentialAction` SearchAction only if on-site search is later built.
- **Per prayer page**: a `CreativeWork` describing the prayer
  (`name` = Latin title, `alternateName` = English, `inLanguage` = `["la","en"]`,
  `about`, `isPartOf` the WebSite, `publisher`, `citation` = the source URL,
  `url`, `dateModified`), plus a `BreadcrumbList` (Prayers > Category > Prayer).
- There is no schema.org "Prayer" type; `CreativeWork` is the correct generic
  fit. The "About this prayer" prose can additionally be modelled as an `Article`
  or as the CreativeWork's `description`. Do not overreach with inaccurate types.
- Concrete snippets are in the Appendix.

### D. Content and on-page (P1/P2)

- **Category anchors and landing pages**: give each homepage category section an
  `id` (slug of the category) so it can be linked and used in breadcrumbs. Then
  consider dedicated category pages (e.g. `/prayers/marian/` or
  `/categories/<slug>/`) that capture category-level queries ("Marian prayers in
  Latin"), deepen internal linking, and give the sitemap more entry points.
- **Related-prayer links**: at the foot of each prayer, link 3 to 5 related
  prayers (same category, or hand-curated). This spreads link equity, increases
  crawl depth, and raises dwell time. The context prose can also link inline to
  other prayers it names (e.g. the Angelus referencing the Regina Caeli).
- **FAQ blocks (optional, high GEO value)**: a short, honest Q&A per prayer
  ("What is the Pater Noster?", "How is the Our Father prayed in Latin?") marked
  up as `FAQPage`. This is strong bait for featured snippets and for AI answers,
  which love question-shaped, directly-quotable content. Treat as P2 content work.
- **Freshness**: surface a "recently added" note or `dateModified`, and keep the
  sitemap `lastmod` honest. Freshness is a minor but real signal.
- **Homepage scale**: one page listing all prayers is a fine hub today. As the
  catalogue grows past a few dozen more, category pages (above) become the better
  structure than an ever-longer index.

### E. E-E-A-T and trust (P1)

Traditional Catholic devotional content sits adjacent to "Your Money or Your
Life" territory in how search engines weigh trust. The site already does the
hard part (authentic texts, cited sources). It should now make authority legible:

- **Publish an About page** (mission, the editorial doctrine in reader-facing
  form, how texts are sourced and vetted, who maintains the site, how to make
  corrections). The Manifesto is intentionally hidden and is a different artifact;
  About is a calmer, evergreen trust page. Register it via `STANDALONE_PAGES`.
- **Machine-readable publisher identity** via the `Organization` JSON-LD above,
  plus a stable logo.
- **Keep and strengthen source citations** (already present). Consider citing
  the specific authoritative reference per text rather than a single landing page
  where practical.
- **A contact path** (even just an email or a GitHub link) supports the
  "trustworthiness" leg of E-E-A-T.

### F. Core Web Vitals and performance (P2)

The site is already light, so these are refinements, not rescues:

- **Dimension the hero image**: add `width`/`height` (or an `aspect-ratio` CSS
  rule) to `christ.webp` on the homepage to eliminate CLS.
- **Prioritise the LCP image**: `fetchpriority="high"` on the homepage hero, and
  consider `<link rel="preload" as="image">`. Add `loading="lazy"` to any future
  below-the-fold imagery.
- **Reconsider `background-attachment: fixed`** on the body background on mobile;
  it can cause scroll jank and repaint cost on some devices. Test on a phone.
- **Responsive images**: a `srcset` for the hero would trim bytes on small
  screens.
- **Optional CSS minify at build**: a stdlib-only whitespace/comment strip in
  `build.py` would shave the single stylesheet. Low priority given its size.
- These all keep "JS disabled still works" intact.

### G. Semantics and accessibility (mostly done)

Already strong (skip link, `lang`, `alt`, heading order). Two small wins:
expose a true breadcrumb (paired with `BreadcrumbList`), and ensure the prayer
English name is reachable as a heading or strongly marked element so the primary
English query term is not buried in a paragraph.

---

## 4. Generative Engine Optimization (LLM / AI search)

AI answer engines (Google AI Overviews, ChatGPT Search, Perplexity, Claude with
web access, Bing Copilot) increasingly mediate discovery. Optimizing for them
("GEO") overlaps with classic SEO but adds emphases:

1. **Be crawlable by the AI bots, on purpose.** This is an apostolic site whose
   goal is to be found and cited, so the recommendation is to **allow** the major
   AI crawlers explicitly in `robots.txt`: `GPTBot` and `OAI-SearchBot` (OpenAI),
   `ClaudeBot` and `anthropic-ai` (Anthropic), `PerplexityBot`, `Google-Extended`
   (Gemini grounding/training), `CCBot` (Common Crawl, which feeds many models),
   and the standard `Bingbot` (which also powers Copilot). This is a deliberate
   editorial choice to maximise reach; it is reversible. Document it so it is not
   silently changed.
2. **`/llms.txt`** (emerging convention, llmstxt.org): a short Markdown file at
   the site root that gives models a clean, curated map of the site: a one-line
   description, then a list of the prayers grouped by category with their URLs
   and a one-line gloss each. Trivial to generate from the same data `build.py`
   already loads, and very on-brand (a plain, legible index).
3. **Lead each page with a definitional sentence.** Models extract and quote
   crisp, self-contained statements. The "About this prayer" prose already tends
   to open this way ("The Pater Noster is the prayer our Lord ... taught"); make
   that a consistent pattern so the first sentence is a quotable definition.
4. **Question-shaped content (FAQ).** Same as the on-page FAQ recommendation;
   AI answers are disproportionately drawn from clear Q&A and list structures.
5. **Structured data helps models too**, not just Google. The `CreativeWork` and
   `BreadcrumbList` JSON-LD give an LLM unambiguous entities (Latin name, English
   name, languages, source) to attach facts to.
6. **Consistency and citability.** Stable URLs, no contradictory facts across
   pages, explicit sourcing, and visible authorship all raise the odds a model
   cites latinprayers.org by name and links to it. The existing translation-source
   line is already a citability asset.
7. **Plain-text reachability.** The pages are server-rendered HTML with no JS
   dependency, which means every bot sees the full content without executing
   scripts. This is a real advantage over JS-heavy competitors; preserve it.

---

## 5. Measurement and tooling

You cannot improve rank without seeing query and crawl data. The privacy-friendly,
no-JavaScript options fit the doctrine cleanly:

- **Google Search Console** (essential): verify via a DNS TXT record at Cloudflare
  (no file, no script) or a static HTML verification file. Gives real query,
  impression, click, position, and indexing/coverage data, and lets you submit
  `sitemap.xml`. No effect on page weight.
- **Bing Webmaster Tools** (recommended): Bing's index also informs ChatGPT
  Search and Copilot, so this has GEO value beyond Bing itself. Same DNS or file
  verification model.
- **Analytics (the doctrine tension)**: classic web analytics (Google Analytics,
  Plausible, Cloudflare Web Analytics) all inject a client script, which conflicts
  with "no runtime dependencies / progressive enhancement only." Options, owner's
  call: (a) rely on Search Console + Cloudflare's server-side request analytics
  (zero script) for most needs; (b) accept one small privacy-respecting script as
  a deliberate, documented exception; (c) parse server/CDN logs. Recommendation:
  start with (a); it covers search performance without touching the page.

---

## 6. Off-page and authority (context, not in-repo work)

Ranking "as high as possible" in a niche with strong incumbents (EWTN, Wikipedia,
fisheaters, prayinglatin, ourcatholicprayers) ultimately needs external signals
that cannot be coded into the repo:

- **Backlinks** from traditional Catholic communities, parish and apostolate
  sites, blogs, and directories. The unique bilingual + context format is
  link-worthy; it needs outreach.
- **Citations and shares.** Open Graph cards (above) make shared links look
  credible on social platforms and in chats, indirectly helping acquisition.
- **Wikipedia and reference mentions** where genuinely appropriate and allowed.
- These are go-to-market actions for the maintainer, listed for completeness.

---

## 7. Prioritized roadmap

Impact and effort are rough. "Where" points at the file that would change when
implementation begins (not now).

| # | Item | Priority | Impact | Effort | Where |
|---|---|---|---|---|---|
| 1 | `robots.txt` (with AI-bot policy) | P0 | High | XS | `build.py` / `STATIC_FILES` |
| 2 | `sitemap.xml` with `lastmod` | P0 | High | S | `build.py` |
| 3 | Canonical tag from `BASE_URL` | P0 | High | S | `base.html`, `build.py` |
| 4 | `www` to apex 301 + documented canonical host | P0 | Med | XS | Cloudflare / docs |
| 5 | Custom `404.html` | P0 | Med | S | `templates/`, `build.py` |
| 6 | `WebSite` + `Organization` JSON-LD | P0 | High | S | `base.html`, `build.py` |
| 7 | Per-prayer `CreativeWork` + `BreadcrumbList` JSON-LD | P1 | High | M | `build.py`, `prayer.html` |
| 8 | Open Graph + Twitter cards + default share image | P1 | Med | M | `base.html`, `build.py`, `assets/img` |
| 9 | Title/description templates tuned for "in Latin/English" | P1 | Med | S | `build.py` |
| 10 | About page (E-E-A-T) | P1 | Med | M | `templates/about.html`, `STANDALONE_PAGES` |
| 11 | `/llms.txt` | P1 | Med | S | `build.py` |
| 12 | Search Console + Bing WMT verification + sitemap submit | P1 | High | S | DNS / static file |
| 13 | Category anchors (`id` on sections) | P1 | Med | S | `build.py` (index) |
| 14 | Related-prayer links + inline context links | P2 | Med | M | `build.py`, `prayer.html` |
| 15 | Category landing pages | P2 | Med | M | `build.py`, new template |
| 16 | FAQ blocks + `FAQPage` JSON-LD | P2 | Med | L | `data/`, `build.py` |
| 17 | Hero image dimensions + LCP priority + lazy-load | P2 | Low/Med | S | `index.html`, `prayer.html` |
| 18 | Reconsider `background-attachment: fixed` on mobile | P2 | Low | XS | `assets/css/style.css` |

A natural first implementation slice (one focused PR) is items 1, 2, 3, 5, 6:
all build-time, all foundational, no new content or images required.

---

## 8. Implementation notes and doctrine compatibility

- **Everything above is build-time and static.** `robots.txt`, `sitemap.xml`,
  `404.html`, `llms.txt`, canonical/OG tags, and JSON-LD are all plain text
  emitted by `build.py` through `templates/`, using only the standard library.
  No framework, no runtime dependency, no content fetched at runtime.
- **Single source of truth for URLs**: introduce one `BASE_URL` constant in
  `build.py` and derive canonical, sitemap, OG `og:url`, JSON-LD `url`, and
  `llms.txt` links from it, so the absolute-URL logic lives in exactly one place.
- **Generate, never hand-maintain**: the sitemap and `llms.txt` must be produced
  from the same `load_prayers()` data so they cannot drift from the pages.
- **Progressive enhancement preserved**: none of this needs JavaScript. If
  on-site search is added later for the `WebSite` SearchAction, it must remain an
  optional client-side enhancement over the already-complete static pages.
- **House style**: all generated metadata and any new prose follow the Douay
  register and the no-em-dash rule.
- **The analytics exception is the only doctrine conflict** and is left as an
  explicit owner's decision (Section 5).
- **Validation hooks worth adding when implementing**: extend `build.py --check`
  to assert every page has a canonical and a non-empty title/description, that
  the sitemap URL count equals the page count, and that emitted JSON-LD parses.

---

## Appendix: concrete snippets (for the implementation phase, not yet applied)

### A1. `robots.txt`

```
User-agent: *
Allow: /

# AI / answer-engine crawlers (explicitly allowed to maximise reach)
User-agent: GPTBot
Allow: /
User-agent: OAI-SearchBot
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Google-Extended
Allow: /
User-agent: CCBot
Allow: /

Sitemap: https://latinprayers.org/sitemap.xml
```

### A2. `sitemap.xml` (shape; generated for every URL)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://latinprayers.org/</loc><lastmod>2026-06-19</lastmod></url>
  <url><loc>https://latinprayers.org/prayers/pater-noster/</loc><lastmod>2026-06-19</lastmod></url>
  <!-- ... one <url> per prayer and standalone page ... -->
</urlset>
```

### A3. Head additions in `base.html` (new tokens filled by `build.py`)

```html
<link rel="canonical" href="{{canonical_url}}">
<meta property="og:type" content="{{og_type}}">          <!-- "website" or "article" -->
<meta property="og:site_name" content="latinprayers.org">
<meta property="og:locale" content="en_US">
<meta property="og:title" content="{{og_title}}">
<meta property="og:description" content="{{page_description}}">
<meta property="og:url" content="{{canonical_url}}">
<meta property="og:image" content="https://latinprayers.org/assets/img/og-default.png">
<meta name="twitter:card" content="summary_large_image">
```

### A4. Site-wide JSON-LD (homepage / base)

```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "latinprayers.org",
  "url": "https://latinprayers.org/",
  "inLanguage": "en",
  "publisher": {
    "@type": "Organization",
    "name": "latinprayers.org",
    "logo": {
      "@type": "ImageObject",
      "url": "https://latinprayers.org/assets/img/sacred-heart.png"
    }
  }
}
```

### A5. Per-prayer JSON-LD (`CreativeWork` + `BreadcrumbList`)

```json
{
  "@context": "https://schema.org",
  "@type": "CreativeWork",
  "name": "Pater Noster",
  "alternateName": "The Lord's Prayer",
  "inLanguage": ["la", "en"],
  "headline": "Pater Noster (The Lord's Prayer) in Latin and English",
  "about": "The Lord's Prayer",
  "url": "https://latinprayers.org/prayers/pater-noster/",
  "isPartOf": { "@type": "WebSite", "name": "latinprayers.org", "url": "https://latinprayers.org/" },
  "publisher": { "@type": "Organization", "name": "latinprayers.org" },
  "citation": "https://fisheaters.com/prayers.html",
  "dateModified": "2026-06-19"
}
```

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Prayers", "item": "https://latinprayers.org/" },
    { "@type": "ListItem", "position": 2, "name": "Common Prayers", "item": "https://latinprayers.org/#common-prayers" },
    { "@type": "ListItem", "position": 3, "name": "Pater Noster", "item": "https://latinprayers.org/prayers/pater-noster/" }
  ]
}
```

### A6. `/llms.txt` (shape)

```
# latinprayers.org

> A reverent repository of traditional Catholic prayers in Latin set
> side by side with a faithful Douay-register English translation, with
> notes on each prayer's history, origin, and liturgical use.

## Common Prayers
- [Pater Noster — The Lord's Prayer](https://latinprayers.org/prayers/pater-noster/): the prayer our Lord taught his disciples.
- [Ave Maria — The Hail Mary](https://latinprayers.org/prayers/ave-maria/): the angelic salutation.
- ... (one line per prayer, generated from data/prayers.csv) ...
```

### A7. Suggested title and description templates

```
Title (prefer):  {title} ({subtitle}) in Latin & English · latinprayers.org
Title (fallback when >60 chars):  {title}, {subtitle} · latinprayers.org

Description (150-160 chars):
  The {subtitle} ({title}) in Latin with a faithful traditional English
  translation. {first sentence of context}
```
