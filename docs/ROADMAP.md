# Roadmap — queued follow-ups

Durable record of agreed next builds, so nothing lives as folklore. Each item
lands as its own reviewed PR when its phase stabilizes.

## Prediction and track-record ledger (strategy pivot, 2026-07-13)

**The core asset.** Signal North is a predictive intelligence engine whose
value is a provable, time-stamped track record of calling which companies win
government attention before the market sees it. The current propose-then-
approve loop evolves into propose, predict, approve, reconcile. Build order is
dependency order, A then B then C then D, with collector and coverage PRs
interleaved so collection never pauses:

- **Phase A:** demand-strength taxonomy on every signal (chatter, intent,
  commitment, in_market, awarded) plus a first-class `procurements` entity.
- **Phase B:** the immutable, public-provenance prediction ledger plus a
  weekly propose-only reconciliation job and a hit-rate and lead-time view.
- **Phase C:** decision-adjacent seller outputs and the two-sided export seam
  (seller built, investor designed but gated off).
- **Phase D:** incumbent vulnerability, timing windows, competitor positioning.

Design docs (approved build order, code not started): see
`docs/prediction-ledger-design.md` (Phases A and B schema and modules) and
`docs/legal-seam-investor.md` (securities, MNPI, and manipulation flags for
counsel; the investor line is Phase 2, pending legal review, nothing
investor-facing is built).

## Grants collectors — BUILT 2026-07-11 (programs); awards design-first

**Design note (operator, 2026-07-11):** grant awards are leading indicators of
downstream procurement 6–18 months out. They are often sub-threshold and
invisible to tender monitoring — treat as **first-class**, not an afterthought.

Built (RUNBOOK Step 8 has the apply order):
- `src/grants_ontario.py` — the province's open funding directory (daily) +
  one-time closed-archive baseline (`--baseline`). Deadlines are event dates;
  CFR guideline rubrics captured into the program record; TPON-gated
  guidelines recorded via `documents.guidelines_gated`, never skipped.
- `src/grants_pscanada.py` — PS Canada's ~30 contribution/grant programs with
  detail-page terms as bodies (weekly).

- `src/grants_federal_awards.py` — federal `grant_award` docs from the
  open.canada.ca proactive-disclosure datastore (design approved 2026-07-11,
  `docs/grants-federal-awards-design.md`; ps-sp / rcmp-grc / dnd-mdn /
  cbsa-asfc, window 2024-04-01+, 25/dept/run, weekly).

Remaining follow-ups:
- **csc-scc and jus** as additional awards departments — one-line reviewed
  config changes when wanted.
- **Transfer Payment Ontario listings + ministry grant pages + newsroom grant
  announcements** as additional Ontario feeders, if the directory proves to
  lag them.

## Ontario Newsroom JSON-API adapter (small PR)

news.ontario.ca is a JS SPA with no RSS/Atom feed (probe 2026-07-11 +
operator page-source check). The feed entry is PARKED in `src/rss_collector.py`.
The unpark path is a small adapter for their JSON backend (still the official
publisher source), run through the same keyword/scope filters and content_hash
dedupe as the RSS feeds.

## Brief generation (future) — event-date discipline (editorial constraint)

**Binding constraint from editorial review (2026-07-11):** when the brief
generator is built, its selection query MUST filter and sort on the **event
date** — the source document's `published_on`, surfaced through the signal's
document join — never on `created_at`/collection date. The two dates diverge
by design: collectors backfill history (Peel's board archive spans 2017–2026),
so collection-date ordering would let backfilled history masquerade as news.
A 2019 board decision collected yesterday is context, not a headline.

**Date precision is explicit in the data** (`documents.date_precision`,
'day'|'month'): Peel's {item}-{MM}-{YY} filename convention dates a document
to its meeting month only, stored as day=01 with precision 'month'.
**Renderers MUST show month-precision dates as "Apr 2026", never as a full
date** — the review page's eventDate() does; the brief generator must.

Corollaries for the implementer:
- Signals whose document has `published_on IS NULL` need an explicit policy
  (exclude from dated briefs, or a separate "date unknown" section) — never
  silently substitute the collection date.
- The review page already leads each card with the event date (`tag.event`),
  so the reviewer sees what the brief reader would see.

**Reader-facing date TYPE labels (operator, 2026-07-13) — DEFERRED to the
published brief format + Wave 3 subscriber portal, NOT the internal editor.**
Every date shown to a reader must carry its type as a label derived from
(timing_path + doc_type): "Application deadline" (imminent grant), "Contract
awarded" (award_notice), "Tender closes/expected" (tender_notice), "Board
decision" (board_minutes). A bare date is ambiguous (a subscriber could misread
a deadline as a past event). Full spec + baseline map in
docs/editorial-model-redesign.md section 7.4.

