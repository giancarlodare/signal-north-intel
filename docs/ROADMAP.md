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

## Synapse Advisory drafting engine (banked 2026-07-21; separate IP, build on first paid engagement)

**Banked as Synapse Advisory IP, operator instruction 2026-07-21
(expanded spec same day). Not a Signal North product: zero SN code, zero
SN data, zero SN branding.** A bid/grant application drafting engine in
four layers; automated pipeline, human judgment at the top, the SN
operating model pointed at proposals:

1. **Client-material ingestion.** Uploads (Excel financials, capability
   decks, past proposals, CVs) parsed into a per-client, per-engagement
   knowledge base. Lives entirely on the Synapse side; this is the
   material the firewall says never enters SN.
2. **Intelligence layer.** The SN subscription feed as ONE input among
   several: procurement history with the buyer, incumbent and award
   patterns, grant program rules, plus geopolitical trends, policy
   announcements, budget signals, the "where the wind is blowing"
   strategic context.
3. **Generation.** Drafts that fuse client evidence with market
   intelligence against the RFP's own evaluation criteria, criterion by
   criterion.
4. **The audit loop.** Every draft scored section by section against the
   rubric; weak sections surfaced WITH REASONS; iterate to threshold;
   the human sharpens; version-stamped trail throughout, adjudicated the
   way the calibration audit adjudicates predictions. The methodology
   (the audit-loop discipline) is what transfers from Signal North; the
   implementation is built fresh as Synapse IP.

Demand evidence recorded: unsolicited McKinsey partner interest (would
anchor founding membership) and the Peel grant-writing thread.

**Founding-member structure (operator, 2026-07-21):** SN founding
membership includes preferred standing at Synapse (priority engine
access, founding engagement rates) as a CROSS-ENTITY PERK, never a
bundled product. Separate contracts and separate invoices: the SN
membership agreement references the Synapse benefit; Synapse engagements
are their own paper. The legal form and disclosure language are a
September counsel question (docs/legal-seam-investor.md, Synapse
section).

**Firewall implications live in docs/legal-seam-investor.md (Synapse
section), for counsel alongside the investor-seam flags.** Short form:
information flows SN to Synapse exactly as to any subscriber, never in
reverse; no client RFP responses, drafts, or engagement material ever
enters SN's corpus; conflict-check protocol so Synapse cannot draft
competing bids on the same solicitation.

**Build trigger: the first paid engagement post-gate, not before.** The
first real RFP with a real deadline designs the tool better than
speculation. Nothing is scaffolded until then.

## Cooperative purchasing layer (named week-2 sprint probe, upgraded 2026-07-21)

**A structural feature of Ontario municipal purchasing that per-buyer
portals partially miss**: cooperative tenders carry many buyers' demand in
one solicitation, and awards form contracts between the vendor and EACH
member agency (halton.ca states this explicitly for HCPG, whose published
member roster includes Halton Regional Police Service). Three official
vendor pages have now named this layer independently (DRPS, Vaughan,
Halton), and those vendor pages ARE the provenance chains.

Aggregate CPO list across the three sightings: HCPG (Halton Co-operative
Purchasing Group), PCPG (Police Cooperative Purchasing Group), Supply
Chain Ontario, OECM (named twice), provincial Vendor-of-Record
arrangements (named twice), the Ministry of Public and Business Service
Delivery marketplace (doingbusiness.mgs.gov.on.ca), Canoe Procurement
Group, Kinetic GPO, YPCO (York Purchasing Co-operative), HealthPRO, SGP.

Probe scope (week 2 of docs/august-sprint-plan.md, behind the sprint
fronts): for each CPO, does it publish opportunities and/or awards
publicly and collectably (no login, robots-compatible)? Standard
discipline: read-only, no accounts; public-and-collectable surfaces get a
design-first proposal, walled ones get recorded verdicts.

## Toronto procurement: GREEN via CKAN open data (verdict 2026-07-25)

Toronto's SAP Ariba front end is closed to automation, and that is
irrelevant. The City of Toronto publishes its bids, awards, and
non-competitive contracts as public open data through its CKAN API, the
same publisher-open-data route the Windsor collector already rides.

Probe evidence (CI job 89676754793, read-only, 2026-07-25):
package_search on the documented CKAN host
`ckan0.cf.opendata.inter.prod-toronto.ca` for bids / tenders / procurement
/ purchasing returned City of Toronto datasets:

- `tobids-all-open-solicitations` (Toronto Bids Solicitations), CSV/JSON/XML
- `tobids-awarded-contracts`, CSV/JSON/XML
- `tobids-non-competitive-contracts`, CSV/JSON/XML
- XML feeds: `call-documents-for-the-purchase-of-goods-and-services`,
  `competitive-call-award-results`, `non-competitive-contracts`; plus a
  `procurement-pipeline` index stub (0 resources at probe time).

Endpoint error ruled out: the earlier 404 came from querying
`open.toronto.ca` (the web host, not the API host), which 404s every
package_search. The 404 was the wrong host, not an absence.

`tobids-non-competitive-contracts` is the standout. Sole-source awards are
demand signal we collect from no other source; competitive-only feeds miss
them entirely. Provenance is publisher-published by definition (the city's
own open-data catalogue).

Build queued design-first: `docs/toronto-ckan-design.md` (Windsor pattern,
propose-then-approve, collector not started).

## API access (banked future capability, 2026-07-25; design-only, demand-pulled)

Expose the Signal North corpus and prediction table via an authenticated API
as a Tier-3 / enterprise offering. NOT a sprint item; not built until
triggered.

