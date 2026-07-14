# Peel tenders collector: Design (bids&tenders, render-and-read)

Status: design-first proposal (2026-07-13), code not started. Awaiting operator
approval before building, per propose-then-approve.

## 1. Purpose and the gap it closes

We collect Peel's board minutes (commitment-stage INTENT) but not Peel's tenders
or awards. So for any Peel opportunity we can see intent but not whether it
reached in_market (tender open) or awarded, which means we cannot reconcile a
Peel prediction or check liveness. This collector closes the in_market and
awarded rungs for Peel, and (parameterized) for every other Ontario municipality
on the same platform. It is the priority forward-signal source: it feeds the
weekly brief (an open tender's close date is a future event -> Path B imminent),
settles reconciliation (award notices -> awarded rung), and answers liveness
(a tender's open/closed/awarded status).

## 2. Source and provenance (confirmed by probe)

  * Peel's official procurement page, `peelregion.ca/business/procurement/
    procurement-overview`, links directly to the portal.
  * Platform: **bids&tenders**. Portal: **`https://peelregion.bidsandtenders.ca/
    Module/Tenders/en`** (page title "Bids and Tenders - Peel Region").
  * PROVENANCE HOLDS: this is Peel's OWN Peel-branded subdomain that the Region
    posts to directly. bids&tenders is only the SaaS host; each municipality
    posts to its own portal. This is the publisher surface, NOT a cross-sourcing
    aggregator, so it passes the "publisher URLs only, no aggregators" rule. (A
    third-party site that re-scraped many portals would fail the rule; a
    per-municipality bids&tenders portal does not.)

## 3. Probe findings (the evidence base, 5 probes 2026-07-13)

  1. Portal + platform + provenance confirmed (above).
  2. `/robots.txt` is a soft-404 (returns the app HTML, not a real robots file),
     so there are no crawl directives. We apply a conservative polite delay by
     default.
  3. The listing is NOT a server-rendered HTML table and NOT inline data: the
     page is a fixed 41 KB client template whose only tender-ish strings are
     COLUMN HEADER definitions (BidStatusColHeader, BidClosingDateColHeader...).
     The `?status=Open|Closed|Awarded` query string has no effect (identical
     bytes); status is a client-side control.
  4. The row data loads from a CSRF-token-guarded call (the page carries 2
     antiforgery-token inputs). Direct/naive GET/POST to the obvious data paths
     returns a 280-byte "An error has occurred" page. A headless load fired NO
     bids&tenders data XHR (only analytics beacons).
  5. No tender rows rendered in any probe, most consistent with Peel having 0
     OPEN bids at probe time (empty grid: no rows, no fetch, no empty-state
     text). Not yet a proven extraction -> see the build-step-1 spike (section 9).

## 4. Access method: A (render-and-read) vs B (replay the JSON), DECIDED = A

Method B (scrape the guarded JSON endpoint with requests) is rejected on
evidence: the endpoint is CSRF-token-guarded, undocumented, and was not
characterizable across five probes. Even if captured, replaying it per
municipality means scraping a per-session token and posting the right internal
params, and it fails SILENTLY when bids&tenders changes the token scheme or
params: the collector would return empty and a municipality would look inactive
when the integration is actually broken. For a product whose value is a provable
hit-rate, a silent-empty failure is the worst failure mode.

Method A (drive Chromium via Playwright: load the portal, trigger the grid, read
the rendered rows) is heavier but robust and, crucially, fails LOUDLY (0 rows or
an exception), which is detectable. It does not depend on reverse-engineering an
internal endpoint. CHOSEN.

Cost, on probe evidence, at daily x dozens of `*.bidsandtenders.ca` municipalities:

  | | Method A (chosen) | Method B (rejected) |
  |---|---|---|
  | Per org/run | Chromium + ~2.1 MB / 56 req / ~5s load, plus install | ~1-2 small requests |
  | CI weight | playwright install (~1 min) + tens of min/day for dozens of orgs; parallelize with a matrix | negligible |
  | Fragility | UI/selector changes; VISIBLE breakage | token/param changes; SILENT breakage |
  | Verdict | heavier but honest-failing and maintainable | cheap but silently-breakable |

Cost mitigations for A at scale: run the browser once per org and read all
statuses in that session; a CI matrix parallelizes across municipalities; cache
the Chromium install; and (optional future) if a later spike cleanly captures the
guarded call WITH its token, add a fast-path that replays it and falls back to
render on any anomaly.

## 5. Extraction and mapping (existing spine, no schema change)

Per bid row read from the rendered grid (open + closed/awarded views):

  * Open bid -> `documents.doc_type = 'tender_notice'` -> in_market (grade 4).
    The bid's CLOSING date is a FUTURE `published_on` -> Path B imminent in the
    brief. `date_precision='day'`.
  * Awarded bid -> `documents.doc_type = 'award_notice'` -> awarded (grade 5) ->
    settles reconciliation and gives liveness. If the awarded view exposes the
    winning vendor + amount (bids&tenders usually does), capture them for org
    resolution and `amount_max_cad`.
  * Provenance URL = the bid's own detail page on Peel's portal (each row links
    to a Preview/OpenView URL with the bid GUID).
  * "None beats a wrong date": if a close/award date does not parse, store null,
    never a fabricated date. Month-only dates use `date_precision='month'`.

## 6. Politeness

No robots directives (soft-404), so we self-impose: identify our User-Agent, one
sequential session per org, a conservative delay between navigations, and low
volume (a municipality's live-bid count is modest). Never parallel-hammer a
single portal.

## 7. Idempotency and dedup

`content_hash` dedup (the existing collector pattern) keyed on the bid reference
number + status. A close-date or status change (open -> closed -> awarded) is a
real event: it inserts a fresh document (like a grant deadline change), so the
lifecycle open -> awarded is captured as a sequence, which is exactly what
reconciliation reads.

## 8. Scope

Keep EVERYTHING (operator decision): every Peel tender and award is collected,
and `defence_relevant` is TAGGED via the keyword filter, never used to drop. The
brief and taxonomy already down-weight off-scope items by grade/materiality;
nothing is silently discarded at collection.

## 9. Build plan (once approved)

  * Step 1, FEASIBILITY SPIKE (gate): a Playwright run against the awarded/closed
    view (guaranteed non-empty, unlike open bids today) that renders the grid,
    reads rows, and dumps the real DOM structure + selectors + a sample row.
    Confirms extraction is possible and pins the selectors BEFORE the collector
    is written. If Peel's open grid is simply empty today, this proves the
    mechanism on history.
  * Step 2: `src/tenders_bidsandtenders.py`, parameterized by `{org_key,
    subdomain}` (Peel first), reading open + awarded, mapping per section 5.
  * Step 3: sources seed (Peel portal), tests (parse + mapping + dedupe), wire
    into the daily workflow with the Chromium install, dry-run from a runner,
    then real run.
  * Step 4 (coverage multiplier): add more `*.bidsandtenders.ca` municipalities
    as config rows, no new code.

## 10. Cadence

Daily (operator decision): it is the priority forward-signal source; daily
catches new opens, close-date shifts, and awards promptly, matching the
CanadaBuys daily cadence.

## 11. Coverage multiplier

The collector is parameterized by `{org_key, subdomain}`, so one adapter covers
every Ontario municipality on bids&tenders. Peel is the first row; each
additional municipality is a config row, not new code. This is why solving Peel
solves a large Ontario municipal footprint.

## 12. Noted alternative for the awarded rung (cheaper, partial)

Peel Regional Council awards significant contracts by resolution, documented in
council agendas/minutes, which we ALREADY collect via `src/board_minutes.py`.
So the AWARDED rung for large Peel contracts may be partially reachable from the
existing board source (award resolutions), independent of the tender portal.
That does not replace the portal (it misses smaller awards and all the forward
tender-open signal), but it is a cheaper partial path for reconciliation-grade
award events and is worth extracting in parallel.

## 12a. Awarded rung: Method B ADOPTED for Awarded only (built, validated 2026-07-14)

The Open rung stays Method A (section 4). The AWARDED rung, by contrast, is now
built on Method B, because the evidence for Awarded is the opposite of Open:

- the JS tab-click never switches the grid to Awarded (it returns the Open rows
  relabelled), so render-and-read cannot get Awarded at all;
- a spike proved the page's own guarded call, replayed as
  `POST .../Tender/Search/<moduleGUID>?status=Awarded`, returns HTTP 200 JSON of
  genuinely awarded bids, a set disjoint from Open, each `Title` carrying the
  same reference format (`2017-695N - ...`) that hard-keys to the tender.

So the collector captures that guarded call as it auto-fires on load (its URL,
CSRF token body and ajax header) and replays it for `?status=Awarded`, paging
the awarded history into `award_notice` documents keyed on the bid reference.

What the endpoint gives and does NOT give (honesty for the "None beats a wrong
answer" rule): reference, title, status and closing date, YES; winning vendor,
award value and a distinct award date, NO (those live on a per-bid results page
and are a deferred enrichment). `published_on` is the closing date, the only
timestamp the endpoint exposes, labelled as such, not invented as an award date.
The reference number is all the awarded rung needs to reconcile against the
tender it settles.

Live dry-run 2026-07-14: Open 25 rows (Method A) + **Awarded 2762 rows**
(Method B) parsed into `award_notice` payloads, references and closing dates
correct, spanning 2017 through the prior day, 0 errors. Loud-failure guard: an
empty awarded set raises (a live Peel portal has years of awards).

This is the reconciling awarded rung; the section-12 board-minutes path remains
the complementary source for boards whose awards are not on a bids&tenders
portal (e.g. TPSB).

## 13. Open decisions for the operator

  1. Approve Method A (render-and-read) and the feasibility-spike-first build
     plan.
  2. Approve daily cadence and keep-all + defence_relevant tagging (recorded
     above per operator instruction; restated for the record).
  3. Pursue the section-12 council-award-resolution path in parallel, or portal
     only for now?
