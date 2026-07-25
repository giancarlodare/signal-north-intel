# Ontario Hansard + committee documents collector: design

Status: PROPOSED (design-first, sprint front 3). Probe evidence from the
read-only CI probe 2026-07-25 (job 89676754793).

## Why

Legislative debate and committee estimates are upstream INTENT signal: a
minister's statement, an estimates exchange, or a committee recommendation
often precedes the budget line and the tender by months. The target is
narrow and high-value: Solicitor General / community-safety, and
infrastructure / capital statements, not the whole Hansard firehose.

## Probe evidence the design rests on

ola.org (Legislative Assembly of Ontario) is **server-side HTML, plainly
requests-collectable** (no JS shell, no render barrier):

- `/en/legislative-business/house-documents/parliament-NN/session-M/` returns
  200 (146 KB, 255 links) and lists per-DAY debate pages by date, e.g.
  `.../parliament-43/session-1/2024-12-12/`. The daily transcript is an HTML
  page (0 PDF links at the index; the text is in the page, ideal for
  extraction).
- `/en/legislative-business/committees/documents` is the committee-documents
  index (estimates, reports).
- A Hansard search and a House Hansard index exist as additional entry points.

Robots respected throughout; the shared PoliteFetcher fetched every page.

## Collector (src/hansard.py, requests-based on the shared PoliteFetcher)

- **Discovery, publisher-indexed:** from the current parliament/session page,
  enumerate the per-day debate URLs (dated `YYYY-MM-DD`), and from the
  committee-documents index enumerate committee document URLs. Both are the
  Assembly's own listings.
- **Per-run NEW-item cap** (25, board-minutes style): content_hash(url,
  doc_type) checked first, so the multi-session archive drains over days and
  known transcripts skip without a fetch.
- **Body + date:** fetch each transcript/committee-doc page, html_to_text the
  body, published_on = the sitting date (day precision; the date is in the
  URL and the page, so >= 90% parse is easy). date_precision never null
  (coalesce to 'day', per the fix in #103).
- **SCOPE FILTER, not keep-all:** unlike a police board (in-scope by
  construction), a full day's Hansard is mostly off-topic. Apply a scope
  filter BEFORE storing: keep a document only if it matches
  SolGen/community-safety or infrastructure/capital scope terms (reuse the
  rss_collector `scope_terms` pattern), then the keywords.txt relevance
  filter tags defence_relevant on top. This keeps the corpus (and the
  extraction budget) focused on procurement-relevant legislative signal.
- **LOUD FAILURE:** the current session page yielding zero dated debate URLs
  raises (the Assembly always has a current session).

## Spine + extraction mapping

- **doc_type:** propose a new `legislative_debate` doc_type (enum migration,
  additive) rather than overloading news_release; it reads differently for
  the reader-facing date-type label ("Legislative statement" vs "Contract
  awarded"). Add it to the daily forward-extraction doc-types list so
  Hansard signals populate the brief on the same pass.
- **Signal types it feeds** (already in the taxonomy): budget_allocation,
  capital_plan_item, mandate_direction, policy_announcement,
  legislative_change, political_pressure. The extractor lifts these from the
  prose the same way it lifts board_decision from board minutes; no extractor
  code change beyond the doc-type list.
- **Buyer/org:** the province (Ministry of the Solicitor General, etc.),
  resolved from the prose; the relevant ministries are already in ORG_SEED.

## Cost note (the operator's standing extraction-budget concern)

Hansard transcripts are LONG (full-day debates). The scope filter is what
keeps this affordable: only scope-matching documents are stored and
extracted, so the added Opus volume is a handful of relevant
statements/estimates per sitting, not entire debate days. Quantify the
projected monthly extraction number in the build PR's validation dry-run
before enabling, same discipline as the board-minutes budget.

## Build shape on approval

Probe-validate-PR cycle: build `src/hansard.py` + the `legislative_debate`
enum migration + a URL-guarded sources row + scope terms, run a CI validation
dry-run (>= 90% date parse, scope-filter keeps a sane fraction, nonzero
bodies, projected extraction volume), bring the table, single-go gate before
enabling. No enablement without the operator's go.