**Architecture note:** a thin authenticated READ layer over the existing
Supabase data (Supabase auto-REST plus a small FastAPI / Edge-Function layer
for clean endpoints), not a new product. Days of build, not months. Candidate
endpoints:

- `GET /signals`: query the corpus by buyer / category / date /
  defence-relevance / grade.
- `GET /predictions`: the demand-arc prediction table with CIs (the
  crown-jewel endpoint).
- `GET /solicitations`: open opportunities.
- Watchlist WEBHOOKS: push notifications into a subscriber's own CRM /
  pipeline. The highest-value pattern; drives enterprise stickiness.

**Three gating conditions before any build:**
1. Do NOT expose the prediction table until the confidence intervals and
   significance gates are real (the north-star spec built) and the ledger has
   a track record. An API over half-calibrated predictions is worse than none.
2. Build only when a paying Tier-3 buyer requires it ("we sign if you have an
   API"). Demand-pulled: an API is a standing uptime/support/stability
   commitment, not a one-time build.
3. Governance: API terms state it is the same neutral intelligence sold to any
   subscriber, read-only, rate-limited fairly, never a back-channel. Flagged
   for the September counsel package's neutrality-wall terms.

## Interactive prediction pathway (banked 2026-07-26; Wave 3 flagship visualization)

Click a prediction, it expands into an interactive horizontal timeline of
the reconstructed arc: real events in sequence by intel type, each node
clicking through to its source document; the measured significant lag per
phase above the flow; the projection extending forward as a widening
confidence cone (the cone IS the CI). Self-justifying prediction, and a
provenance trail competitors cannot replicate. Strictly downstream of the
engine: requires verified arc reconstruction, PUBLISHED rhythms, and
per-node provenance verification. Full spec: docs/wave3-portal-design.md.
Design intent only; nothing built ahead of the pilot.

## The client-facing gate (doctrine, 2026-07-26)

Governing doctrine for everything client-facing: an explicit backend ->
frontend gate; nothing a client sees crosses until it is defensible to a
skeptic. Withhold, never caveat forward. Three engineered gap types
(coverage, confidence, correctness) and per-surface gate tests for
signals, predictions, and drafted applications. Full doctrine:
docs/client-facing-gate.md; bound into the Wave 3 dashboard, Weekly
Signal, Grant Engine, and API designs. Design principle, not a build
item.

## Convergence indicator (banked 2026-07-26; client-facing predictive product, pilot-gated)

The client-facing product design for the predictive layer. Two claims: Claim
1 is the specific hard prediction (the ledger: precise, dated, rare, its
verified track record is the proof); Claim 2 is the convergence / movement
prediction ("independent sources converging on service + domain, expect
movement in ~N months, confidence X"), makeable far more often and the
feature subscribers watch. Claim 1's audited record makes Claim 2 credible.
The surface is a per-service, per-domain convergence indicator that rises as
independent upstream signals stack, always shows the converging signals
(never a black box), attaches the expected window from the measured
demand-arc lag with its CI, and progressively sharpens the predicted
instrument (grant / tender / legislation / program change) as signals land.
Full spec: docs/demand-arc-backtest-design.md section 0d; folded as banked
cross-references into docs/wave3-portal-design.md (dashboard) and
docs/published-brief-design.md section 9 (Weekly Signal). GATED on the
Toronto + Peel pilot proving significance; design-thinking only, nothing
built ahead of that.

## Parked / waiting

- **Extractor max_tokens bump for large docs (known-class fix, banked
  2026-07-26)** — two drain batch-1 docs failed with truncated model JSON
  ("Unterminated string" / "Expecting value"): the structured output hit the
  4096 max_tokens cap mid-response on signal-dense docs (a MERX award, a TPSB
  agenda). Fix when convenient: raise max_tokens (or chunk oversized docs) in
  src/signal_extractor.py; the two docs stay status=failed until then and
  re-extract after the fix.
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
  - **data.ontario.ca open-dataset probe: PARKED 2026-07-25 (verdict
    earned).** The host was unreachable across four probe attempts on Jul
    21, 22, 23, and 25 (robots.txt 502 / connection failures, all retries
    exhausted, three separate CI runners). The OTP open-dataset question is
    UNDETERMINED, not answered: a sustained-down host is not a "no". REVIVAL
    when the host recovers: re-run the CKAN package_search on
    data.ontario.ca for a tender/procurement dataset. PROXY COVERAGE while
    parked: provincial procurement signal rests on the IO newsroom awards
    leg (live) plus grants/budget signal; OTP tender feed stays undetermined
    pending host recovery.
  - **OPP procurement IS publicly reachable via merx.com/
    infrastructureontario** (OPP Modernization Phase Three visible on its
    awarded tab), on the platform the tenders_merx collector already
    speaks. PARKED 2026-07-21: neither the machine crawl nor the
    operator's human browse of infrastructureontario.ca found a link to
    the MERX page, so provenance is not established. Revival paths (both
    banked): a deeper targeted crawl of IO's site on a quiet day (the
    2026-07-21 sitemap sweep of 227 procurement-ish pages found no MERX
    link either), and the data.ontario.ca OTP-dataset probe below, which
    covers provincial procurement including OPP regardless of the IO
    question. PROXY COVERAGE: the IO newsroom collector (design in
    docs/merx-windsor-design.md section 9, approved target 2026-07-21)
    makes IO's line "awards via newsroom live, tender feed parked pending
    provenance". Details in docs/merx-windsor-design.md sections 8-9.
  - **Aggregators are never sources**: Tendersift and GlobalTenders
    confirmed OTP/OPP tenders exist; research tools only, provenance rule
    excludes them as collection sources.
