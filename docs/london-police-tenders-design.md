# London Police Service bids page: collector design (Phase 1 wrap)

Status: step-1 probe COMPLETE 2026-07-28 (run 30321078029) and it
simplified everything: the Umbraco page is a landing page whose
procurement link goes to **londonpolice.bidsandtenders.ca** (a standard
bids&tenders tenant, like York Regional Police already enabled). No new
collector is needed; step 2 collapses into the standard tenant validation
dry-run under the existing collector, then operator go + seed paste to
enable. Provenance chain: londonpolice.ca (service's own domain, robots
permitted) names the tenant, the same publisher-links-portal pattern the
tier-2/tier-3 enablements used. The original plain-requests design below
is retained for the record; it is superseded by the tenant route.

Program: coverage program Phase 1 (operator approved 2026-07-28 under the
$500 cap). Design-first per the standing discipline.

## Why this source

`londonpolice.ca/about/bids-and-tenders/` is a police-service-DIRECT
procurement channel: the service posts its own bids rather than routing
through the City of London portal. Police-service-direct feeds are the
highest-value class for our niche, and this is the first one found that is
collectable without a render dependency (DRPS sits behind Biddingo).

## What the 2026-07-27 CI probe established (run on the GitHub runner)

* The page returns server-rendered HTML: Umbraco CMS, ~71KB, no JS shell.
  Plain requests collect it; no Playwright needed.
* `robots.txt` permits the path. Only CMS internals are disallowed
  (`/bin/`, `/config/`, `/install/`, `/umbraco/`, `/views/`), and a
  sitemap exists at `/sitemap-xml/`.
* Provenance is publisher-linked by construction: the service's own domain.
* Separate finding, unchanged by this design: the London Police Service
  BOARD remains PARKED for board minutes (no server-side meeting documents;
  calendar.londonpolice.ca exposes events only).

Not yet established (step 1 below): the listing markup, the field set per
bid (title, reference, close date, documents), whether awarded history is
exposed, and typical volume.

## Build plan (three steps, each gated)

1. **Structure probe** (CI, read-only, no DB writes): fetch the page and
   any per-bid detail pages, report the markup shape, extractable fields,
   open-vs-closed sections, and volume. Cost: nil.
2. **Collector build** `src/tenders_londonpolice.py`, only if step 1 shows
   parseable structure: plain-requests fetch, 2s politeness, keep-all with
   tags (relevance filter tags defence_relevant, never drops: a police
   service's own feed is in-vertical by definition), content_hash dedupe,
   loud failure on zero rows, URL-keyed source seed row, ORG_SEED entry
   resolving to London Police Service. Dates only as published, with
   date_precision honored; no fabricated dates.
3. **CI validation dry-run against the standing bars** (non-zero rows,
   reference and date parse rates, provenance link check), then operator
   go before the source row is pasted and the collector joins daily-collect.

## Self-maintenance (program condition)

On enablement the collector joins the daily-collect workflow like every
other enabled source; forward extraction rides the capped daily pass. No
historical drain is proposed for this source. If step 1 surfaces an awarded
archive worth draining, that comes back separately with a measured envelope
per the cost gate; it never joins a drain silently.

## Failure modes and outs

* Listing turns out to be an embedded third-party widget: park with the
  probe evidence recorded, as with Niagara Falls and Sarnia.
* Fields too sparse to meet the bars (no close dates, say): hold, record
  the diagnosis, and revisit; never enable-and-hope.
