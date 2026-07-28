# Ontario Newsroom collector design (plain requests, no render)

Status: DESIGN for operator review. Build starts on operator go; nothing
enables without the validation dry-run table and a second go. Folded out of
the grants-near-zero investigation (item 6 of the coverage program,
operator 2026-07-28): the newsroom is where Ontario grants get ANNOUNCED,
so this is both the provincial grant-capture channel and the cross-check on
the grants pipeline.

## Evidence (probe, 2026-07-28)

The news.ontario.ca site is a JS shell to plain requests, but the endpoint
hunt (scripts/probe_newsroom_grants.py; recorded in
docs/render-evaluation.md addendum) found the structured API behind it:

    api.news.ontario.ca/api/v1/releases   (HTTP 200, JSON)

Releases carry ids, dates, and ministries. Render machinery is NOT needed;
the standing lesson (hunt the API before renting a browser) is applied.

## Design

* **Module**: `src/newsroom_ontario.py`, plain requests through the polite
  pattern (SignalNorthIntel/1.0 UA, robots re-checked per run, 2s delay).
* **Step 0 of the build (CI, before any code lands)**: one probe run
  re-verifying robots for api.news.ontario.ca + news.ontario.ca and
  printing one full release object VERBATIM, so field mapping is built on
  the real shape, not memory of it. Pagination and ministry-filter
  parameters confirmed in the same run.
* **Scope gate**: releases pass the shared public-safety relevance filter
  (src/public_safety.py; the regional-govt feed gate) before insert --
  ministry prefilter (Solicitor General, Attorney General, Emergency
  Preparedness, plus infrastructure/health where the filter passes) is an
  efficiency hint, never the keep decision. Blotter-class noise has no
  equivalent here; the risk is province-wide non-safety announcements, and
  the relevance filter is the tested gate for exactly that.
* **Mapping**: one release -> documents row, doc_type `news_release`,
  published_on from the release date (never fabricated), URL = the PUBLIC
  news.ontario.ca release page (publisher-linked provenance; the API URL is
  transport, not provenance), content = release body text (capped as
  usual), content_hash on URL + doc_type. Grant/funding language then rides
  the normal extraction pass (funding_program / funding_announcement
  signals), which is the grants-near-zero payoff.
* **Cadence**: daily-collect step, forward window only (recent releases
  each run). Historical backfill is a SEPARATE cost-gated decision: the
  archive is large, extraction is the cost driver, and per the standing
  cost gate a projected envelope comes to the operator BEFORE any drain.
* **Loud failure**: zero releases from the API raises (the newsroom is
  never legitimately empty); a schema change that drops a required field
  raises rather than inserting partial rows.

## Validation bars (before enablement)

Dry-run table delivered to the operator: releases read, relevance keep
rate, ministry distribution of keeps, date parse (must be 100%), sample of
kept titles incl. at least one grant/funding announcement, and the
projected daily extraction load (expected: a handful of docs/day into the
capped forward pass).

## Federal side (same investigation, already resolved)

PS Canada newsroom is rich in grant announcements and already collected;
DND slug fixed; RCMP migrated to rcmp.ca feeds with the scope gate. No new
federal build needed.
