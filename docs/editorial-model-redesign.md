# Editorial Model Redesign: Design (score-as-trust, brief-as-work)

Status: approved in principle (2026-07-13), phased build pending review of this doc.
Supersedes the manual signal-approval queue as the operating model.

## 1. Purpose

The manual review queue is the wrong operating model. Approving or rejecting raw
signals asks the operator to judge "is this extraction accurate," which is not a
judgment the operator should be making and does not scale (hundreds of items a
week). The weekly human effort should be editorial, not QA.

This redesign moves the trust boundary. The machine's own scores (confidence,
evidence_grade, materiality) become the trust layer; every signal enters the
corpus live on insert with no human approval gate. Human effort concentrates on
three deliberate acts:

  1. Reviewing and editing an auto-generated draft Weekly Signal (the main
     weekly job): the operator edits a draft brief, never a raw queue.
  2. Authoring predictions (deliberate, rare).
  3. Approving discovery proposals (rare).

Non-goals: this does not change collection, the taxonomy, the prediction ledger,
or the discovery engine. It changes what happens to a signal AFTER extraction and
what the operator touches each week.

## 2. The model shift

Before:

    collect -> extract -> signal (reviewed=false) -> HUMAN approve/reject
      -> approved signals feed proposer -> procurements -> HUMAN confirm
      -> HUMAN author prediction -> reconcile

After:

    collect -> extract -> signal (LIVE, scored) -> corpus
      -> AR1 auto-suppress obvious noise (machine)
      -> proposer clusters scored, non-suppressed signals -> procurement candidates
      -> weekly draft brief built from fresh/high-materiality/strong-grade signals
      -> HUMAN edits the brief (weekly)
      -> HUMAN authors prediction from a candidate (confirmation folded in; merge preserved)
      -> reconcile

The scores stop being metadata and become the primary filter everywhere. The
only machine write to review state is AR1 suppression of noise.

## 3. Hard rules preserved (non-negotiable)

  * Provenance absolute: publisher URLs only, no aggregators. Unchanged.
  * "None beats a wrong date": undated stays undated; date precision honored.
  * No em dashes in any generated copy (including the brief).
  * The prediction remains the one hard human trust gate: nothing becomes a
    published claim without a person authoring it with frozen evidence, a
    DB-computed hash, and an external timestamp. This is deliberate (see 8).
  * The wall between triage and the ledger holds: suppression touches only
    signal review state, never a prediction or procurement.
  * Canadian data residency preserved.

## 4. Data model

### 4.1 Retire the approval gate

`signals.reviewed`, `review_note`, `reviewed_by` stop meaning "cleared for use."
A signal is corpus-live the moment it is inserted. These columns are NOT dropped
(they hold historical review provenance and the AR1/human rejection history);
they simply stop gating anything. New inserts leave them at their defaults.

### 4.2 One editorial override

Add a single flag, the only lever over corpus membership:

    alter table signals add column if not exists suppressed boolean not null default false;
    alter table signals add column if not exists suppressed_reason text;   -- 'AR1' | free text
    alter table signals add column if not exists suppressed_by text;       -- 'triage@v1' | 'human'

`suppressed=false` is the default: everything is live and visible. Suppression is
the rare, reversible, fully-audited "hide a clearly-wrong or noise signal"
action. Nothing is ever deleted. A suppressed signal stays in the database and
in provenance; it is only excluded from the corpus browser, the proposer, and
the brief.

### 4.3 Backfill existing review state

One-time, inside the Phase 1 migration:

  * `suppressed=true, suppressed_reason='rejected (migrated)', suppressed_by=<reviewed_by>`
    for every signal whose `review_note` currently starts with 'rejected'
    (human rejects and AR1 auto-rejects alike) so existing exclusions are
    preserved as suppressions.
  * Everything else becomes live (no action needed; approved and never-reviewed
    signals are all just live).

