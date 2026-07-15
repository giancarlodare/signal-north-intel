# Published Brief Format + Email Delivery: Design

Status: design-first proposal (2026-07-15), code not started. Awaiting operator
approval before building, per propose-then-approve.

## 0. Scope and what already exists

This designs the READER-FACING published brief (the artifact a vendor reads) and
its email delivery. It does NOT re-do selection or editing, which exist:

- `src/brief_generator.py` selects/clusters/ranks the week's timing-relevant
  signals and writes a `draft` brief (`briefs` + `brief_items`,
  migration 2026-07-13_briefs.sql).
- `/brief` (`web/app/brief`) is the operator editor: cut, reorder, add
  `title`/`intro`, `headline_override`, `editor_note`; Publish sets
  `status='published'` and freezes `published_at`.
- `docs/editorial-model-redesign.md` §7.4 specifies reader-facing date labels
  (deferred until exactly this format is built).

What is NOT built and this covers: the published render itself (the memo), the
standing exhibits, and Resend email delivery to the operator.

The standard is a McKinsey/BCG client memo: serious, editorially dense, a
committed point of view, every element answering "so what for a vendor." Clean
typographic hierarchy, generous whitespace, restrained palette, no newsletter
chrome, no stock photography.

## 1. Honesty rules that bind the format (inherited, non-negotiable)

1. No em dashes anywhere in generated or edited copy.
2. No fabricated dates. Date precision is honored (month-precision renders
   "Apr 2026", never a fabricated day), and every reader-facing date carries its
   TYPE label (§3).
3. Provenance on every claim: each item links to the publisher document that
   backs it; each exhibit carries its data basis (record count, date range,
   sources). No floating numbers.
4. The brief never pads to look substantial. A thin honest brief beats a fat
   stale one. Standing exhibits (corpus-based, §4) carry substance on a quiet
   news week so we never reach for filler items.
5. None beats a wrong chart: an exhibit that would mislead on thin data is left
   out, with the reason recorded, until the data supports it (§4).

## 2. Structure of the published brief

One column, top to bottom. Nothing below is optional-to-fill: a section with
nothing honest to say is omitted, not padded.

1. **Masthead.** "The Signal" (or the chosen name), the covered week
   (`week_start` to `week_start+6`), and a one-line dateline. No logo chrome.
2. **The Read.** One paragraph, the operator's voice (`briefs.intro`): the
   editorial judgment, what this week means for a vendor selling to government.
   A committed point of view, not a summary. This is the memo's lede.
3. **Lead item.** The single most imminent/actionable cluster (the top-ranked
   `imminent` brief_item). Renders:
   - headline (`headline_override` or the lead signal title),
   - the ACTION WINDOW, explicit, with its §3 type label
     (e.g. "Tender closes 24 Jul 2026", "Application deadline 31 Aug 2026"),
   - the vendor implication ("so what") from `editor_note`,
   - buyer/organization and amount when known,
   - a provenance link to the publisher document.
