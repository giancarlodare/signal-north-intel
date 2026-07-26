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

### 4d. Status of the run

The analysis runs NOW off the fetched page, no new collection needed to start
(`scripts/analyze_solgen_grants.py`): it builds the per-service capture table
(total, streams, projects, eligible-but-absent) and two ranked views (money on
the table; roster services absent from the ledger = warmest Tier-1 leads). The
formula-vs-competition flag keeps the ROI model peer-cohort relative. The
collector above productizes it for the maintained Tier-1 targeting feed.
