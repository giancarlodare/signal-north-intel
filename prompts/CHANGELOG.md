# Prompt Library Changelog

All notable changes to Signal North prompts. Each released version is
immutable; changes ship as a new version with an entry here. The version is
stamped onto produced artifacts as `<name>@v<version>` (e.g. `extraction@v1`).

## extraction

### v3 - 2026-07-28 - BUILT, NOT ACTIVE (no-ship verdict; v2 stands)
- Prompt-cache restructure: static instructions consolidated into a system
  block (above Opus 4.8's 1024-token cache floor, `cache_control` stamped),
  per-doc fields alone in the user message, split on the `=====USER=====`
  marker. The file exists in the library but ACTIVE_VERSIONS stays at 2:
  the operator-gated v2-vs-v3 comparison (run 30358817521, 16 docs) showed
  a real quality slip - 44 -> 29 signals, one rich news release collapsed
  8 -> 0, amount drift on a TPS contract-award signal - and the operator's
  bar (cost savings never justify degrading extraction) refused it.
  Cost finding for the record: caching mechanics worked, -46%/doc on
  title-only docs, -29%/doc rich.
- Documented retry path (low priority, operator 2026-07-28): a v4 that
  moves the v2 text VERBATIM into the cached system block - no embedded
  schema, no added task line - validated against a v2-vs-v2 rerun first to
  establish the sampling-noise floor before judging the restructure.


### v2 - 2026-07-20
- One-line confidence clarification from the first calibration audit
  (issue #85, adjudicated): grade-5 confidence agreement was 50%, with every
  flip on award_notice documents wobbling between confirmed/probable/
  speculative. v2 states that an award notice reports an event that has
  already happened and scores as confirmed unless the text itself hedges
  ("intent to award", "pending", "proposed").
- No other changes; v1 remains immutable. New signals stamp
  `extracted_by = "extraction@v2"`, so next month's audit shows per-version
  whether grade-5 confidence recovers.


### v1 — 2026-07-09
- Initial versioned extraction prompt, ported from the PR #6 inline prompt
  (`signal_extractor.EXTRACTION_PROMPT`) and moved into the prompt library.
- Behavioural changes vs. the ported original:
  - Always returns `organization_name` (raw, as written in the document) even
    when unsure, so unresolved orgs can be resolved later instead of dropped.
  - Explicitly told the input may be title-only, and to mark confidence
    accordingly (a headline alone rarely supports `confirmed`).
- **Pending before first production run:** the `signal_type` and
  `category_slug` value lists embedded in the prompt must be verified against
  the live DB enums / `categories.slug` values. Ported as-is from PR #6; that
  code inserted successfully, so they are likely valid, but confirm before
  extracting at scale.

## discovery@v1 — 2026-07-11
- Initial discovery triage prompt (weekly propose-then-approve job; see
  docs/discovery-engine-design.md). Surfaces candidate organizations, senior
  appointments, and company-Canada-intent from batches of rich-bodied
  documents. Text-stated facts only, exact names, mandatory [doc:UUID]
  evidence per candidate — a candidate without evidence must be omitted.
  Precision over recall: everything it surfaces is human-reviewed, nothing it
  proposes is acted on automatically.
