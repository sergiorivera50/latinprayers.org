# The Mass page: development, validation, and ideas

Tracks the design, content, decisions, and (above all) the **validation** of
`/mass/`. Like the SEO and Rosary docs, this file is internal: it is not
published (the build only emits `templates/`, `data/`, `assets/`).

## Source of truth and how we treat it

The page's content derives from [`docs/tridentine-mass.md`](tridentine-mass.md),
the output of a Claude research process describing the order of the 1962
Tridentine Mass. **That document is the working source of truth, but its claims
are not yet validated.** The maintainer is the doctrinal authority and is not a
priest; the research has not been checked against a physical 1962 altar Missal or
the standard ceremonial manuals.

Therefore the rule for this page is: **everything is provisional until verified,
point by point, and the verification is recorded here.** Build the depiction
incrementally; do not pour in unverified rubrical detail faster than it can be
checked. (The research itself flags, in its Caveats, several points that "for
publication-grade certainty the editor should verify against a physical 1962
altar Missal and Fortescue, O'Connell, and Reid.")

The research recommends authoritative anchors to validate against:
- the 1962 *Ritus servandus in celebratione Missae* (printed in the Missal),
- the General Rubrics of the 1962 Missal (nn. 269–530),
- **Fortescue, O'Connell, and Reid, *The Ceremonies of the Roman Rite Described*** (15th ed., 2009), the standard ceremonial manual,
- supplemented by FSSP / ICKSP / Una Voce / Latin Mass Society practical guides.

## What is implemented (MVP)

A first, deliberately high-level page that mirrors the Rosary page's architecture:

- **`data/mass.csv`** — one row per step of the Ordo Missae (37 steps), columns
  `division, part, order, name_la, name_en, summary`. So the order of service is
  as editable as the prayers and mysteries, and detail can be added row by row.
- **`build.py`**: `load_mass()`, `build_mass_page()` (groups the steps by
  *division* then *part*, renders the static outline), page-specific `Article`
  JSON-LD, the `/mass/` URL, a sitemap entry, and `build.py --check` coverage.
- **`templates/mass.html`**: centred header, hero image (reusing
  `assets/img/tridentine-mass.jpeg`), intro prose (what the Mass is; the 1962
  Missal and *Summorum Pontificum*; the two divisions), a static "Three Forms"
  explainer (Low / Cantata / Solemn), the `{{order_of_mass}}` slot, and a humble
  "A Note on This Page" closing panel naming the sources still to be checked.
- **`templates/base.html`**: the "The Mass" nav item, formerly a disabled WIP
  span, is now an active link to `/mass/`.
- Styles added to `assets/css/style.css` (`.mass-*`, `.ordo-*`), reusing the
  Rosary page's tokens and visual language.
- **Congregational posture layer** (Round 2): a `posture` column in
  `data/mass.csv` (the customary Low Mass posture per step), rendered as a small
  colour-keyed tag (stand = gold, sit = muted, kneel = crimson) in each step's
  right column, with an italic note that postures are customary and vary.
- **Position + silent layer** (Round 3): `position` (the celebrant's principal
  position) and `voice` columns, rendered as a small meta line under each step's
  name, e.g. "EPISTLE SIDE" or "CENTRE · *said silently*".
- **Ordinary vs. Proper** (Round 4): a `proper` column flags the eight steps whose
  text changes with the calendar, shown as a gold "Proper of the day" chip in the
  meta line; the order's lead defines the distinction.
- **Asperges preliminary rite** (Round 5): a section in `templates/mass.html`
  before the order, with the two antiphons (Asperges me / Vidi aquam) in Latin and
  English (reusing the `.rosary-collect` card) and a description of the rite.
- **Form selector** (Round 6): the first of the three axes made interactive. A
  Low / Sung / Solemn segmented control (`main.js` `initMassForm`) filters per-step
  form notes (`note_sung` shows at Sung & Solemn; `note_solemn` only at Solemn)
  and hides whatever does not occur in the chosen form (`forms` column). It is
  **progressive enhancement**: the control is `hidden` without JS, and every
  form's notes stay visible and labelled. The control is `position: sticky`
  within `.ordo`, so the pill rides along through the whole order (making it clear
  the choice changes what you see) and releases at the end of the order. Only the
  pill floats (no caption, no full-width bar); clicks pass through the rest. A
  handwritten "choose the form" hint with an organic (inline-SVG) arrow points at
  the pill; it is decorative (`aria-hidden`), shown only with JS, and **static**
  (a normal-flow sibling, so it stays at the start position and scrolls away
  rather than riding along). The script face is a system cursive stack (no CDN).
- **Form-aware posture** (Round 7): a `posture_high` column (set only where it
  differs from Low) so the posture tag switches with the selector. At sung/Solemn
  the people stand (not kneel) through the foot prayers, Introit, and Kyrie, stand
  to be incensed, and stand for the Preface. Low is the no-JS default.

### Scope of the MVP (what it intentionally does NOT yet do)

The page currently shows **only the invariant skeleton** (the Ordinary), at the
level of named steps with a one or two sentence summary each. Deliberately
deferred (see the research's "Recommendations"):

- **Two of the three axes as interactive toggles** — **Day & Season** (Gloria?
  Credo? inter-lesson chant? dismissal? colour?) and the **Requiem** mode are
  still folded into per-step parentheticals, not modelled as state. (The **Form**
  axis is now interactive, Round 6.)
- **The Proper texts themselves** (Introit, Collect, Epistle, Gradual, Gospel,
  Offertory, Secret, Communion, Postcommunion). As of Round 4 the page now *marks*
  which steps are Proper, but it still does not *print* their texts (correctly, as
  they change every day). A future round could pull a given day's Propers from the
  Missal/Ordo into a labelled slot; per the research, never hard-code them.
- **The Requiem as a master mode** (black; no Judica/Gloria/Credo/Pax/blessing;
  Dies Irae; Absolution at the catafalque; Requiescant in pace).
- **The rest of the per-step ceremonial metadata**: actor (priest / deacon /
  subdeacon / servers) and mode (spoken / sung), and a fuller voice model than the
  single silent flag. (Posture is done in Round 2; principal position and the
  silent flag in Round 3.)

## Validation log (point by point)

Status legend: ☐ unverified · ◐ partially checked · ☑ cross-checked against
sources (pending maintainer sign-off) · ✺ correction applied.

### Round 1 — verified 2026-06-28 (cross-checked against the sources below)

The first pass validated the page's spine (the divisions, the order, the step
names) and the branch notes. **One factual correction was made; everything else
on the page checked out.** Sources used this round: Wikipedia *Tridentine Mass*,
*Missa cantata*, and *Ite, missa est*; the Council of Trent Session XXII (the
subtitle phrase); and traditional-rubric references surfaced in search (1962
Ordo, MusicaSacra forum, Fr. Z, CCWatershed, Restore the 54). These are
secondary/explanatory, not the Latin typical edition; the maintainer remains the
final authority and a physical 1962 altar Missal + Fortescue is the gold standard.

- ☑ **The two divisions and their boundaries** — Mass of the Catechumens (after
  the foot prayers, Introit through the Creed) and Mass of the Faithful (begins at
  the Offertory, through the blessing and Last Gospel). Confirmed (Wikipedia,
  *Tridentine Mass*).
- ☑ **The order of the 37 steps** — the sequence matches the standard walkthrough
  (foot prayers, Introit, Kyrie, Gloria, Collect, Epistle, Gradual, Gospel, Credo;
  Offertory, Lavabo, Secret, Preface, Sanctus, Canon, Consecration, Pater Noster,
  Agnus Dei, Communion, Postcommunion, dismissal, blessing, Last Gospel).
- ☑ **Page Latin subtitle** "Sacrosanctum Missae Sacrificium" — this is the
  Council of Trent's own phrase (Session XXII, *De sacrosancto Missae sacrificio*),
  = "the most holy Sacrifice of the Mass." Grammatically and historically sound.
  Final wording remains the maintainer's call.
- ☑ **Step names / Latin incipits** — all standard and correct: *Judica me*
  (Ps. 42), *Aufer a nobis* (the ascent), *Munda cor meum*, *Suscipe sancte
  Pater* / *Suscipe sancta Trinitas*, *Orate fratres*, *Canon Missae*, *Unde et
  memores* (anamnesis), *Per ipsum* (doxology / minor elevation), *Pax Domini*,
  *Ultimum Evangelium*.
- ☑ **Gloria branch** (step 7) — said on Sundays (except Advent / Septuagesima /
  Lent / Passiontide), on feasts III class and higher, and on white-colour ferias;
  omitted in penitential seasons and at Requiems. The page's high-level summary is
  accurate.
- ☑ **Credo branch** (step 14) — said on Sundays and the greater feasts (the altar
  Missal prints "Credo" when it applies). Accurate.
- ☑ **Inter-lesson chants and the five Sequences** (step 10) — Gradual + Alleluia
  by default, Tract in penitential seasons, double Alleluia in Paschaltide; the
  five Sequences are exactly *Victimae Paschali* (Easter), *Veni Sancte Spiritus*
  (Pentecost), *Lauda Sion* (Corpus Christi), *Dies Irae* (Requiems), and *Stabat
  Mater* (Our Lady of Sorrows, added 1727). Confirmed.
- ✺ **CORRECTION — the dismissal** (step 34). The page originally said Benedicamus
  Domino is "sung on certain days." In the **1962** Missal, Benedicamus Domino is
  used only when **another liturgical action follows** (e.g. the Holy Thursday and
  Corpus Christi processions); otherwise Ite missa est is sung, and Requiescant in
  pace at Requiems. The old "Gloria omitted → Benedicamus" rule is **pre-1962**;
  the research doc's master-flow step 34 repeats that older rule (its Axis 2 entry
  hedges it). **Fixed in `data/mass.csv`** to the 1962 rule. (Wikipedia,
  *Tridentine Mass* / *Ite, missa est*.)
