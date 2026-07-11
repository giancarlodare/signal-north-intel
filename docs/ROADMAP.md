# Roadmap — queued follow-ups

Durable record of agreed next builds, so nothing lives as folklore. Each item
lands as its own reviewed PR when its phase stabilizes.

## Next collector: grants (Ontario first, federal second)

**Design note (operator, 2026-07-11):** grant awards are leading indicators of
downstream procurement 6–18 months out. They are often sub-threshold and
invisible to tender monitoring — treat as **first-class**, not an afterthought.
The PS Canada newsroom feed already catching grant announcements (crime
prevention Calgary/Edmundston, Canada Community Security Program) confirms the
signal is there.

- **Phase 1 — Ontario:** Transfer Payment Ontario public listings, ministry
  grant program pages, newsroom grant announcements.
- **Phase 2 — federal:** Public Safety Canada contribution programs.
- **Two new doc types:** `grant_program` (a program exists / opens) and
  `grant_award` (money moved to a recipient). Both need DB enum additions
  (additive migration) before the collector lands.
- Same standards as every collector: publisher URLs, content_hash dedupe,
  polite fetching, hardcoded source configuration, --dry-run verification.

## Ontario Newsroom JSON-API adapter (small PR)

news.ontario.ca is a JS SPA with no RSS/Atom feed (probe 2026-07-11 +
operator page-source check). The feed entry is PARKED in `src/rss_collector.py`.
The unpark path is a small adapter for their JSON backend (still the official
publisher source), run through the same keyword/scope filters and content_hash
dedupe as the RSS feeds.

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