### 4.4 The editorial surface (new tables)

    briefs
      id uuid pk
      week_start date not null unique   -- Monday of the covered week; one brief/week
      status text not null default 'draft'   -- 'draft' | 'published'
      title text
      intro text
      -- Threshold-tuning visibility (operator decision): how many timing-relevant
      -- signals the M3/grade>=3 bar excluded this week, and by which gate.
      excluded_below_threshold int not null default 0
      exclusion_breakdown jsonb          -- {below_materiality: n, below_grade: n}
      created_at timestamptz default now()
      published_at timestamptz           -- set once at publish, frozen thereafter

    brief_items
      id uuid pk
      brief_id uuid references briefs(id) on delete cascade
      -- A cluster reuses the procurement spine where the signal is already
      -- clustered, else groups by organization, else stands alone.
      cluster_kind text not null         -- 'procurement' | 'organization' | 'signal'
      cluster_ref uuid not null          -- procurement_id | organization_id | signal_id
      lead_signal_id uuid references signals(id)  -- strongest/soonest member
      timing_path text not null          -- 'recent' (Path A) | 'imminent' (Path B)
      soonest_date date                  -- the driving published_on (ranking + why)
      included boolean not null default true      -- editor cut = false
      rank int                                     -- editor ordering
      headline_override text                       -- editor copy
      editor_note text
      created_at timestamptz default now()
      unique (brief_id, cluster_kind, cluster_ref)

The generator writes a `draft` brief with `included=true` items; the editor flips
inclusion, reorders, and adds copy; publishing freezes `status` and `published_at`.
The published brief joins the prediction ledger as part of the provable,
time-stamped track record. Clustering deliberately reuses the procurement spine
(the proposer already clusters signals into procurements), so the brief reads as
intelligence, not a row dump.

## 5. Pipeline and consumer changes

  * Procurement proposer: today it excludes signals whose `review_note` starts
    with 'rejected'. Change that single filter to exclude `suppressed=true`. Its
    trust basis (grade present + org resolved) is unchanged; it simply reads the
    live corpus instead of the approved subset.
  * AR1 auto-reject (from PR #51) is repurposed: instead of writing
    `review_note='rejected: ...'`, it sets `suppressed=true, suppressed_reason='AR1',
    suppressed_by='triage@v1'`. Auto-approve in triage becomes a no-op (everything
    is live) and is removed. Triage collapses to a single job: suppress obvious
    noise. It keeps its place in the weekly workflow before the proposer.
  * Predictions and reconcile: unchanged mechanically. The candidate feed for
    authoring changes (see 6.3).

## 6. The app

### 6.1 /review retires to /corpus (read-only)

The raw approve/reject queue is removed. It becomes `/corpus`: a read-only,
filterable, searchable browser over live signals, for when the operator WANTS to
look, never a to-do list. It reuses the filters and event-date sort built in
PR #50 (doc_type, confidence, min grade, min materiality, freshness fresh/stale/
undated, newest/oldest).

Phase 2 ships `/corpus` READ-ONLY (browse only, no write affordance). The
per-signal "suppress" toggle (sets `suppressed`, the editorial override, not an
approval) lands in Phase 3 alongside the brief, so Phase 2 stays a focused,
low-risk read-only conversion.

### 6.2 /brief (new): the weekly job

The editor opens the auto-generated draft Weekly Signal, cuts weak items,
reorders, adds framing, and publishes. Details in section 7.

### 6.3 /procurements becomes the prediction candidate feed

Procurement confirmation folds into prediction authoring: proposed procurements
are the menu the operator picks from when authoring a claim, and confirming
happens implicitly at authoring time. There is no standalone procurement-approval
chore. Merge capability is PRESERVED at authoring time: before authoring a claim
on a candidate, the operator can still non-destructively merge procurements
(the existing merged_into_id flow), so a claim is always made against the
correct, de-duplicated opportunity.

### 6.4 Unchanged

`/predictions` (author + confirm outcomes) and `/discovery` (approve
source/entity proposals) are unchanged.

