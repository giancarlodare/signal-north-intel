# Federal Contracts proactive-disclosure collector: Design (for review)

**Status: DESIGN FOR REVIEW. No code exists yet, nothing built.** Operator
approved building the collector; per the standing rule, this design is brought
for review before any code, same as the grants-awards collector.

This is the highest-yield source for the top of the demand-strength ladder.
Grants gave the leading indicator (commitment and intent); federal contracts
give the outcome (awarded), which is the strongest reconciliation evidence and
the rung the corpus is starved for (0 in_market, 2 awarded before this).

## What the dataset is (CI-probe-verified 2026-07-13)

Structurally identical to the grants dataset, so the grants-awards collector
is the template.

- Dataset: **Proactive Publication - Contracts** (owner `tbs-sct`),
  `open.canada.ca/data/en/dataset/d8f85d91-7dec-4fd1-8055-483b77225d8b`.
- Target resource: **"Contracts over $10,000"**, resource id
  `fac950c0-00d5-4ec1-a4d3-9cbebf98a305`, `datastore_active: true`. The CSV is
  **627 MB** and stays where it is; the CKAN `datastore_search` API serves
  filtered rows, exactly as for grants.
- `owner_org` filtering works. All-time record counts per department:

  | owner_org | department | records (all years) |
  |---|---|---|
  | ps-sp | Public Safety Canada | 2,725 |
  | cbsa-asfc | Canada Border Services Agency | 12,427 |
  | rcmp-grc | RCMP | 35,991 |
  | csc-scc | Correctional Service | 57,325 |
  | dnd-mdn | National Defence | 353,289 |
  | jus | Justice | (probe pending, large) |

## The field that changes everything: `procurement_id`

Each contract record carries both a disclosure `reference_number`
(e.g. `C-2017-2018-Q3-00060`) and a **`procurement_id`** (e.g. `D160830442`):
the solicitation identifier that ties the award back to the tender it came
from. This is precisely the hard key the procurement proposer keys on. So this
collector does not only add awarded-rung signal, it supplies the reference
numbers that make the procurement spine's hard-key path light up: a tender
(in_market) and its award (awarded) can be hard-keyed to the SAME procurement
via `procurement_id`, closing the loop the spine was built for. No other source
we have gives that.

Other useful fields (all probe-confirmed): `vendor_name` (who won),
`buyer_name` / `owner_org`, `contract_date` (award date), `contract_value` /
`original_value` / `amendment_value`, `description_en` (scope),
`commodity_type` / `commodity_code`, and competition context
(`solicitation_procedure`, `number_of_bids`, `limited_tendering_reason`,
`award_criteria`) that later feeds the Phase D neighbouring questions
(incumbent vulnerability, competitor positioning).

## Proposed design

**`src/contracts_federal.py`, weekly** (rides `weekly-discovery.yml` after the
grants awards step). A near-clone of `grants_federal_awards.py`:

- Same six departments (ps-sp, rcmp-grc, dnd-mdn, cbsa-asfc, csc-scc, jus),
  hardcoded, propose-then-approve.
- `datastore_search` POSTed with a JSON body (no query string, so
  open.canada.ca's `Disallow: /*?sort*` rules cannot be tripped), 20s
  Crawl-delay honored by PoliteFetcher, newest-first by `contract_date`,
  offset paging with a steady-state early stop on a fully-known page.
- **doc_type `award_notice`** (a contract award). This floors at grade 5
  (awarded) in the taxonomy, which is exactly right, and distinct from
  `grant_award` (which floors at commitment because a grant is upstream). No
  enum change needed: `award_notice` already exists.
- **Identity** = `content_hash(reference_number, contract_value)`. A
  re-disclosed amendment carries a changed value and inserts as a fresh
  document (the amendment is a real event); the original stays. `procurement_id`
  is captured in the body so the proposer can hard-key on it.
- `published_on` = `contract_date` (day precision); English fields with French
  fallback; bilingual pipe fields split; keywords.txt tag-only.
- Record URL: the award's page on the publisher's search UI
  (`search.open.canada.ca/contracts/...`), format CI-probe-verified before the
  first real run, with the ref-pinned search page as the documented fallback,
  same discipline as grants.

## Two decisions for you (volume is the real question)

DND alone has 353,289 all-time records, and even a 2024-04-01 window leaves
tens of thousands. Unlike grants (where sub-threshold is the point, because a
small grant is still a leading indicator), a contract AWARD is only
prediction-relevant if it is a material procurement a seller would actually
compete for. So two parameters need your call:

1. **Value floor.** Recommendation: ingest only contracts at or above
   **$100,000** (`contract_value`). This cuts the volume dramatically (most
   contracts are small), focuses on material procurements that predictions are
   about, and keeps DND tractable. The alternative is no floor plus reliance on
   the cap, which would bury the signal in routine sub-$100k purchases. My
   recommendation is the $100k floor; you may prefer a different number or
   none.
2. **Window and cap.** Recommendation: same **2024-04-01** window as grants,
   newest-first, with a per-department per-run cap of **50 new docs** (double
   the grants cap, because even floored the volume is higher). Newest-first
   means we always hold the most recent awards, which is what settles recent
   predictions; older awards page through slowly, which is acceptable because
   they are less useful for reconciliation.

## Follow-on, not v1 (flagged so it is not forgotten)

The `contract_awards` table and `find_or_create_vendor` already exist (the
CanadaBuys collector populates them with vendor linkage). Feeding
contracts-disclosure awards into `contract_awards` too would directly serve the
parked prospects-to-vendor join. Valuable, but scope creep for v1; v1 writes
`award_notice` documents only, exactly like the grants awards collector. The
vendor-linkage enrichment is a clean follow-on.

## Rejected alternatives

- **Downloading the 627 MB CSV weekly** and filtering locally: wasteful; the
  datastore API serves the same rows filtered.
- **Scraping search.open.canada.ca contract pages**: a JS UI over the same
  data; the dataset API is the honest machine interface.
- **`grant_award` doc_type**: wrong rung. These are contracts (awarded), not
  grants (commitment).
