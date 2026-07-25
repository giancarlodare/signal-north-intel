# Toronto CKAN open-data tender + award collector: design

Status: PROPOSED (design-first, 2026-07-25). Structure evidence from the
read-only CI probe the same day (job 89676754793). Collector not started;
propose-then-approve holds. This design comes before the collector, per the
operator's instruction.

## 1. Scope

One requests-based collector on the Windsor open-data pattern (the
CanadaBuys / board-minutes politeness stance: SignalNorthCollector UA,
robots respected, 2s shared delay, loud failure on empty). No Playwright,
no accounts, no new schema. Toronto's SAP Ariba front end stays closed to
automation and is irrelevant here: we collect the city's own published
open data, not the Ariba app.

| Target | Why | Provenance |
|---|---|---|
| `tobids-all-open-solicitations` | Open Toronto bids and tenders: the active-opportunity feed with closing dates | City of Toronto CKAN open-data catalogue, publisher-published by definition |
| `tobids-awarded-contracts` | Competitive award results: who won, at what value | Same catalogue |
| `tobids-non-competitive-contracts` | Sole-source awards. Demand signal we collect from no other source; competitive-only feeds miss it entirely | Same catalogue |

CKAN host: `https://ckan0.cf.opendata.inter.prod-toronto.ca` (the API
host). NOT `open.toronto.ca`, which is the web host and 404s every
package_search / datastore call. This host confusion caused the earlier
false 404; it is recorded here so no future probe repeats it.

## 2. Probe evidence the parsing rests on

package_search on the CKAN host for bids / tenders / procurement /
purchasing returned the three target datasets above plus XML-only feeds
(`call-documents-for-the-purchase-of-goods-and-services`,
`competitive-call-award-results`, `non-competitive-contracts`) and a
`procurement-pipeline` index stub (0 resources at probe time). The three
`tobids-*` datasets each expose CSV, JSON, and XML resources, so the
collector reads structured rows, never scraped HTML.

Columns pinned from the live datastore fields by the CI validation dry-run
(2026-07-25, regenerate-brief probe override, job 89681821890):

- open-solicitations: `Document Number`, `Submission Deadline` (close),
  `Issue Date`, `Solicitation Document Description`, `Division`,
  `High Level Category`.
- awarded-contracts: `Document Number`, `Successful Supplier`,
  `Award Authority Obtained Date` (the award date), `Solicitation Document
  Description`, `Division`. MANY rows share one `Document Number` (one per
  successful supplier), so the reference is the clustering key, not the row
  identity (see section 3).
- non-competitive-contracts: `Workspace Number` (per-contract key), `Reason`
  (the sole-source justification, used as the description), `Contract Date`
  (award date), `Supplier Name`, `Contract Amount`. There is NO solicitation
  reference (sole-source), so reference_number stays NULL and identity keys
  on Workspace Number.

The literal names are resolved at run time by `_resolve_columns` (logged
every run), so a column rename surfaces as an UNMAPPED warning and a failed
validation bar rather than a silent regression.

## 3. Collector

### src/tenders_toronto.py (CKAN datastore read, three datasets)

Discovery is the CKAN action API on the publisher's own catalogue, no
scraping:

- Resolve each dataset via `package_show?id=<slug>` to get its active
  datastore resource id (prefer the CSV/JSON resource backed by the
  datastore; fall back to fetching the CSV resource directly if the
  datastore is not active).
- Page rows via `datastore_search` (`limit` + `offset`). A per-run NEW-row
  cap (100, `content_hash` checked first) drains the multi-year history over
  days; unlike MERX each row arrives whole in the page (no per-row fetch),
  so the cap costs Toronto nothing and only paces our own writes. Steady
  state stops after two all-known pages.

Per row, emit one document:

- **`tobids-all-open-solicitations` -> `tender_notice`.** reference_number
  = the solicitation `Document Number`. published_on = the closing date
  (`Submission Deadline`) at day precision. buyer_name = "City of Toronto".
  url = the dataset landing page anchored by reference (open data carries no
  per-solicitation notice URL).
- **`tobids-awarded-contracts` -> `award_notice`.** reference_number = the
  same `Document Number`, so the award clusters to its solicitation.
  published_on = `Award Authority Obtained Date`. content carries the
  `Successful Supplier` and award value.