Page summary:

| Page | Today | After |
|---|---|---|
| /review | raw approve/reject queue | retired -> /corpus read-only browser + suppress toggle |
| /brief | none | new: edit + publish the weekly draft |
| /procurements | propose + confirm queue | prediction candidate feed; merge preserved at authoring |
| /predictions | author + confirm | unchanged |
| /discovery | approve proposals | unchanged |

## 7. The Weekly Signal brief

### 7.1 Selection: an event-date window around now (reviewed 2026-07-13)

KEY FINDING that drives selection: `documents.published_on` means "the event
date," but that resolves differently by source. For awards, news, and board
minutes it is a PAST date (when it happened). For grants it is the program
DEADLINE (grants_ontario stores the deadline as published_on), typically FUTURE.
And `expected_timing` (the extractor's tender/window field) is FREE TEXT
("Q3 2025"), not a machine date. This works in our favour: a grant's imminent
deadline is a future published_on, so a single window on published_on captures
both "happened recently" and "deadline approaching," and it is backfill-safe (a
2024 contract ingested this week has a 2024 published_on and does not flood the
brief).

Selection is therefore an event-date window around today:

  * Path A, recent event: published_on in [today - 7 days, today].
  * Path B, imminent event: published_on in (today, today + lead], where `lead`
    is PER DOC_TYPE (operator decision): default 30 days, and 45 days for grants
    (grant_program, grant_award) because applications need prep runway. Grant
    deadlines, being future published_on, land here.
  * Deliberately NO `created_at` "new to corpus" path. Tradeoff accepted: a
    recently-published-but-slightly-old board decision we ingest late could be
    missed. If briefs feel like they are missing surfaced board decisions, add a
    NARROW board_minutes publication-date exception later (a documented future
    enhancement, not built now).
  * `expected_timing` is CONTEXT-ONLY on the item, never used for automatic
    Path B selection (free text is not safely comparable to a window). Parsing it
    into a real date is a flagged future enhancement.

Gates (`suppressed=false` always; the materiality/grade bar is PATH-SPECIFIC,
operator decision 2026-07-13):
  * Path A (recent, RETROSPECTIVE): full bar, materiality >= 3 AND grade >= 3.
    A past event earns a place only if it was strong enough to matter, so
    materiality gates it.
  * Path B (imminent, PROSPECTIVE): relaxed bar, materiality >= 2 AND grade >= 2.
    A closing-soon opportunity is actionable by virtue of TIMING, so timing gates
    it and grade is secondary; the floor (2/2) keeps pure noise with a future
    date out. This is why the one imminent grant a thin week surfaces is not
    filtered away by a bar meant for retrospective strength.

Cluster the selected signals: by procurement where the signal is linked to an
active, non-rejected procurement (reuses the proposer's clustering), else by
organization, else standalone. Org-level clustering STAYS: it is what makes the
brief read like intelligence rather than a row dump. Each cluster carries a
`lead_signal_id` (strongest member), a `timing_path` (imminent if any member is
future-dated, else recent), and a `soonest_date`. Rank imminent (Path B) clusters
first by soonest date, then by grade, materiality, amount.

Threshold tuning visibility (operator decision): the generator MUST report, each
week, the count of TIMING-RELEVANT signals EXCLUDED because they fell below the
materiality/grade bar, broken down by which gate they missed (below_materiality,
below_grade). It is persisted on the brief row (excluded_below_threshold +
exclusion_breakdown) and printed in the run log, so the bar can be tuned with
evidence. Not optional.

The generator writes nothing outside briefs/brief_items; it never confirms a
procurement, authors a prediction, or suppresses a signal. A brief is regenerated
only while it is a `draft`; a `published` brief is frozen and never overwritten.

### 7.2 Edit and publish

The operator edits at /brief: cut items, reorder, add headline/intro copy,
attach editorial notes. Publish sets `status='published'` and freezes
`published_at`. All honesty rules bind the generated and edited copy (date
precision, provenance links, no em dashes, no fabricated dates).

### 7.3 Cadence

The generator runs weekly (same guard pattern as the other weekly jobs), after
collection and the proposer, so the draft reflects the freshest corpus. A missed
week is not an incident; the draft is regenerable and idempotent per `week_start`.

### 7.4 Reader-facing date labels (DEFERRED: published format + subscriber portal)

Requirement (operator, 2026-07-13). Not needed in the internal /brief editor.
REQUIRED wherever a date is shown to a READER: the published brief format and the
Wave 3 subscriber portal. This is a sibling of the "None beats a wrong date"
honesty rule: a bare date is ambiguous, and a subscriber could misread an
application deadline (future) as a past event.

Every reader-facing date MUST carry its TYPE as a label, derived from
(timing_path + doc_type), both of which the brief already stores (brief_items
carries timing_path; the lead signal's document carries doc_type). Baseline map:

  | doc_type                    | timing_path | label                     |
  |-----------------------------|-------------|---------------------------|
  | grant_program / grant_award | imminent    | Application deadline      |
  | award_notice                | recent      | Contract awarded          |
  | tender_notice               | imminent    | Tender closes             |
  | tender_notice               | recent      | Tender expected           |
  | board_minutes               | recent      | Board decision            |

Combinations not yet specified (e.g. a recent grant, a news_release) get a label
defined when this is built; until then the safe default is to show the label
"Event date" rather than a bare date. Date PRECISION rules still apply (month-
precision renders "Apr 2026", never a fabricated day).

Tracked in docs/ROADMAP.md under the brief-output and Wave 3 subscriber items.

## 8. Safeguards lost, and the backstops (the tradeoff)

Dropping manual signal approval loses four safeguards:

  1. Pre-publication extraction QA: no human catches a mis-parsed amount, wrong
     org, hallucinated award, or mis-dated event before it enters the corpus.
  2. Accuracy gate feeding procurements: a bad signal can inflate a cluster or a
     coverage statistic.
  3. A spam/noise gate beyond AR1's narrow reach.
  4. Human attention on needs_org_resolution signals.

What backstops each, and why the trade is judged favorable:

  * Scores as filters, not gates: weak long-tail extractions still enter but are
    down-weighted and never surface in the brief (strong-grade/high-materiality
    only). Errors mostly live where nobody acts on them.
  * The brief edit IS the QA, on the subset that matters: the operator reviews
    the strongest, decision-relevant signals weekly and suppresses a wrong one on
    sight. QA shifts from 100% of raw extractions (which the operator cannot
    judge) to the few that actually feed decisions (which the operator can).
  * The prediction gate stays the hard trust boundary: nothing is published as a
    claim without a deliberate human authoring act, with frozen evidence, hash,
    and external timestamp. The asset that must be right, the track record, keeps
    its human gate.
  * AR1 suppression stays for obvious noise.
  * The calibration audit (section 9) replaces per-signal QA: audit the scorer,
    not every score.

Net: we trade pre-publication QA of every raw extraction for editorial QA of the
decision-relevant subset plus a hard human gate on the only thing that is
actually published. Residual accepted risk: silent extraction errors in the
long-tail corpus that could subtly skew aggregate counts (coverage, hit-rate
denominators). Mitigation is score-calibration audits, not eyeballing everything.

## 9. Calibration audit (the replacement safeguard)

Because the scores are now the trust layer, they must be kept honest. Add a
precision audit that fires on two triggers (operator decision, 2026-07-13):

  * Scheduled: monthly, sample N (default 30) random live signals stratified by
    grade.
  * Triggered: an additional audit sample after ANY change to a collector or an
    extraction prompt. Those are exactly the changes that can silently shift
    extraction accuracy, and under this model no human approval catches the
    regression, so the audit is the safety net and must run when the scorer
    changes, not only on the calendar. (Mechanically: a manual/dispatchable audit
    run the operator or CI fires as part of shipping any collector or
    extraction-prompt change.)
  * For each sampled signal, record the source URL, the extracted fields, and a
    verdict slot (accurate / inaccurate / unclear) for a human spot-check, or an
    automated re-extraction cross-check where feasible.
  * Report a precision number per grade band and overall, tracked over time (and
    labelled scheduled vs triggered, so a post-change sample is comparable
    against the baseline), so score drift is visible.

The audit is propose-only: it writes an audit sample table and a report, never
changes signals. If precision drops below a floor, that is the signal to retune
the extractor or the grade thresholds. This is the systemic replacement for
per-signal approval: the operator trusts the corpus because the scorer is
measured, not because every row was eyeballed.

## 10. Salvage and sunk (in-flight work)

  * Salvaged: PR #50's review filters + event-date sort become the /corpus
    browser. PR #51's AR1 rule becomes the suppression rule (writes `suppressed`
    instead of a rejected note).
  * Sunk (accepted): PR #49's bulk approve/reject workflow and the approval-gate
    framing. The bulk multi-select UI is retired with the queue.

Recommendation: repurpose #50 and #51 into the phases below rather than merging
them as-is, and close #49's workflow as superseded.

## 11. Phased build plan (each phase one PR, sequenced)

Phase 1: flip the trust model.
  * Migration: add `suppressed` (+ reason, by); backfill from existing
    'rejected' review_note.
  * Proposer: exclude `suppressed=true` instead of rejected review_note.
  * Triage: AR1 writes suppression; remove the auto-approve path; keep the
    weekly step before the proposer.
  * Tests updated. Reversible and small.

Phase 2: /corpus (read-only).
  * Convert /review to a read-only browser (reuse #50 filters + event-date sort).
    Remove the bulk approve/reject UI. NO write affordance in this phase (the
    suppress toggle is deferred to Phase 3), keeping Phase 2 a low-risk
    read-only conversion.

Phase 3: the brief (+ suppress toggle).
  * Migration: briefs + brief_items.
  * Weekly generator: timing-aware selection (Path A published-this-week OR
    Path B imminent deadline/expected-timing) + strong-grade + high-materiality
    + not-suppressed; surfaces the below-threshold exclusion count every week
    (section 7.1); propose-only.
  * /brief editor page: edit, reorder, cut, publish.
  * Add the /corpus per-signal suppress toggle here.
  * Wire the generator into the weekly workflow after the proposer.

Phase 4: prediction candidate feed.
  * /procurements becomes the candidate feed; fold confirmation into authoring;
    preserve the non-destructive merge at authoring time.

Phase 5: calibration audit.
  * Audit sample table + monthly scheduled job + a dispatchable triggered run for
    after collector/extraction-prompt changes + a small report surface.

Predictions, reconcile, anchoring, discovery, and all collectors are untouched
across every phase.

## 12. Decisions already made (2026-07-13)

  1. Suppression model: a single `suppressed` flag is the only editorial override.
  2. Procurement confirmation folds into prediction authoring; merge capability
     preserved at authoring time.
  3. /review retires to a read-only /corpus browser (not deleted outright).
  4. Calibration audit is in scope as the replacement safeguard.
  5. This doc is committed before any code; phases build only after it is reviewed.

Confirmed at review (2026-07-13):
  6. Brief thresholds M3 / grade >= 3, AND the generator must report the count of
     signals excluded below threshold each week so the bar can be tuned with
     evidence (section 7.1).
  7. Calibration audit: monthly N=30, PLUS a triggered audit after any collector
     or extraction-prompt change (section 9).
  8. The /corpus suppress toggle ships in Phase 3; Phase 2 is the read-only
     browser only.
  9. Brief selection is timing-aware: an imminent grant deadline or expected
     tender window qualifies a signal even if collected weeks ago, not only
     publication-fresh (section 7.1).
