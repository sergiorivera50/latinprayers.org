# latinprayers.org

> *In the defense of Tradition, the Tridentine Mass, and Catholic living.*

A central, reverent repository of **prayers in Latin** — Pater Noster, Ave Maria,
Gloria Patri, and more — published to draw souls toward the traditional branch of
Catholicism: the Tridentine (Latin) Mass and traditional Catholic living.

It is a fully **static website**: plain HTML, CSS, and a touch of vanilla
JavaScript. No frameworks, no backend, no runtime dependencies. Prayer content
lives once as JSON data and is rendered into static HTML by a small Python build
script.

## Quick start

```bash
# Build once and serve at http://localhost:8000 (Python 3, no dependencies)
python3 serve.py

# Iterate on content/styling — rebuilds automatically on save
python3 serve.py --watch

# Just build the published output into dist/
python3 build.py
```

## Adding a prayer

1. Add one row to `data/prayers.csv` (see the columns in [CLAUDE.md](CLAUDE.md)).
   Opens as a normal spreadsheet in Excel/Google Sheets.
2. Preview with `python3 serve.py --watch`.
3. Commit `data/prayers.csv` and push — CI builds and publishes. **Never commit HTML.**

## Project layout

| Path                  | Purpose                                              |
| --------------------- | ---------------------------------------------------- |
| `data/prayers.csv`    | Source of truth for prayer content (one row each)    |
| `templates/*.html`    | Page layout and templates                            |
| `assets/`             | Hand-authored CSS and JS                             |
| `build.py`            | Generates the site into `dist/`                      |
| `serve.py`            | Local dev server (build + serve, with `--watch`)     |
| `dist/`               | **Generated** output — gitignored, built by CI       |

## Contributing & development notes

See [CLAUDE.md](CLAUDE.md) for the editorial doctrine (fidelity to Tradition,
authentic texts) and the technical doctrine (static, no frameworks, build-time
generation only). It is the standing brief for development.

## Deployment

Pushing to `main` triggers a GitHub Actions workflow that runs `build.py` and
publishes the `dist/` artifact to GitHub Pages; `CNAME` binds the custom domain.
Rendered HTML is never committed.

> **One-time setup:** in repo *Settings → Pages*, set **Source = "GitHub Actions"**.
