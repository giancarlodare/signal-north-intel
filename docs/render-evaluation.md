# Render-capable collection: evaluation and recommendation

Status: RECOMMENDATION for operator approval (sprint front 6, 2026-07-25).
Decides how Signal North collects the JS-rendered sources parked across the
Big-12 boards work and the Biddingo platform.

## The parked render targets (what this unlocks)

| Target | Parked because | Value |
|---|---|---|
| eScribe boards: Niagara, Ottawa, Hamilton, London | documents live on `*.escribemeetings.com` (JS shell, links absent from server HTML) | 4 police boards, full agenda/minutes history |
| Biddingo: DRPS `/m/drps` | client-rendered `/m/` buyer pages (server HTML is a JS shell) | a police service's full public bid history WITH awards (highest-value single target) |
| Biddingo: Windsor `/m/windsor` | same | backstop; Windsor's open-data mirror already covers it, so this is redundancy, not new coverage |

All three are publisher-linked (provenance already settled: eScribe pages are
linked from each board's own site; DRPS `/m/drps` confirmed public by operator
browser). The only barrier is rendering.

## Candidates

| Option | What it is | Data residency | Cost | CI fit | Maintenance |
|---|---|---|---|---|---|
| **Playwright-in-CI** (incumbent) | headless Chromium in the GitHub Actions runner, already used by `src/tenders_bidsandtenders.py` | stays in our runner + Supabase (Canadian) | $0 marginal (runner minutes only) | native: the stack, pinned browser, and launch pattern already exist | one more adapter per platform; we own the selectors |
| **Firecrawl** (SaaS) | hosted render-and-extract API | pages and extracted content transit a third-party US service | per-page/subscription fee | an HTTP call, but adds an external dependency and an API key | low code, but selector/output drift is theirs, not ours |
| **Self-hosted alt (Selenium/Splash)** | another headless stack we run | in-runner | $0 marginal | net-new stack alongside Playwright | duplicates what Playwright already gives us |

## Recommendation: extend Playwright-in-CI. Do not adopt Firecrawl.

Reasoning, against this project's standing disciplines:

1. **It is already proven here.** `tenders_bidsandtenders.py` renders a
   CSRF-guarded fuelux grid with a real-UA Chromium in CI and has run in
   production for weeks. The marginal cost of an eScribe adapter and a
   Biddingo adapter on the same stack is a parser, not a platform.
2. **Data residency and provenance.** Firecrawl routes publisher pages and
   their extracted text through a third-party US service. The project holds
   Canadian data residency end to end and publisher-linked provenance as hard
   rules; sending government meeting documents through an external renderer
   weakens both for no coverage we cannot get in-runner.
3. **Cost and control.** Playwright is $0 marginal (runner minutes we already
   pay for). We own the selectors and the failure modes, so the loud-failure
   discipline (raise on empty, never record silence) extends cleanly; a SaaS
   renderer's silent-empty is harder to guard.
4. **Firecrawl's edge does not apply.** Its value is fast broad crawling of
   arbitrary sites. Our targets are a handful of known, structured platforms
   (eScribe, Biddingo) where a targeted adapter beats a generic renderer on
   fidelity.

**Cost note the operator flagged earlier:** render adapters do not change the
Opus extraction budget (extraction reads `documents.content` regardless of how
it was collected). They add GitHub Actions runner minutes only. eScribe and
Biddingo are low-volume (per-meeting, per-bid), so the added minutes are small
and drain-capped like the other collectors.

## Build shape on approval (design-first, one adapter at a time)

- **eScribe adapter** first (unlocks 4 boards, one build): a shared
  `src/board_minutes_escribe.py` that renders each `*.escribemeetings.com`
  meeting list, reads the agenda/minutes document links the JS injects, and
  hands each PDF/HTML to the EXISTING board-minutes body + date + dedup path
  (no new spine). Per-board config rows, per-format tests, CI validation
  dry-runs against the board-minutes bars (>= 90% date parse, nonzero bodies)
  before any board enables.
- **Biddingo adapter** second (unlocks DRPS): render `/m/drps`, read the bid
  rows the JS injects (references like `DRPS-2026-002`, Awarded/Closed
  statuses), map to `tender_notice` / `award_notice` on the existing tender
  spine keyed on the bid reference. Validation against the tier-1 tender bars.
  Windsor `/m/windsor` stays parked as redundant with the live open-data feed.

Each adapter is its own probe-validate-PR cycle with the standard single-go
gate; nothing enables without the operator's go after a validation table.
