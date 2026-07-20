# Big 12 tier 1 design: bids&tenders coverage expansion

Status: DESIGN for approval, 2026-07-20. Code follows in a build PR after
approval. Scope approved by the operator from the coverage survey: York
Region, London, Durham Region, plus the police tenants conditional on
provenance. Tier 2 and the Halton/Niagara re-probe follow after tier 1 runs
clean for a few days.

## Provenance verdicts (crawled live from CI, 2026-07-20)

The rule is publisher-linked, no exceptions: a portal is enabled only when
the organization's own procurement page links its bids&tenders tenant.

| Tenant | Official page linking it | Verdict |
|---|---|---|
| york.bidsandtenders.ca | york.ca/business/doing-business-york-region/current-bids-and-tenders | **PASS** |
| london.bidsandtenders.ca | london.ca homepage + london.ca/business-development/procurement-supply | **PASS** |
| durham.bidsandtenders.ca | durham.ca homepage + durham.ca/doing-business/ | **PASS** |
| yrp.bidsandtenders.ca | yrp.ca/reports-and-services/business-services/bids-and-tenders | **PASS** |
| drps.bidsandtenders.ca | drps.ca/about-us/procurement-services/ fetched clean; tenant NOT linked one hop from the homepage | **HELD** |

**Tier 1 enabled set: York Region, London, Durham Region, YRP (four
portals).** DRPS is designed here but stays disabled until its provenance
passes: the build includes a deeper crawl of drps.ca (the tenant link may sit
on a subpage below procurement-services); if that still finds no link, DRPS
waits, however strong the branded tenant looks. The config row ships
commented out with the verdict recorded beside it.

## Config rows (the coverage multiplier working as designed)

`MUNICIPALITIES` in src/tenders_bidsandtenders.py gains, in this order:

| org_key | subdomain | name | buyer_name written |
|---|---|---|---|
| york | york | York Region | York Region |
| london | london | City of London | City of London |
| durham | durham | Region of Durham | Region of Durham |
| yrp | yrp | York Regional Police | York Regional Police |
| (drps | drps | Durham Regional Police Service | held pending provenance) |

Two small additions ride along:

- **documents.buyer_name** (column added by the CanadaBuys enrichment) is now
  set from the config row for every bids&tenders document, Peel included:
  the buyer is structural on these portals, so it should be stored
  deterministically rather than left for extraction to infer.
- **Canonical org seeding**: resolve_orgs.ORG_SEED gains York Region, City
  of London, Region of Durham, and York Regional Police (org_type
  municipality / police_service, with the obvious aliases), so signals from
  these portals resolve to canonical buyers instead of degrading brief items
  with "The buyer".

## Sources seed migration

One migration, four `sources` rows (five with DRPS commented), URL-keyed
insert guards identical to the Peel seed
(2026-07-13_peel_tenders_source_seed.sql): idempotent, re-runnable, keyed on
`https://{subdomain}.bidsandtenders.ca/Module/Tenders/en`.

## Per-portal validation before enabling (reference-format check)

The Peel spike tuned two parsers the grid read depends on: `BID_REF` (the
`2026-104P` reference shape) and `parse_event_date` (the `Wed Jul 15, 2026`
closing-date shape). The survey's small row counts on some tenants are
either low volume or a different reference format; the build phase settles
this per portal, before any daily enablement:

1. A one-off CI dry-run per portal (`--dry-run` already renders and reports
   without writing) with a per-portal summary line: rows read, rows with a
   parsed reference, rows with a parsed date, awarded rows returned.
2. **Acceptance bar**: >= 90% of Open rows parse both a reference and a
   date, and the awarded replay returns nonzero rows. A portal below the bar
   gets its format divergence diagnosed and `BID_REF`/date parsing extended
   (per-portal pattern in the config row if needed) before it is enabled.
   `parse_bid_name` already refuses to fabricate: an unmatched reference
   stores ref=None, and the validation counts exactly those.
3. The LOUD-FAILURE guard stays the day-one backstop, exactly as designed:
   an empty Open grid or a dead awarded replay raises. A format mismatch
   that slipped past validation surfaces as a red run, never silent
   thin data.

## Schedule: sequential renders + per-portal failure isolation

Renders never stack by construction: `collect()` drives ONE Chromium browser
and visits portals sequentially (a fresh context per portal, ~2 minutes
each). Five portals means roughly 10 minutes inside the existing daily
run (6:47am ET), well within the window; no cron change and no parallel
Playwright.

The change the design does make: today one portal's failure raises
immediately and kills the whole run, so a WAF hiccup at portal two would
blind portals three through five. The build wraps each portal in its own
try/except: failures are recorded with the portal name, the loop continues,
and the run RAISES AT THE END if any portal failed. Loud (the day still goes
red, the Actions email still fires, the log names the failing portal) but
never coverage-destroying.

## Unchanged invariants

- **Keep-all + defence_relevant tagging**: `build_payload` calls `evaluate`
  for the tag only; nothing is dropped. Unchanged for all tenants.
- Reference numbers to `documents.reference_number` (procurement spine hard
  key), open bids as tender_notice with the CLOSE date as the event date,
  awarded bids as award_notice, real-UA guard: all unchanged, per tenant.
- Canadian data residency and provenance links (bid preview URLs on the
  portal itself): unchanged.

## Rollout

1. Build PR: config rows (DRPS commented), buyer_name write, ORG_SEED
   additions, sources migration, per-portal isolation in collect(), tests.
2. Apply the migration; run the per-portal validation dry-runs from CI; fix
   any format divergence; enable the four passing portals.
3. Watch the daily run for a few days (the runbook's alert guide applies;
   a red day names the failing portal).
4. Then: tier 2 (branded-tenant cities, each with its own official-link
   confirmation first), the Halton/Niagara re-probe on their real
   subdomains, and the DRPS provenance re-check.

## Tests (build PR)

- Config-row shape (org_key/subdomain unique, buyer_name present).
- build_payload writes buyer_name from the config row.
- Per-portal isolation: a raising portal does not stop later portals, and
  the run still fails at the end (loud).
- ORG_SEED additions resolve the four buyer names.
- Existing Peel fixtures unchanged (regression).
