# Tiered product map (operator request 2026-07-28)

The pricing table is the ROADMAP, not a launch checklist. This maps every
feature row on /pricing to what actually exists today, what is a near-term
build on data we already hold, and what is aspirational/gated -- so the
September launch sells a minimum REAL feature set per tier with honest
live-vs-coming labeling, and nothing is ever sold as live before it is.

Standing constraint restated: demand-arc foresight publishes NOTHING until
a cell genuinely clears the Paule-Mandel + P2 gate and task #53's
client_released human gate. It is roadmap, never launch copy.

## Classification (all 15 pricing rows)

### Category 1 -- BUILT (live or staged-dark today)

| Feature | State |
|---|---|
| Full weekly intelligence brief | BUILT. Generator + editor + member brief page (verified end-to-end today incl. RLS). Launch dependency is editorial cadence, not code. |
| Sourced publisher records | BUILT and hardened today: per-item provenance links on ~99.4% of the corpus, honest record/listing/portal labels + reference numbers on the rest. This is a genuine differentiator; sell it hard. |
| Watchlists (the watch half) | BUILT: watches, daily matcher, event log, trust log ("we told you first"). Alerts (email on match) are the missing half -- see category 2. |
| Priority support and standing | Process, not code. Real on day one for Founding/Enterprise. |

### Category 2 -- NEAR-TERM: data already in the corpus, build is assembly

Ordered by (tier value unlocked) x (closeness to done):

1. **Live closing-soon surface** ("full platform dashboard" core, Pro).
   Data: ~85 tenders/day, 15 buyers, closing dates parsed at 100% bars.
   Design delivered separately (docs/wave3-live-surface-design.md). This is
   the single build that makes Pro feel alive between issues, and it gives
   watch alerts a live universe to fire on. **Build first.**
2. **Weekly headline digest (email)** -- the Free/Weekly funnel row; already
   scoped as task #57 (default-on send, shared SMTP domain). The digest is
   the published brief's headlines, so content exists the day it ships.
3. **Expiring-contract tracking v1** (Pro). Two honest phases:
   - v1 FEDERAL: open.canada.ca contract rows carry contract periods/end
     dates TODAY -- a "contracts expiring in the next N months" view over
     data we hold is real immediately. `contract_expiry` already exists in
     the signal taxonomy.
   - v2 MUNICIPAL: needs the award end-date enrichment backlog (task #56:
     0 of 548 awards carry end dates today; per-bid enrichment is
     cost-gated). Label the launch feature "federal-first, municipal
     expanding" -- never imply municipal end dates we do not hold.
4. **Buyer and agency profiles v1** (Pro). Pure assembly: per organization,
   its recent tenders, awarded history, board signals, categories. Every
   row exists; the build is one page + one gate-cleared data slice.
5. **Watch alerts (email on match)** -- completes the watchlists row. The
   matcher and event log exist; the build is a send step + preference.
6. **Grant eligibility teaser** (Free) -- a digest block from the grants
   corpus (PS Canada programs + Ontario funding pages + deadlines). Small.
7. **Incumbent intelligence v1** (the incumbent half of "pricing and
   incumbent intelligence", Pro): federal awards carry vendor + amount
   today; council award mining adds municipal vendors. Label federal-first.
8. **Multiple seats** (Enterprise): auth already supports N members; the
   build is account grouping. Small, needed only when first team signs.

### Category 3 -- ASPIRATIONAL / GATED / ENTERPRISE-NEGOTIATED

| Feature | Honest state |
|---|---|
| Demand-arc foresight views | GATED. Zero cells clear the statistical gate today (Paule-Mandel result 2026-07-28: zero honest cells beats one dishonest one). Roadmap copy only: "publishes when it clears our statistical gate." Task #53 human gate stands above everything. |
| Pricing intelligence (the pricing half) | Aspirational depth: systematic unit-price benchmarking needs document-level enrichment we have not built. Incumbent v1 (cat. 2) is the honest launch slice. |
| Network and market intelligence | As a NAMED feature this is category 3 until defined. The honest launch mapping is corpus stats + category/buyer activity views riding the live surface; anything grander (relationship graphs) is roadmap. Recommend scoping the launch cell to what the dashboard actually shows. |
| API access | Nothing built. Enterprise-negotiated roadmap; do not table-check it as live. |
| Custom coverage | REAL as a service (the design-first source pipeline is literally the shop's daily practice; DRPS was operator-requested coverage delivered in a day). Sell as service with honest per-source lead times, not as a self-serve feature. |

## Minimum honest launchable set per tier (September)

- **Free**: digest email (build #2) + grant teaser (build #6). Two small
  builds and the funnel works.
- **Weekly ($390/mo)**: full brief + sourced records -- ALREADY REAL. This
  tier is sellable the day the editorial cadence is weekly and reliable.
- **Pro ($1,900/mo)**: everything in Weekly + live dashboard (build #1) +
  watchlists with alerts (#5) + buyer profiles (#4) + expiring contracts
  federal-first (#3). Demand-arc row carries an explicit "in development,
  gate-governed" marker at launch. That is a real $1,900 product: live
  stream + watches + profiles + expiries + the brief.
- **Enterprise**: Pro + seats (#8) + custom coverage as a service +
  priority standing. API stays quoted as roadmap in the agreement.

Pricing-page honesty change to make before launch: the tier table needs a
live vs "in development" visual distinction on the demand-arc row (and API
row), so the table never claims an ungated feature. Copy change, operator
approves wording.

## Build order recommendation (question 4)

1. Live surface (unlocks the Pro dashboard + alert universe; data 100% ready)
2. Digest email (unlocks Free + the funnel; scoped already)
3. Watch alerts (completes a checked Pro row; small)
4. Buyer profiles v1 (assembly)
5. Expiring contracts v1 federal (real data today) -- then municipal via the
   cost-gated end-date enrichment (#56) as v2
6. Grant teaser (rides the digest)
7. Incumbent v1 federal (after profiles, shares the assembly)

The operator's instinct on expiring contracts is half right: the AWARD data
is rich, but municipal END DATES are absent at source until the enrichment
backlog runs (task #56), which is why federal leads that build. The
fastest whole-value path is the live surface: zero missing data, and three
pricing rows (dashboard, watchlists/alerts, network intelligence's honest
scope) hang off it.
