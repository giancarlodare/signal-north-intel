# Upstream-intent collector at scale: design (service-parameterized)

Status: PROPOSED (design-first, 2026-07-26). The Peel precision proof passed
both rounds (news mix, then the richer board-docs mix: 9/12 non-noise on board
docs vs 2/10 on news releases, noise precision intact, zero hard FPs, the
realized-acquisition fix stable). Scaling is unlocked; this is the design to
approve before the build. Extends docs/upstream-intent-layer-design.md.

## 1. Shape: one collector, service config rows, TWO source types per service

`src/upstream_intent.py`, parameterized by a per-service config (the
bids&tenders pattern): each covered service row carries its sources and its
governing council. Per service:

**Source type 1: police board docs + service newsroom.**
- Board docs are the intent-rich vein (proven): budget / capital-plan /
  agenda-report doc types PRIORITIZED over news. Where the board is already
  collected by board_minutes (Peel, TPSB, York, Durham, Halton, Waterloo,
  Sudbury), the upstream layer READS THE CORPUS (no refetch); the intent
  classifier runs over board docs as a new extraction pass.
- Service newsroom: the news-feed listing per service (Peel pattern:
  /news-feed/news-releases/ + /news-feed/posts/<slug>), requests-collected,
  keep-scope filter as designed.

**Source type 2 (NEW): the municipal/regional COUNCIL minutes for the council
each police service board reports to.** Rationale (operator 2026-07-26): the
demand arc ORIGINATES at council. Public frustration and councillor pressure
surface there first, flow to the police board as pressure, become budget
lines, become tenders. Councils are also where the biggest capital budgets are
FORMALLY APPROVED. Council minutes therefore feed TWO arc rungs:
- earliest PRESSURE (rung 1 inputs: councillor motions, deputations,
  public-safety debates), and
- BUDGET APPROVAL (rung 3 commitment: the approved capital line, a hard
  commitment the demand-arc backtest can anchor on).

## 2. Service -> governing council mapping (part of this design)

| Police service / board | Governing council | Minutes surface (probe-first) |
|---|---|---|
| Toronto Police Service Board | Toronto City Council | secure.toronto.ca TMMIS (agenda item search; probe for server-side/API) |
| Peel Regional Police Board | Region of Peel Council | peelregion.ca council meetings (probe; escribe risk) |
| York Regional Police Board | York Region Council | york.ca council/committee (probe) |
| Durham Regional Police Board | Region of Durham Council | durham.ca council (probe; iCompass/CivicWeb risk) |
| Halton Police Board | Halton Region Council | halton.ca council (probe) |
| Waterloo Regional Police Board | Region of Waterloo Council | regionofwaterloo.ca council (probe) |
| Greater Sudbury Police Board | Greater Sudbury City Council | agendasonline.greatersudbury.ca (probe; historically server-side) |
| Windsor Police Board | Windsor City Council | citywindsor.ca council minutes (probe) |
| Ottawa Police Services Board | Ottawa City Council | ottawa.ca / eScribe (JS risk; render-adapter path) |

Rule: every council surface is PROBED before build (requests-collectable or it
parks for the render adapter with a proxy line, the board-minutes discipline).
The mapping table is config data; adding a service means adding a row.

## 3. The council noise problem: RELEVANCE filter AHEAD of the intent filter

Council minutes are far noisier than board docs (zoning, water, transit;
occasional public-safety items). Without a pre-filter the council feed floods
the brief with irrelevant municipal RFPs. Two-stage pipeline, in order:

1. **Public-safety RELEVANCE filter (cheap, keyword, BEFORE any LLM):** a
   council item survives only if it matches the police/public-safety scope:
   the service's name and acronym, "police", "community safety", "public
   safety", "emergency services", "911", "paramedic/fire" (config-tunable),
   or the police capital budget line. Everything else is dropped at zero LLM
   cost. This is a SCOPE filter (Hansard precedent), not keep-all: council
   corpora are mostly out-of-scope by volume.
2. **Intent classifier (the proven Peel extractor):** procurement_intent /
   funding_intent / pressure_signal / noise, with the realized-acquisition
   sense, over survivors only. Council-sourced signals tag their arc role:
   pressure items feed rung 1; approved-budget items feed rung 3.

## 4. Doc types and extraction path

- Board docs: already `board_minutes` in the corpus; the intent pass adds
  signals, no new doc_type.
- Service newsroom: `news_release` (existing type, existing forward path).
- Council minutes: new `council_minutes` doc_type (enum migration) so arc
  attribution and the relevance filter are auditable per source. Not in the
  daily forward-extraction path; extracted via the intent pass with the
  relevance pre-filter.

## 5. Rollout order (validated waves, per house rules)

1. **Wave A (corpus-only, no new fetching):** run the intent pass over the
   ALREADY-COLLECTED board docs of the six live boards + Peel. Cheapest
   possible scale step; immediately feeds demand-arc rungs.
2. **Wave B:** service newsrooms for those services (probe each listing URL,
   Peel pattern).
3. **Wave C:** council minutes, one council at a time, probe-first, relevance
   filter validated per council with a VALIDATION line (sampled items:
   relevance-filter survival rate, intent yield on survivors, spot-check that
   dropped items are genuinely out of scope). Toronto and Peel councils first
   (largest capital budgets, densest arc data).

Per-wave validation bar before the next wave: intent precision on a sampled
adjudication >= the Peel rounds' standard, and the council relevance filter
must not leak (sampled dropped items reviewed once per council at enablement).

## 6. Budget note

Wave A is bounded by the existing board corpus (hundreds of docs, one-time
pass at backfill rates); newsroom/council steady state rides the per-run caps.
The council relevance pre-filter is the cost control: LLM spend only on
survivors. Numbers restated at the Aug 4 extraction-budget checkpoint.