- **`tobids-non-competitive-contracts` -> `award_notice`, marked
  non-competitive in the title and content** (the `status` column is the
  processing_status enum, not a business marker, so the sole-source signal
  rides in the title "Non-competitive: ..." and the content's first line
  instead). No solicitation reference (sole-source), so reference_number
  stays NULL; the `Reason` (sole-source justification) is the description,
  the signal this dataset uniquely provides. published_on = `Contract Date`.

Hard key vs row identity (a distinction the live data forced): the
CLUSTERING key is Toronto's own reference (`Document Number`), stored in
reference_number so awards cluster to their solicitation, exactly as the
operator asked. But awarded-contracts carries MANY rows per Document Number
(one per successful supplier), so the Document Number cannot be the row
IDENTITY: `content_hash` keys on the reference PLUS supplier PLUS award date
for awards, or the Document Number alone for the one-row-per-solicitation
open feed. Non-competitive rows key on `Workspace Number` (their per-contract
identifier) in a separate namespace. The CKAN `_id` is never used (unstable
across dataset refreshes). Keying identity on the reference alone would have
collapsed every award under a solicitation into a single row; the CI dry-run
caught it before enablement.

Dates (per the #103 fix): `date_precision` is always `"day"`, never None.
When a row carries no usable date, published_on is NULL and date_precision
stays `"day"`; the null-date signal rides in published_on, matching
board_minutes and the four collectors corrected in #103. None beats a wrong
date: no closing or award date is ever fabricated or inferred.

Keep-all with defence_relevant tagging (unchanged discipline): every row is
kept; the filter tags, it never drops. Toronto Police Service (TPS) and
Toronto Fire / paramedic commodity items tag defence_relevant via the
existing keyword list; add "TPS" and "Toronto Police" to the acronym set if
the sample rows title police items by acronym (the Windsor WPS / Ottawa OPS
precedent).

LOUD FAILURE: a `datastore_search` that returns 0 rows for the open
solicitations dataset raises (Toronto always carries active
opportunities); per-row parse failures count toward an error budget (25)
then raise. A silent-empty CKAN response never passes as success.

## 4. Sources, orgs, tagging

- Sources migration: one URL-key-guarded row per dataset (or one row keyed
  on the CKAN host with the three slugs recorded), gov_website / municipal
  / scraper / daily.
- ORG_SEED: City of Toronto (municipality, ON) if not already present;
  Toronto Police Service if police items resolve by name.
- defence_relevant keyword additions as in section 3.

## 5. Validation before enablement (tier-1 bars)

CI dry-run before the migration applies and the build PR merges, one
VALIDATION line per dataset. `key_parsed` is the row identity key
(solicitation Document Number, or Workspace Number for non-competitive);
`ref_parsed` is the solicitation reference specifically.

RESULT (job 89681821890, first sample page per dataset, 100 rows each):

- open-solicitations (total 905): key_parsed 100%, date_parsed 100%. PASS.
- awarded-contracts (total 7583): key_parsed 100%, date_parsed 100% after
  pinning `Award Authority Obtained Date`; vendor nonzero. PASS.
- non-competitive-contracts (total 2922): key_parsed 100% (Workspace
  Number), date_parsed 100%, non_competitive marker on every row.
  ref_parsed 0% is STRUCTURAL, not a defect: sole-source contracts have no
  solicitation. PASS.

Bar: key_parsed AND date_parsed >= 90% per dataset (a genuinely
source-omitted date is a published NULL, never fabricated). Below the bar:
diagnose and extend the column mapping before enabling, never
enable-and-hope.

## 6. Scheduling

A light requests collector (CKAN JSON, no Chromium): one new step in
daily-collect after the Windsor / MERX steps, sharing the politeness
pattern. Steady state is three `datastore_search` sweeps returning mostly
already-hashed rows; the per-run cap of 100 new rows per dataset bounds the
initial history drain (awarded-contracts' 7583-row backlog drains over
days, board-minutes style).

## 7. Banked, not built

- The XML-only feeds (`competitive-call-award-results`,
  `non-competitive-contracts` XML, `call-documents-...`) are redundant with
  the `tobids-*` datastore reads for now; banked as a fallback if a
  `tobids-*` dataset is ever retired.
- `procurement-pipeline` (0 resources at probe time) is a forward-looking
  signal if Toronto populates it; re-probe on revival.
- Toronto's Ariba supplier portal stays out of scope: closed to
  automation, and the open data covers the same opportunities and awards
  with clean provenance.
