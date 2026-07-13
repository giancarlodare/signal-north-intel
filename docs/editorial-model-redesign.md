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
      week_start date not null          -- Monday of the covered week
      status text not null default 'draft'   -- 'draft' | 'published'
      title text
      intro text
      created_at timestamptz default now()
      published_at timestamptz          -- set at publish, frozen thereafter
      unique (week_start)               -- one brief per week

    brief_items
      id uuid pk
      brief_id uuid references briefs(id)
      signal_id uuid references signals(id)         -- nullable
      procurement_id uuid references procurements(id) -- nullable (item may be a cluster)
      included boolean not null default true         -- editor cut = false
      rank int                                        -- editor ordering
      headline_override text                          -- editor copy
      editor_note text
      created_at timestamptz default now()

The generator writes a `draft` brief with `included=true` items; the editor flips
inclusion, reorders, and adds copy; publishing freezes `status` and `published_at`.
The published brief joins the prediction ledger as part of the provable,
time-stamped track record.

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
undated, newest/oldest). The only write affordance is a per-signal "suppress"
toggle (sets `suppressed`), which is the editorial override, not an approval.

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

### 7.1 Generation (weekly job)

Select the week's signals where all hold:
  * event date (documents.published_on) within the covered week (fresh);
  * materiality >= threshold (default M3, tunable);
  * evidence_grade >= threshold (default commitment/3, tunable);
  * `suppressed=false`.

Cluster them (by procurement where linked, else by organization, else by theme),
rank by a simple salience score (grade, then materiality, then amount), and write
a `draft` brief with `brief_items`. The generator writes nothing outside briefs/
brief_items; it never confirms a procurement or authors a prediction.

### 7.2 Edit and publish

The operator edits at /brief: cut items, reorder, add headline/intro copy,
attach editorial notes. Publish sets `status='published'` and freezes
`published_at`. All honesty rules bind the generated and edited copy (date
precision, provenance links, no em dashes, no fabricated dates).

### 7.3 Cadence

The generator runs weekly (same guard pattern as the other weekly jobs), after
collection and the proposer, so the draft reflects the freshest corpus. A missed
week is not an incident; the draft is regenerable and idempotent per `week_start`.

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
recurring precision audit:

  * Monthly, sample N (default 30) random live signals stratified by grade.
  * For each, record the source URL, the extracted fields, and a verdict slot
    (accurate / inaccurate / unclear) for a human spot-check, or an automated
    re-extraction cross-check where feasible.
  * Report a precision number per grade band and overall, tracked over time, so
    score drift is visible.

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

Phase 2: /corpus.
  * Convert /review to a read-only browser (reuse #50 filters + event-date sort)
    with a per-signal suppress toggle. Remove the bulk approve/reject UI.

Phase 3: the brief.
  * Migration: briefs + brief_items.
  * Weekly generator (fresh + strong-grade + high-materiality + not-suppressed),
    propose-only.
  * /brief editor page: edit, reorder, cut, publish.
  * Wire the generator into the weekly workflow after the proposer.

Phase 4: prediction candidate feed.
  * /procurements becomes the candidate feed; fold confirmation into authoring;
    preserve the non-destructive merge at authoring time.

Phase 5: calibration audit.
  * Audit sample table + monthly job + a small report surface.

Predictions, reconcile, anchoring, discovery, and all collectors are untouched
across every phase.

## 12. Decisions already made (2026-07-13)

  1. Suppression model: a single `suppressed` flag is the only editorial override.
  2. Procurement confirmation folds into prediction authoring; merge capability
     preserved at authoring time.
  3. /review retires to a read-only /corpus browser (not deleted outright).
  4. Calibration audit is in scope as the replacement safeguard.
  5. This doc is committed before any code; phases build only after it is reviewed.

Open for confirmation at review: the default brief thresholds (M3, grade >= 3),
the audit cadence and sample size (monthly, N=30), and whether the /corpus
suppress toggle ships in Phase 2 or waits for Phase 3.