## Per-jurisdiction demand-arc backtest (calibration layer, Wave 2 / post-award-history)

**Banked 2026-07-13. Not now.** A calibration layer that learns each
jurisdiction's real demand rhythm from its own award history. Prerequisite:
sufficient AWARD history per jurisdiction, which starts flowing once the
municipal award collectors land (Peel via bids&tenders,
`docs/peel-tenders-design.md`).

Mechanism: walk each AWARDED procurement backward along the procurement spine to
its originating commitment/budget signal; measure the lag at each rung
transition (commitment -> in_market, in_market -> awarded); aggregate per
jurisdiction into a conversion RHYTHM (lag distribution) and conversion RATE
(which commitments became procurements vs fizzled).

Two payoffs: (1) ground prediction horizon defaults in each jurisdiction's
MEASURED history instead of the fixed per-rung guesses
(`src/predictions.py:default_horizon_months`, app `DEFAULT_HORIZON`); (2) surface
a conversion-rate PRIOR on procurement candidates ("Peel commitments of this
type historically reach tender X% of the time in Y months"), shown to inform the
human author, never an auto-claim.

**Design implication to preserve NOW:** the procurement spine's hard-key wiring
(`procurement_id` linking tender to award; `procurement_signals` back to
commitment signals) is what makes walking the arc possible. Keep that linkage
clean in every collector and the proposer. Full spec:
`docs/prediction-ledger-design.md` section 5.7.

## Parked / waiting

- **TPSB board minutes** — parked in `src/board_minutes.py`: tpsb.ca's WAF
  415s the collector site-wide despite an allow-all robots.txt. Unpark via
  board-office contact or WAF change.
- **Peel news-and-updates HTML posts** — page 1 is scanned for PDFs; collecting
  the paginated posts (×16) as documents is a follow-up.
- **Signal-level dedup** — blocker before the full title-backlog drain
  (RUNBOOK Step 6). Unblocked doc types (board_minutes) can extract now via
  `--doc-type`.
- **prospects ↔ contract_awards vendor join** — design note in
  `web/app/prospects/constants.ts` (normalized matching, org-resolver
  discipline).
- **OPP coverage (probed 2026-07-21; the open door is Infrastructure
  Ontario on MERX).** Likely the single largest police buyer in the
  province, currently dark to us except via federal grants and ontario.ca
  news. The arc is provincial: central purchasing plus Infrastructure
  Ontario for facilities; oversight signal is SolGen budget/estimates
  rather than a single board; detachment boards long-tail. Probe results
  (CI job 88525460550, read-only):
  - **Ontario Tenders Portal is CLOSED to automation.** It is
    Jaggaer-hosted (ontariotenders.app.jaggaer.com, supplier login at
    /esop/nac-host/public/web/login.html) and its robots.txt disallows the
    entire /esop tree to all agents, which covers every candidate public
    path; the site root is a 117-byte JS stub. Whether or not a no-login
    browse surface exists behind that, robots forbids automated
    collection, so OTP joins the registered-access policy bank as
    human-research-only. A future probe candidate that routes around this
    honestly: whether data.ontario.ca publishes an OTP tender dataset
    (publisher open data, like Windsor's).
  - **OPP procurement IS publicly reachable via merx.com/
    infrastructureontario** (OPP Modernization Phase Three visible on its
    awarded tab), on the platform the tenders_merx collector already
    speaks. Banked as a MERX buyer target pending the operator's browser
    provenance check; details in docs/merx-windsor-design.md section 8.
  - **Aggregators are never sources**: Tendersift and GlobalTenders
    confirmed OTP/OPP tenders exist; research tools only, provenance rule
    excludes them as collection sources.
