# Operator protocols

Standing report commands the operator issues in chat; keep these current.

## "overnight status"

When the operator says "overnight status", deliver a compact report built
from the latest GitHub Actions runs (via the API or job logs), covering:

1. **Last night's runs**: daily-collect (CanadaBuys, board minutes,
   Windsor open-data, MERX-Ottawa, newsroom RSS, Ontario grants,
   extraction step) and daily-tenders (bids&tenders portals), plus any
   extract-backfill runs. Green/red per run.
2. **Counts**: per collector from the run logs (read / inserted /
   duplicates / refreshed / errors; the VALIDATION lines where present).
3. **Anything red**: failed runs or steps, loud-failure raises, WAF or
   robots blocks, healthcheck misses. Name the collector and the cause;
   never summarize a red as fine.
4. **Backfill progress**: what the per-run caps drained overnight (board
   minutes backlog, MERX per-tab new items, bids&tenders awarded history)
   and a rough remaining estimate where the logs allow one.

Compact means one screen: a short table or tight list per section, no
narration. Report honestly; a partial or failed night is stated as such.

## Context

- Sprint plan and cadence: docs/august-sprint-plan.md (daily check-in
  fires each morning via a scheduled routine).
- Standing disciplines: probe-first, validation bars before enablement,
  loud failure, publisher-linked provenance, propose-then-approve; no em
  dashes in generated copy; never fabricate dates.