- ☑ **1962-specific deltas** (all confirmed):
  - The **second / pre-Communion Confiteor** was suppressed in 1962 (*Rubricae
    generales* §503: when Communion is given within Mass, the confession and
    absolution are omitted; only *Ecce Agnus Dei* + triple *Domine non sum dignus*
    remain). It survives in the 1962 Pontificale and is "tolerated where
    established practice" (FSSP Ordo); some communities retain it. The page already
    omits it (correct for 1962). Surface the "sometimes retained" nuance only when
    the ceremonial layer is added.
  - **Incense permitted at every Missa Cantata** — 1960 Code of Rubrics no. 426,
    verbatim: "The incensations that are obligatory in Solemn Mass are permitted in
    every Missa Cantata" (not at Low Mass). Matches the Three Forms card.
  - **Psalm 42 (Judica me) omitted** in Passiontide (Masses of the season) and at
    Requiems — confirmed verbatim (step 2 already says this).
  - **Leonine Prayers after Low Mass only** — confirmed (suppressed 1965, retained
    today under *Summorum Pontificum*); step 37 is correct.

### Round 2 — congregational posture, added 2026-06-28

Added the customary **Low Mass** posture to each step (`posture` column).

- **Why Low Mass, and why "customary":** every source agrees lay postures were
  **never comprehensively codified** by the 1962 rubrics (the rubrics govern the
  clergy). The page says so plainly and tells the reader, when in doubt, to follow
  the local congregation. Low Mass is the common pew case and suits the "How to
  follow" framing; sung/Solemn Masses follow the sacred ministers and differ.