4. **Supporting items.** The remaining included brief_items, ranked as the
   editor left them. Same anatomy as the lead, tighter. If there are none, the
   section is omitted and a one-line honest note stands in its place
   ("A quiet week for new signals; the standing exhibits below carry the
   through-line.").
5. **Standing exhibits** (§4). Corpus aggregates, not the week's items. These
   are the analytical spine and the reason the brief is never thin-looking even
   when the news is thin.
6. **Provenance footer.** Method note: how items are selected, what the exhibit
   is built from, and the honest count of items reviewed but held below the
   materiality bar this week (`excluded_below_threshold`) so density is never
   overstated.

Anatomy of every item: headline / action-window-with-type-label / vendor "so
what" / buyer + amount when known / provenance link. Nothing shown that we
cannot source.

## 3. Reader-facing date labels (§7.4, implemented here)

Every reader-facing date carries its TYPE, derived from
`(doc_type, timing_path)` (brief_items store `timing_path`; the lead signal's
document carries `doc_type`). Baseline map from §7.4:

| doc_type                    | timing_path | label                |
|-----------------------------|-------------|----------------------|
| grant_program / grant_award | imminent    | Application deadline |
| award_notice                | recent      | Contract awarded     |
| tender_notice               | imminent    | Tender closes        |
| tender_notice               | recent      | Tender expected      |
| board_minutes               | recent      | Board decision       |

Any combination not listed renders the safe default label "Event date" rather
than a bare date. A shared `dateLabel(docType, timingPath)` helper is the single
source of truth, unit-tested against this table. Precision still applies:
month-precision dates render "Apr 2026".

## 4. Standing exhibits: proposed set and the honesty verdict

The weekly item count is small and always will be; charting two items is
padding. Exhibits are built from corpus AGGREGATES. Here is the proposed set and
a blunt verdict on which are honest at today's data density. The rule is "none
beats a wrong chart."

### 4.1 SHIP: Peel municipal contract awards by quarter (volume)
Count of `award_notice` documents by quarter of `published_on`, for the Peel
Region municipal source. We hold 2,758 Peel awards back to 2017, so this is
dense and real. It shows the rhythm and scale of a government buyer's award
activity, which is exactly the "how big and how often does this buyer actually
buy" question a vendor asks.

Honest caveats stated on the exhibit:
- It is award CLOSINGS by date, and the Peel history is a one-time backfill, so
  it is a standing picture of the buyer, not "this quarter's news" (that is the
  point of a standing exhibit).
- The most recent quarter is partial and is labeled as such (never drawn as a
  drop in activity).

### 4.2 HOLD: award volume by quarter ACROSS jurisdictions (comparison)
Tempting, but DISHONEST at current coverage. We have deep Peel municipal data
(2,758) and shallow federal award coverage. A side-by-side per-jurisdiction
chart would make federal look tiny next to Peel, which is an artifact of OUR
coverage, not of reality. We do not draw a cross-jurisdiction comparison until
federal/provincial award coverage is comparable. Ship the single-jurisdiction
Peel exhibit (§4.1) instead, honestly labeled as Peel.

### 4.3 HOLD: award VALUE by quarter
No honest value data for municipal awards: the bids&tenders awarded endpoint
exposes reference, title and closing date but NOT the award value (documented in
the Peel awarded design). Award value exists only for some federal contract
signals. A value-by-quarter chart would therefore show near-zero municipal value
and misrepresent a very active buyer. Left out until a value source lands (the
per-bid results-page enrichment noted in the awarded design, or council-minutes
award values which carry dollar figures).

### 4.4 HOLD (or tightly scope): demand-ladder distribution
"Where money is forming vs closing" is the right question, but the raw ladder
across the whole corpus is dominated by the 2,758-award historical backfill
(rung 5), so it would read as "almost everything is already awarded", which is a
backfill artifact, not the live pipeline. It is honest ONLY if scoped to avoid
that skew, and even then our formation rungs (chatter/intent/commitment) are
thin because we see closings better than early formation. Recommendation: HOLD
until the live pipeline has density. If wanted sooner, the only honest variant is
a clearly-labeled "current Peel pipeline snapshot" (open tenders in_market vs
awards in a trailing window), with an explicit note that early-formation rungs
are under-observed. Operator decision (§8).

### 4.5 HOLD: contract-expiry / recompete windows
The most vendor-valuable exhibit ("what is up for recompete and when"), but we do
not systematically capture contract TERM or expiry dates. The awarded endpoint
gives closing dates, not term; some council-minutes awards state a term in prose
("five-year period to 2028") but that is not extracted as structured data. Drawing
recompete windows now would be fabricating the very dates the exhibit is about.
Left out until a term/expiry extraction exists (a natural follow-on to the
council-award mining, which already sees term language).

### 4.6 Net verdict
One honest standing exhibit today: **§4.1, Peel municipal award volume by
quarter.** Three held with their reasons (value, cross-jurisdiction comparison,
recompete) and one scoped-or-held (demand ladder). This is deliberate: a single
honest exhibit is the whole ethos. As value, coverage, and term extraction land,
the held exhibits turn on one at a time.

### 4.7 How exhibits render (email-safe)
Email clients do not run JavaScript and many strip SVG and remote images. So
exhibits are drawn as HTML/CSS bar charts (table of labeled rows with a filled
bar cell whose width is a percentage), which render in every client and degrade
to a clean labeled table if CSS is stripped. No canvas, no JS, no external image
fetch. Each exhibit shows its data basis inline: record count, date range, and
source list, so the chart is never a floating number.

## 5. Render architecture

A single email-safe HTML render is the canonical published format, used by BOTH
the web published view and the email, so they can never drift.

- `renderBrief(brief, items, exhibits)` -> HTML string. Inline styles only (no
  external stylesheet), single column, `max-width: 600px`, a system font stack
  (no web fonts), a restrained palette (ink on paper, one accent), table-based
  layout for client compatibility. Phone-first: it is a single column that reads
  top to bottom on a 360px screen.
- Web: a published route (e.g. `/brief/[week_start]`) renders the same HTML for
  preview and for a shareable read. Auth stays as-is for now (pre-gate).
- Data: the brief and its included items (joined to each lead signal's document
  for `doc_type`, `url`, `published_on`, `date_precision`), plus the exhibit
  aggregate (one SQL group-by for §4.1). All read-only.

Rendering is pure (brief + items + exhibits in, HTML out), so it is unit-testable
without a database or a mail send, and the honesty checks (no em dash, every date
labeled, every item has a provenance href) are asserted in tests.

## 6. Email delivery (Resend)

- **Provider:** Resend, REST API, `RESEND_API_KEY` as a repo/web secret.
- **Recipient:** the operator only, giancarlo97dare@gmail.com, hardcoded. No
  list, no subscriber capture, no unsubscribe plumbing until after the gate.
  Sending to self pre-departure is the whole point.
- **Sender:** Resend's `onboarding@resend.dev` works for sending to the account
  owner's address WITHOUT domain verification, so we can ship immediately. A
  verified sending domain is a prerequisite only for real recipients later
  (post-gate), noted but not built now.
- **Trigger:** an explicit "Send to me" action on a PUBLISHED brief, separate
  from Publish. Publish freezes the content; Send is a deliberate second step so
  a brief is reviewed in its published form before it is mailed. The action
  renders the canonical HTML (§5) and posts it to Resend.
- **Idempotency:** a new `briefs.sent_at` column records the send; the action
  refuses to re-send a brief that already has `sent_at` unless explicitly
  confirmed, so a double-click or re-open cannot double-send.
- **Degradation:** inline styles, table layout, real text (not images) for all
  content, a plain-text alternative part generated from the same data, and a
  short preheader. Assume it is read on a phone in a client that strips CSS: it
  must still read as an ordered, labeled document.

## 7. Schema deltas (minimal, additive)

- `briefs.sent_at timestamptz` (nullable): set once when the brief is emailed, so
  Send is idempotent and the delivery is part of the record.
- Reuse existing columns for the memo, no new item columns: `headline_override`
  is the item headline, `editor_note` is the vendor "so what". If the "so what"
  deserves its own field later we add it then; reuse avoids churn now.
- No change to selection, clustering, or the ledger.

## 8. Build plan (once approved) and open questions

Build order: (1) `dateLabel` helper + tests (§3); (2) `renderBrief` pure render
with honesty-check tests (§5) and the §4.1 exhibit query; (3) web published route
using the render; (4) `sent_at` migration + Resend "Send to me" action (§6);
(5) a dry preview (render to a static HTML file / a "Preview" tab) before the
first real send.

Open questions for the operator:
1. **Demand-ladder exhibit (§4.4):** hold until the live pipeline has density, or
   ship the tightly-scoped "current Peel pipeline snapshot" now with the
   under-observation caveat? Recommendation: hold.
2. **Send trigger (§6):** explicit "Send to me" on a published brief
   (recommended), or auto-send on Publish?
3. **Sender (§6):** ship on `onboarding@resend.dev` now (works to your own
   address), or verify a sending domain first?
4. **The vendor "so what" copy:** operator-written per item (reuse
   `editor_note`), or should the generator propose a draft implication the editor
   refines? Recommendation: operator-written now; generator-proposed later.
5. **Masthead name:** confirm the brief's reader-facing title.
