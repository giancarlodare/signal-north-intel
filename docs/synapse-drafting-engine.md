# Synapse Advisory drafting engine: go-to-market structure (banked)

Status: BANKED strategy, operator 2026-07-25. NOT a build. The engine stays
gated to the first paid engagement, post-October; nothing here changes the
sprint. Synapse Advisory IP, separate from Signal North: zero SN code, zero SN
data crossing the firewall, zero SN branding. The four-layer engine spec lives
in docs/ROADMAP.md ("Synapse Advisory drafting engine"); this doc records how
it goes to market.

## 1. One engine, three tiers (differentiated by how much human judgment wraps it)

The same scored-draft engine serves BOTH the enterprise and small-service
markets. The tiers differ only in how much Synapse human judgment wraps the
identical engine output.

- **Tier 1 Self-serve** (small police/fire services with no grant writers,
  chiefs writing their own applications): the customer edits the tool's scored
  draft themselves. No Synapse human time. Priced as software, anchored to ROI.
  Hypothesis: $2 to 5K/yr subscription, or $500 to 1.5K/application. The
  public-data ROI pitch ("here is the grant money you are eligible for and not
  winning") is what sells it.
- **Tier 2 Assisted** (mid-market): tool draft PLUS a Synapse associate review
  pass on the rubric-flagged weak sections. Priced as software-plus-hours.
  Hypothesis: $3 to 8K/application.
- **Tier 3 Done-for-you** (enterprise / McKinsey-tier / high-stakes): a full
  Synapse engagement; the engine is the internal accelerator the client never
  sees. Priced at consulting rates (five figures and up). The client is buying
  the outcome, the accountability, and senior human judgment, not software.

- **Signal North intelligence subscription sits UNDER all three** and is the
  small-service entry point: a cheap or free "your eligible grants + your ROI
  gap" feed that converts into the drafting tiers.

## 2. Pricing principle

- Tier 1 is priced on VALUE: the ROI gap, provable from public data.
- Tier 3 is priced on TIME: consulting rates.
- Tier 2 bridges the two (software-plus-hours).
- Every number above is a HYPOTHESIS to validate in post-October customer
  discovery, not a decision.

## 3. Why the tiers compound (the strategic point)

Small-service volume is not a low-margin distraction; it is the machine that
sells the enterprise tier:

- It is the FUNNEL (SN subscription -> Tier 1 -> up-tier as stakes rise).
- It is the TEMPLATE-REFINEMENT engine (every application sharpens the rubric
  and the winning-language library the engine draws on).
- It is the PUBLIC TRACK RECORD ("helped X services win $Y") that is the
  credibility asset the Tier 3 enterprise sale rests on.

## 4. Grounding analysis: small-Ontario-service grant ROI table

Purpose: ground Tier 1 targeting and the ROI model in real public data. For
each small Ontario police (and fire, if collectable) service, a per-service
row of: total grant dollars awarded over ~3 years, distinct grants won, and the
ELIGIBLE-BUT-NOT-WON gap versus a peer cohort of similar-size services. Ranked
output: most award history = warmest prospect (they already play the game);
largest gap = biggest ROI pitch (money left on the table).

### 4a. Data sources (named)

- **Provincial SOLGEN grant awards (the core input, and a COVERAGE GAP, see
  4c).** The Ministry of the Solicitor General runs the grants that dominate
  small-police funding: the Community Safety and Policing (CSP) Grant,
  Proceeds of Crime Front-Line Policing, Guns/Gangs/Violence Reduction, RIDE,
  and similar. The AWARD RECIPIENTS (which service got how much, which year)
  are the table's backbone.
- **Federal grant awards (HAVE).** `src/grants_federal_awards.py` already
  collects federal grant/contribution awards from open.canada.ca with
  `recipient_legal_name`, value, and dates (doc_type `grant_award`). This
  covers Public Safety Canada and related federal transfers to services, a
  minority of small-police funding but real and in-corpus today.
- **Eligibility universe.** The set of Ontario municipal police services (and
  fire services) plus their size proxy (population served / budget / sworn
  strength) to define peer cohorts. Public: OAPSB / ministry directories,
  StatsCan police administration data.
- **Signal North org resolution** to attribute awards to canonical services
  and roll services into peer cohorts.

### 4b. Method (once the data is in)

1. Aggregate `grant_award` documents per recipient service over the trailing 3
   years: total dollars, distinct grants, years active.
2. Define peer cohorts by size band (e.g. services within +/- 30% population).
3. Eligible-but-not-won gap = grants that >= K peers in the cohort won that
   this service did not, valued at the cohort's median award. Ranked two ways:
   warmest (most award history) and biggest ROI (largest gap).
4. No fabricated numbers: a service with thin coverage is labeled
   insufficient, never given a soft gap estimate (same discipline as the
   demand-arc gate).

### 4c. Coverage: the SOLGEN award ledger is FOUND (operator 2026-07-25)

The core input is now identified and confirmed collectable:
**https://www.ontario.ca/page/current-community-safety-project-grant-recipients**
the authoritative per-service SOLGEN grant-award ledger. Server-side Drupal
(our fetch pulled the full tables), publisher-official, modified 2026-05-28. It
lists recipients + dollar amounts across FIVE streams:

- Community Safety and Policing (CSP) local (~$74.8M/yr, 88 projects) and
  provincial ($16.4M, 39 projects);
- Proceeds of Crime Front-Line ($6M / 3yr, 23 projects);
- Victim Support ($6M / 2yr);
- Safer and Vital Communities ($2M).

We do NOT collect it today (we collect Ontario grant PROGRAMS via
`src/grants_ontario.py`, not award recipients; federal awards have recipients
but not provincial SOLGEN). This is the named SOLGEN award source we had been
missing, and it is the ledger the small-service ROI product depends on.

**Collector proposal (design-first, probe done via the analysis fetch):**
`src/grants_solgen_recipients.py`, a requests collector on the Windsor/IO
pattern (server-side HTML, robots honored, loud-fail on empty). Parse each
stream's recipient table into `grant_award` documents keyed on (recipient
service, stream, project), buyer/funder = Ministry of the Solicitor General,
recipient = the service, value = the dollar amount, published_on = the funding
year (day precision, never fabricated). One sources row, org resolution to
canonical services. Validation dry-run with a per-stream recipient/amount parse
bar before enablement. This is the collector that turns the one-off analysis
into a maintained ledger that refreshes when the ministry updates the page.

