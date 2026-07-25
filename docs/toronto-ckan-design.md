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

Not yet pinned by the probe (the probe enumerated datasets, it did not dump
rows): the exact column names for the solicitation/call reference, the
per-row publisher notice URL, and the date fields. The build reads one
sample row per dataset via `datastore_search` (limit 1), maps the columns
once, and the validation bar in section 5 holds the mapping honest before
enablement. The design fixes the semantics (what each field must carry);
the build fixes the literal column names against a live sample.

## 3. Collector

### src/tenders_toronto.py (CKAN datastore read, three datasets)

Discovery is the CKAN action API on the publisher's own catalogue, no
scraping:

- Resolve each dataset via `package_show?id=<slug>` to get its active
  datastore resource id (prefer the CSV/JSON resource backed by the
  datastore; fall back to fetching the CSV resource directly if the
  datastore is not active).
- Page rows via `datastore_search` (`limit` + `offset`) until exhausted.
  A per-run NEW-row cap (25, board-minutes style, `content_hash(url,
  doc_type)` checked first) drains the multi-year history over days; the
  steady state fetches only rows whose hash is new.

Per row, emit one document:

- **`tobids-all-open-solicitations` -> `tender_notice`.** reference_number
  = Toronto's own solicitation / call reference (the hard key; see below).
  published_on = the closing date at day precision. buyer_name = "City of
  Toronto". content = the row's description / commodity text. url = the
  per-solicitation Toronto Bids notice page if the row carries one, else
  the dataset landing page anchored by reference (publisher artifact
  first, listing fallback, Windsor convention).
- **`tobids-awarded-contracts` -> `award_notice`.** Same reference as its
  originating solicitation where present, so the notice and its award share
  a hard key and reconcile. published_on = the award date at day precision.
  content includes the winning vendor and award value where the row
  carries them.
- **`tobids-non-competitive-contracts` -> `award_notice`, marked
  non-competitive.** A `non_competitive` marker rides in the document
  (status text / content prefix) so downstream can isolate sole-source
  awards, the signal this dataset uniquely provides. Same reference-key and
  date discipline as competitive awards.

Hard key (operator instruction): reference_number is Toronto's own
solicitation / call reference, never a CKAN row id. Toronto's procurement
references take forms like a Tender Call number, an RFQ/RFP number, or a
Doc number; the build maps the reference column from the sample row and the
validation bar requires it to parse on >= 90% of rows. The CKAN `_id` rides
only in the URL / content_hash namespace, never as the procurement key
(same discipline as the MERX id in tenders_merx).

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
VALIDATION log line per dataset:

- open-solicitations: >= 90% of rows parse reference AND closing date;
  nonzero rows.
- awarded-contracts: >= 90% of rows parse reference AND award date OR a
  published NULL-date row where the source genuinely omits it (never a
  fabricated date); nonzero rows; vendor field nonzero.
- non-competitive-contracts: nonzero rows; the non_competitive marker set
  on every row from this dataset; reference parse >= 90%.
- Below the bar: diagnose and extend the column mapping before enabling,
  never enable-and-hope.

## 6. Scheduling

A light requests collector (CKAN JSON, no Chromium): one new step in
daily-collect after the Windsor / MERX steps, sharing the politeness
pattern. Steady state is three `datastore_search` sweeps returning mostly
already-hashed rows; the per-run cap of 25 new rows bounds the initial
history drain.

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
