# Roadmap — queued follow-ups

Durable record of agreed next builds, so nothing lives as folklore. Each item
lands as its own reviewed PR when its phase stabilizes.

## Grants collectors — BUILT 2026-07-11 (programs); awards design-first

**Design note (operator, 2026-07-11):** grant awards are leading indicators of
downstream procurement 6–18 months out. They are often sub-threshold and
invisible to tender monitoring — treat as **first-class**, not an afterthought.

Built (RUNBOOK Step 8 has the apply order):
- `src/grants_ontario.py` — the province's open funding directory (daily) +
  one-time closed-archive baseline (`--baseline`). Deadlines are event dates;
  CFR guideline rubrics captured into the program record; TPON-gated
  guidelines recorded via `documents.guidelines_gated`, never skipped.
- `src/grants_pscanada.py` — PS Canada's ~30 contribution/grant programs with
  detail-page terms as bodies (weekly).

Remaining, design-first (operator instruction — propose before building):
- **Federal grant awards** as `grant_award` docs from the open.canada.ca
  proactive-disclosure grants dataset, filtered to ps-sp / rcmp-grc /
  dnd-mdn / cbsa-asfc. Probe-verified access path and proposed ingest:
  `docs/grants-federal-awards-design.md`. Nothing ingests until approved.
- **Transfer Payment Ontario listings + ministry grant pages + newsroom grant
  announcements** as additional Ontario feeders, if the directory proves to
  lag them.

## Ontario Newsroom JSON-API adapter (small PR)

news.ontario.ca is a JS SPA with no RSS/Atom feed (probe 2026-07-11 +
operator page-source check). The feed entry is PARKED in `src/rss_collector.py`.
The unpark path is a small adapter for their JSON backend (still the official
publisher source), run through the same keyword/scope filters and content_hash
dedupe as the RSS feeds.

## Brief generation (future) — event-date discipline (editorial constraint)

**Binding constraint from editorial review (2026-07-11):** when the brief
generator is built, its selection query MUST filter and sort on the **event
date** — the source document's `published_on`, surfaced through the signal's
document join — never on `created_at`/collection date. The two dates diverge
by design: collectors backfill history (Peel's board archive spans 2017–2026),
so collection-date ordering would let backfilled history masquerade as news.
A 2019 board decision collected yesterday is context, not a headline.

**Date precision is explicit in the data** (`documents.date_precision`,
'day'|'month'): Peel's {item}-{MM}-{YY} filename convention dates a document
to its meeting month only, stored as day=01 with precision 'month'.
**Renderers MUST show month-precision dates as "Apr 2026", never as a full
date** — the review page's eventDate() does; the brief generator must.

Corollaries for the implementer:
- Signals whose document has `published_on IS NULL` need an explicit policy
  (exclude from dated briefs, or a separate "date unknown" section) — never
  silently substitute the collection date.
- The review page already leads each card with the event date (`tag.event`),
  so the reviewer sees what the brief reader would see.

## Parked / waiting

- **TPSB board minutes** — parked in `src/board_minutes.py`: tpsb.ca's WAF
  415s the collector site-wide despite an allow-all robots.txt. Unpark via
  board-office contact or WAF change.
- **Peel news-and-updates HTML posts** — page 1 is scanned for PDFs; collecting
  the paginated posts (×16) as documents is a follow-up.
- **Signal-level dedup** — blocker before the full title-backlog drain
  (RUNBOOK Step 6). Unblocked doc types (board_minutes) can extract now via
  `--doc-type`.
- **prospects ↔ contract_awards vendor join** — design note in
  `web/app/prospects/constants.ts` (normalized matching, org-resolver
  discipline).
