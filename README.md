# latinprayers.org

> *In the defense of Tradition, the Tridentine Mass, and Catholic living.*

A central, reverent repository of **prayers in Latin** — Pater Noster, Ave Maria,
Gloria Patri, and more — published to draw souls toward the traditional branch of
Catholicism: the Tridentine (Latin) Mass and traditional Catholic living.

It is a fully **static website**: plain HTML, CSS, and a touch of vanilla
JavaScript. No frameworks, no backend, no runtime dependencies. Prayer content
lives once as CSV data and is rendered into static HTML by a small Python build
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

The dev server also mounts the **Prayer Studio** at <http://127.0.0.1:8000/_studio/>,
and puts a link to it in the bottom-left corner of the prayer pages it serves.
`--no-studio` turns it off.

## Adding a prayer

1. Add one row to `data/prayers.csv` (see the columns in [CLAUDE.md](CLAUDE.md)).
   Opens as a normal spreadsheet in Excel/Google Sheets. Or use the local editor:
   `python3 serve.py --studio`, then <http://127.0.0.1:8000/_studio/>.
2. Preview with `python3 serve.py --watch`.
3. Commit `data/prayers.csv` and push — CI builds and publishes. **Never commit HTML.**

### Prayer Studio (local only)

`serve.py` mounts a plain admin UI for `data/prayers.csv` at `/_studio/`: a table of
every prayer with validation status, an editor with the Latin and English side by side
and line-aligned, and a field-by-field, word-by-word diff shown for confirmation before
anything is written. Saves are atomic, take a backup, and rebuild the site. The prayer
pages the dev server serves carry a bottom-left link into it, and on an individual
prayer that link opens that prayer's editor.

It is mounted only on a loopback bind (`--no-studio` turns it off), and is never copied
into `dist/` — `build.py` has no knowledge of it, and the corner badge is injected by
the dev server rather than built into the HTML. Details in [CLAUDE.md](CLAUDE.md).

## Project layout

| Path                  | Purpose                                              |
| --------------------- | ---------------------------------------------------- |
| `data/prayers.csv`    | Source of truth for prayer content (one row each)    |
| `templates/*.html`    | Page layout and templates                            |
| `assets/`             | Hand-authored CSS and JS                             |
| `build.py`            | Generates the site into `dist/`                      |
| `serve.py`            | Local dev server (build + serve, with `--watch`)     |
| `studio.py`, `studio/`| Local-only prayer editor at `/_studio/`; never published |
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