### 4d. Analysis v1 run (2026-07-25) and what it exposed

`scripts/analyze_solgen_grants.py` fetched and parsed the ledger. Nine streams
present: Projects receiving LOCAL priorities, Projects receiving PROVINCIAL
priorities, Mobile Crisis Response Team Enhancement, Bail Compliance and Warrant
Apprehension, Preventing Auto Thefts, Proceeds of Crime Front-Line, Victim
Support, Safer and Vital Communities, Fire Protection. Two v1 defects to fix
before the table is trustworthy:

- Aggregation grouped per RAW recipient row, so a multi-detachment force (OPP)
  fragmented into dozens of rows instead of one per-service total. Fix:
  aggregate by CANONICAL service (roll detachments up), summing across streams.
- The cross-reference roster is our ~15 seeded police orgs, several NON-Ontario
  (Calgary, RCMP, Surete du Quebec), and mixes service-vs-board names. Fix:
  build the real universe of Ontario municipal police services (View B is only
  as good as that roster) and match service names, not board names.

## 5. Refinements (operator 2026-07-25): the CSP-local formula is the Tier-1 wedge

### 5a. MAJOR reframe: CSP local-priorities is a FORMULA ALLOCATION, not a competition

Every police service has a PRE-DETERMINED CSP local-priorities entitlement; the
only requirement to receive it is submitting an application specifying how the
money will be spent. Not applying = FORFEITING money already allocated to them.
This is the cleanest Tier-1 product case: no ROI uncertainty, no absorptive-
capacity caveat, a binary claim-or-forfeit. The pitch is "you forfeited $X in
already-allocated money; this tool files the compliant spending plan in an
afternoon." Re-prioritize the analysis around it:

1. Determine whether the CSP local-priorities ALLOCATION FORMULA (or the
   per-service allocation table) is public (grant guidelines / ministry
   allocation schedule). If so, compute each service's entitlement.
2. Cross-reference entitlement against the recipient page to flag services that
   did NOT claim, claimed PARTIALLY, or claimed LATE. These are the highest-
   value, easiest-sell Tier-1 leads.
3. Keep the competitive-stream gap (provincial priorities, Proceeds of Crime,
   Victim Support, Safer and Vital, and the targeted streams) as the SECONDARY,
   capacity-bounded ROI layer (5b).

### 5b. Competitive-stream ROI is CAPACITY-bounded, not writing-skill-bounded

A 40-officer service cannot deliver a $13M project regardless of application
quality. Competitive-stream ROI claims must be peer-cohort relative where the
cohort is defined by size AND delivery capacity: "services of your size and
capacity capture $X, you are at $Y." Never fantasy-relative ("you could get
Toronto money"). This keeps the pitch credible.

### 5c. Formula-vs-competitive split (confirm per stream, never mis-pitch)

Working split, to confirm against each stream's program rules before any pitch:

- FORMULA / ENTITLEMENT: CSP local-priorities (the wedge above).
- COMPETITION / DISCRETIONARY: CSP provincial-priorities, Proceeds of Crime
  Front-Line, Victim Support, Safer and Vital Communities.
- TARGETED (confirm each): Mobile Crisis Response Team Enhancement, Bail
  Compliance and Warrant Apprehension, Preventing Auto Thefts, Fire Protection
  (these may be allocation-shaped or invitation-based; do not assume). A
  competitive stream must never be pitched as guaranteed money.

### 5e. The denominator: the CSPA police-services roster (operator 2026-07-25)

The absentee count's denominator is the OFFICIAL roster of police services under
the Community Safety and Policing Act (CSPA), maintained by the Solicitor
General / Inspectorate of Policing. NOT a municipality list (OPP-contracted
municipalities have no service to fund and are not leads) and NOT our corpus
roster. Only entities on this list are eligible to claim a local-priorities
allocation, so it is the correct denominator that survives a skeptical chief.

The count method:
1. Find the authoritative CSPA services list on ontario.ca / SolGen sources.
2. Parse the recipient page, isolate the CSP LOCAL-priorities recipients
   specifically (the formula stream), separate from provincial-priorities.
3. Diff the CSPA roster against the local-priorities recipients.
4. Output: the number and NAMED list of CSPA services absent from the
   local-priorities stream (the forfeited-allocation Tier-1 lead list), stated
   with the method + denominator so it is defensible.
5. If the local-priorities ALLOCATION FORMULA is published on ontario.ca,
   compute per-service entitlement so each absence converts to a precise
   forfeited-dollar figure.

Special handling to flag in the roster: First Nations police services (distinct
funding paths, may not be CSP-local eligible) and joint-board services (one
board, multiple municipalities) so the denominator is not over- or
under-counted.

### 5d. Next steps (design-first, still gated, no sprint change)

1. Probe the CSPA services roster URL + the CSP local allocation formula /
   per-service allocation table on ontario.ca / SolGen.
2. Isolate the local-priorities recipients from the ledger; diff against the
   CSPA roster for the forfeited-allocation lead list.
3. Fix v1 aggregation (canonical rollup) for the capture totals.
4. The `grants_solgen_recipients.py` collector (section 4c) turns this into a
   maintained feed once the analysis is validated.
