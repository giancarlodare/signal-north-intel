# Operator protocols

Standing report commands the operator issues in chat; keep these current.

## Digest protocol (operator 2026-08-02, effective immediately)

The operator reads TWO digests a day, morning and evening (Eastern), and is
NOT watching in between. Binding rules:

1. **No reports as they land.** Everything batches into the two digests.
   One message each, structured exactly: what shipped / what needs a
   decision and why / what's blocked. Nothing else.
2. **DECISION vs FYI.** Anything needing the operator is labelled DECISION
   at the top. Everything else goes under FYI and gets no reply. Probe
   results, census output, bucket tables and reachability reports are FYI
   unless a choice hangs on them.
3. **Answer your own questions from the codebase first.** Grep before
   asking. (The costed example: recommending a mail provider without
   checking that Resend was already wired and domain-verified.) Ask only
   what genuinely needs the operator's judgment.
4. **BLOCKING** in the subject line pulls an item forward; otherwise it
   waits for the next window.
5. **"Needs you tomorrow" look-ahead** (operator addition, same day): each
   digest carries a short section naming every item that will need the
   operator the NEXT day -- the item, roughly when it will be ready, and
   what it unblocks -- so evenings can be cleared in advance rather than
   discovering at 9pm that the scorer sat idle since noon. Dependency
   chains are announced a day ahead, never just BLOCKING-flagged at the
   wall.

## Time zone

ALL times shown to the operator are Eastern (America/Toronto), never UTC.
The operator's label for this is EST; use the correct Eastern wall-clock
time year-round (EDT offset in summer), converting from UTC internally.
Cron schedules stay UTC in config, but are always REPORTED as Eastern.

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
- COST GATE (operator 2026-07-27): before ANY large historical backfill
  or full-source drain runs, bring the operator the projected cost first
  (doc count x measured per-doc rate, stated as an envelope like the
  Toronto $63) and get the spike approved BEFORE dispatch. A drain
  cadence never auto-extends past its approved envelope; new source
  histories entering drain scope pause for approval, never spend
  silently. Steady-state scheduled LLM spend is only the capped daily
  forward pass plus the small weekly discovery and monthly calibration
  jobs.

## Autonomy: safe class vs gated class

Operator directive 2026-08-01. The diagnosis behind it: the bottleneck was
never capability or token budget, it was wall-clock latency on human
approval. A live_surface fix sat pushed for eleven hours while collection
died a third night; daily-tenders never ran for seventeen nights behind a
one-line cron guard. We had built real guardrails (envelope guard,
loud-failure raises, validation bars, a green suite) and then kept a human
gate beside every one of them, paying for each guardrail twice. **The point
of a guardrail is that it buys freedom.**

### SAFE CLASS: merge on green CI, no approval, log it after

* Bug fixes to existing collectors and extractors **where tests cover the fix**.
* Workflow, cron, and CI configuration.
* Dependency bumps.
* Test additions.
* Documentation.
* Any change touching only `src/` with no schema change and no
  member-facing surface.

Conditions, all three required:
1. Full suite green.
2. The change introduces **no new silently-swallowed failure path**.
3. It is logged in `docs/decision-log.md`.

**If it is unclear whether something is in the safe class, it is not. Ask.**

### GATED CLASS: human gate, unchanged

Nothing in the autonomy grant relaxes any of these.

* Migrations and schema changes.
* Anything member-facing or on the marketing site.
* Anything that spends money.
* Anything changing a public claim, a price, or a coverage statement.
* New data sources with robots or coverage implications.
* Anything crossing the client-facing gate.

### Ceremony matches blast radius

Probe → design doc → operator approval → build stays for the gated class.
It is overhead on a collector bug fix. Use judgment, and **default to the
heavier process whenever the blast radius is unclear.**

### Silent failure is the enemy, not failure

Every automated system reports its own failure, loudly, without a human
reading a log. If something breaks, the operator knows within minutes, not
four nights. A monitor that reports success it has not verified is the same
defect class as a swallowed error, and both are treated as outages.

## State lives in the repo, not in chat

Decisions made only in conversation drift from what the repo actually does.

* `docs/decision-log.md` is the versioned record of what was decided and
  why. Keep it current; it is the memory that survives a context reset.
* Overnight and status reports become GitHub issues, not long prose.
* The morning report is SHORT and links to durable artifacts rather than
  restating them.
