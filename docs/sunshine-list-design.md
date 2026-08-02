# Sunshine List + StatCan ingest — design (operator approval required)

Status: PROPOSED 2026-08-02. Gated class (new data sources). Approved in
principle by the operator 2026-08-02 ("send the design doc and I'll approve
same day"); nothing builds until the explicit go.

## What this is

The first two Layer-1 LEDGER sources of the labour/compensation collection
(operator addendum 2026-08-02): annual, structured, downloadable files — no
scraping, no LLM, no extraction spend.

1. **Ontario Public Sector Salary Disclosure ("Sunshine List")** —
   data.ontario.ca, Open Government Licence – Ontario. One structured file
   per disclosure year, every public employee over $100k with employer,
   position, salary, taxable benefits. Robots: **ALLOWED** (probed
   2026-08-02, crawl-delay 10s — moot for dataset downloads).
2. **StatCan Police Administration Survey** — annual personnel and
   expenditure by police service (authorized/actual strength province-wide).
   Table CSVs via the StatCan tables endpoint. Robots: **ALLOWED**
   (crawl-delay 2s). Rides in the same PR; it is a strict subset of the same
   ingest pattern.

Both also serve the fire/EMS domain expansion: Sunshine covers fire and
paramedic employers, and FIR (next on this pattern) carries fire and
policing expenditure by municipality.

## Decisions proposed

- **D1 — Rows land in their own tables, not in `documents`.** These are
  datasets (hundreds of thousands of rows/year), not documents; stuffing
  them into `documents.content` would make them unqueryable and bloat the
  corpus the extractor walks. Two new tables:
  - `salary_disclosures(year, employer, employer_sector, last_name,
    first_name, position, salary_paid, taxable_benefits, source_url,
    ingested_at)` — unique on (year, employer, last_name, first_name,
    position).
  - `police_admin_stats(year, service, metric, value, source_url,
    ingested_at)` — long format, unique on (year, service, metric).
  Migration SQL comes to the operator verbatim for pasting, as always.
- **D2 — Scope filter at ingest, full file retained on disk only
  transiently.** We ingest rows for employers matching the public-safety
  scope (police, fire, paramedic/EMS employers plus their boards and the
  provincial services) rather than all sectors. The operator's "over-capture"
  ruling applied to the keep-filter on *documents*; a 300k-row/yr all-sector
  table is a different cost shape. **Open to widening on request** — the
  source files remain available annually, so widening later loses nothing
  (unlike the tender keep-filter, these files are re-downloadable history).
- **D3 — Every year available, one backfill run.** The time series is the
  point. Backfill is idempotent on the unique keys; re-runs refresh, never
  duplicate.
- **D4 — Provenance**: each row carries `source_url` of the exact annual
  file. Publisher-linked provenance discipline unchanged.
- **D5 — Loud failure**: a year-file that fails to parse raises; a partial
  year never lands silently. The collector reports counts
  (read/inserted/refreshed/errors) in the run log like every other
  collector, and the workflow pings the healthcheck fail-path on failure.
- **D6 — Cadence**: annual, checked monthly by a light workflow step (the
  release lands ~March; a monthly check costs nothing and catches early or
  revised files). No continuous scraping.

## Estimated cost (collect only, never extract)

- Sunshine: ~30 year-files, ~50–80 MB/yr recent years all-sector; filtered
  to public-safety employers the stored subset is a few MB/yr. Storage
  <500 MB total worst case, likely far less. Runtime minutes per year-file.
- StatCan: <10 MB total, all years, all tables we want.
- LLM spend: **zero**, by design. No extraction path touches these tables.

## The lag, stated honestly

Sunshine publishes ~March for the prior calendar year: a pay event is
3–15 months old on arrival. FIR is 1–2 years behind. These are the
comparability layer, not the pulse; the pulse is Layer 2 (agendas,
arbitration awards, association announcements) and nothing here claims
otherwise. The product surface must date each figure by its disclosure
year, never present it as current-quarter compensation.

## Out of scope here

FIR (next PR, same pattern), CBIS agreements (needs a page-structure
probe), OPAAC awards (host confirmation outstanding — flagged separately as
a product risk), any member-facing surface, any extraction.

## Rollback

Drop the two tables. No other system reads them yet.