- **Source aligned to:** the widely-circulated "Understanding When to Kneel, Sit
  and Stand at a Traditional Latin Mass" chart (Richard Friend; mycatholicsource
  flier), cross-checked with the research doc's posture summary. The fixed points
  all agree: kneel at the foot, stand for the Gloria/Collect, sit for the
  Epistle/Gradual/sermon, stand for the Gospel, stand for the Credo (genuflect at
  *Et incarnatus*), sit through the Offertory, kneel from the Sanctus through
  Communion, stand for the Postcommunion, kneel for the blessing, stand for the
  Last Gospel (genuflect at *Et Verbum caro factum est*), kneel for the Leonine
  Prayers.
- ◐ **Known soft points** (genuine variation, carried by the "varies" note rather
  than asserted): the **Preface** (set to *sit* here, following the "sit until the
  Sanctus bell" custom; some kneel, some stand for the dialogue); the **Pater
  Noster / Communion rite** (set to *kneel*, the common Low Mass practice; at High
  Mass the people stand for the Pater Noster); and the **dismissal** (set to
  *stand*, then kneel for the blessing; some charts kneel from the Ite missa est).
- ☐ For a later "follow the ministers" view, the **High/Sung Mass** posture column
  differs (e.g. kneel — not genuflect — at *Et incarnatus* when the choir sings
  it; stand for the Pater Noster) and can be added as a second posture set.

### Round 3 — position + silent flag, added 2026-06-28

Added the celebrant's **principal position** (`position`) and a **"said silently"**
flag on the secreto parts (`voice`). Both are rubrical (the *Ritus servandus*),
so this round is higher-confidence than the postures.

- ☑ **Altar geography** — cross-checked: Introit and Collect at the **Epistle
  side**; Kyrie, Gloria, and the whole Offertory/Canon at the **centre**; the
  Missal crosses to the **Gospel side** for the Gospel; Lavabo, the Communion
  antiphon/Postcommunion, and the Ablutions at the **Epistle side**; the Last
  Gospel at the **Gospel side**. (LMS Bloomington walkthrough; LiturgyGuy.)
- ☑ **Silent (secreto) parts** — cross-checked: the Offertory prayers, the Canon
  "except the Preface and the final doxology," the Secret (said inaudibly, ending
  *Per omnia* aloud), and the prayers between the Pater Noster and Postcommunion
  apart from the Agnus Dei. Flagged steps: the ascent (4), Munda cor meum (11),
  the Offering (16), Lavabo (18), Suscipe sancta Trinitas (19), the Secret (20),
  the Canon (23), Consecration (24), Anamnesis (25), the doxology (26), and the
  priest's Communion (30). (Wikipedia; MyCatholicSource.)
- ◐ **"Principal" position is a simplification.** Several steps involve movement
  within them (the Collect: kiss at centre, turn for *Dominus vobiscum*, then read
  at the Missal on the Epistle side; the Offertory and Conclusion likewise). The
  page shows the dominant position; a later round could show the movement.
- ◐ **The silent flag is deliberately conservative.** It marks only the
  predominantly-silent steps; genuinely mixed steps (the Fraction with its aloud
  *Pax Domini*; the minor elevation with its aloud *Per omnia*) are left unflagged,
  with the aloud conclusions already noted in those steps' summaries. A fuller
  silent / low-voice / aloud / sung model is left for a later round.

### Round 4 — Ordinary vs. Proper, added 2026-06-28

Marked the steps whose **text changes with the calendar** (`proper` column → a
"Proper of the day" chip), implementing the research's recommendation #4.

- ☑ **The Proper set** — cross-checked against the standard Propers of the Mass
  (*Proprium Missae*): Introit, Collect, Epistle, Gradual/Tract (+Sequence),
  Gospel, Offertory, Secret, Communion, Postcommunion. Flagged steps 5, 8, 9, 10,
  12, 15, 20 (the Secret), and 33 (which covers both the Communion antiphon and
  the Postcommunion). (New Advent *Missal*; Grokipedia *Proper (liturgy)*.)
- ◐ **The Preface (step 21) is left UNflagged on purpose.** Proper prefaces do vary
  by season/feast, and the research's rec #4 lists the Preface among the proper
  slots; but the conventional *Proprium Missae* list excludes it (it belongs to the
  Ordo Missae framework, with a Common Preface default). The page keeps the
  Preface as Ordinary and notes its seasonal variation in the step's summary
  instead. Revisit if the maintainer prefers it flagged.
- ☐ The chip marks *that* a step is Proper; it does not yet show the day's actual
  Proper text (see "The Proper texts themselves" under Scope).

### Round 5 — the Asperges, added 2026-06-28

Added the preliminary Sunday sprinkling as its own section before the order of
Mass (bracketing it with the Leonine Prayers at the end). It prints both
antiphons in Latin and English.

- ☑ **The two antiphons** — *Asperges me* (Ps. 50, throughout the year) and *Vidi
  aquam* (Ezech. 47, in Paschaltide). Latin set in the site's no-accent, spelled-
  out-"ae" house style; English in the Douay register ("Thou shalt sprinkle me…
  whiter than snow"; "I saw water… were saved… alleluia, alleluia"). Cross-checked
  against Wikipedia (*Asperges me*, *Vidi aquam*) and the Adoremus / New Liturgical
  Movement Asperges articles.
- ☑ **The rubric** — done before the principal Sunday Mass; celebrant in a cope of
  the day's colour; sprinkles altar, ministers, then people; structured like an
  Introit (antiphon, psalm verse, Gloria Patri omitted in Passiontide, antiphon
  repeated), then versicles and a collect; omitted on Palm Sunday (blessing of
  palms) and at Pontifical High Mass. Confirmed by the same sources.
- **Note (typography, site-wide, not a defect):** the Latin renders the
  classical V-for-U ("mvndabor", "tvvm", "qvi") because EB Garamond applies a
  Latin `locl` OpenType feature to `lang="la"` text. Every prayer page already
  does this (e.g. the Pater Noster), so the antiphons are consistent with the site.
  If plain u's are ever wanted site-wide, add `font-feature-settings: "locl" 0;`
  (or `font-variant-alternates: normal`) to the Latin text. Left as-is to match.

### Round 6 — the Form axis (interactive), added 2026-06-28

Made **Form** (Low / Sung / Solemn) an interactive selector. Choosing a form
reveals that form's per-step notes and hides whatever does not occur in it.

- **Model:** `note_sung` (shown at Sung *and* Solemn) carries the "if sung"
  changes (choir sings the chants, priest chants the Preface / Pater Noster /
  dismissal, he sits at the sedilia during a sung Gloria/Credo); `note_solemn`
  (Solemn only) carries the sacred ministers (subdeacon chants the Epistle, deacon
  chants the Gospel with lights and incense, the offering by the ministers, the
  incensation order, the Kiss of Peace). This mirrors reality: Solemn = Sung +
  deacon & subdeacon. The four form parentheticals were moved out of the base
  summaries into these notes.
- **Applicability:** `forms` restricts the Incensation (Sung & Solemn only) and
  the Leonine Prayers (Low only); the chosen form hides the others entirely. A
  step, part, or whole division is hidden (`group_forms` propagates the
  restriction up, so "After Mass" disappears as a whole at sung/Solemn rather than
  leaving an empty heading). Step numbers are a CSS counter, so a hidden step
  leaves no gap in the sequence.
- ☑ **The note content** rests on already-validated facts (Rounds 1–3): the
  subdeacon/deacon roles, incense permitted at every Cantata, the silent-while-
  sung sedilia behaviour, the Kiss of Peace at Solemn only. Sourced from the
  research doc and the earlier cross-checks.
- ◐ **Worth a closer look later:** the exact Pax order (celebrant → deacon →
  subdeacon → choir) and the precise incensation order are from the research doc,
  not yet checked against Fortescue; and "he sits at the sedilia" applies to a
  *sung* Gloria/Credo when the choir's setting is long (not invariably). These are
  phrased generally to stay honest.
- ☑ **Posture now switches by form** (done in Round 7).
- **Progressive enhancement check:** with JS off, the selector is `hidden` and all
  notes render with "Sung" / "Solemn" labels, so nothing is lost.

### Round 7 — form-aware posture, added 2026-06-28

Posture now switches with the Form selector (`posture_high`, set only where it
differs from Low; the tag renders both values and CSS shows the right one).

- ◐ **The High posture set** aligns with the research doc's High/Sung model and the
  mycatholicsource High column: at sung & Solemn Mass the people stand (rather than
  kneel) through the prayers at the foot, the Introit, and the Kyrie, stand to be
  incensed, and stand for the Preface; they kneel from the Sanctus through
  Communion as at Low Mass. Like all postures these are **customary and vary**.
- ◐ **Soft points** (flagged, not asserted): some communities kneel for the
  prayers at the foot even at High Mass; some stand for the sung Pater Noster
  (kept as kneel here, matching "kneel from the Sanctus through Communion"); and
  during a long sung Gloria/Credo the people sit when the priest sits (covered by
  the posture note rather than per step).
- **No-JS default** stays Low. The posture note was reworded to describe both
  Low and sung/Solemn custom rather than Low alone.

### Still open (next rounds)

- ☐ **Maintainer sign-off** on Round 1 (the doctrinal authority's confirmation,
  especially the subtitle choice and the dismissal wording).
- ☐ **Honest points of variation** to present as such once the ceremonial layer is
  added: posture for the sung Sanctus (stand-until-bell vs kneel-from-Sanctus);
  retention of the pre-Communion Confiteor by some communities; whether the
  celebrant is incensed after the Gospel at a Cantata; the deacon's Gospel
  orientation (1962 *Ritus servandus* "facing the people" vs Fortescue's "north").
- ☐ **The remaining ceremonial metadata** (actor, position, voice silent/aloud,
  spoken/sung) before it goes on the page — verify against the *Ritus servandus*
  and Fortescue, not search summaries.
- ☐ **The Requiem (Mass for the Dead) — deliberately deferred.** Per the
  maintainer (2026-06-28), it is intentionally *not* built yet, to avoid adding
  too much at once. It is now flagged as a known future addition in the page's "A
  Note on This Page" panel (black vestments, no Gloria/Creed, Dies Irae,
  Requiescant in pace, Absolution at the catafalque). When taken up, model it as a
  single master switch cascading the disable/enable set in the Branch-Factor Index,
  not as many independent toggles, and verify against the *Ritus servandus* and
  Fortescue.
- ☐ **The Propers text handling** — verify when built.

## Backlog / ideas (not commitments)

- **Extend the interactive axes** (JS progressive enhancement): the **Form** axis
  is done (Round 6); add the **Day & Season** selector (Gloria / Credo / chant /
  dismissal / colour) and the **Requiem** mode, re-rendering each step's variant.
  The static page stays the fallback. This is the research's central recommendation.
- **Per-step detail pages or expandable rows**: actor, position, voice, posture.
- **Requiem mode** as a single master switch cascading the disable/enable set.
- **Link the Mass and the prayers**: many step names (Pater Noster, Gloria,
  Confiteor, Agnus Dei, Credo) already exist as prayer pages; link them, and add
  a Mass CTA on those prayers (as the Rosary CTA does).
- **Sacred art** per part or division, replacing/illustrating the outline.
- **BreadcrumbList** JSON-LD and, eventually, richer `HowTo`-style structured data.
- **Liturgical colour** as a visual cue once the Day/Season axis is modelled.
