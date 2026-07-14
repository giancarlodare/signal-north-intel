# Prediction and Track-Record Ledger: Design (Phases A and B)

**Status: DESIGN FOR REVIEW. No code exists yet, no schema applied.** Nothing
below gets built until this document is approved, matching the convention used
for the discovery engine and the federal awards ingest.

Author stamp convention will follow the rest of the repo: modules stamp a
version (for example `ledger@v1`, `reconcile@v1`) onto every row they write.

## 0. Thesis

Signal North is not a prospect list. It is a predictive intelligence engine
whose most valuable asset is a provable, time-stamped track record of calling
which companies win government attention and contracts before the market sees
it. The engine today records what it observed. It does not yet record what it
predicted, nor reconcile predictions against outcomes, nor compute a hit-rate.
This document designs the ledger that closes that gap, plus the two
foundations a credible prediction rests on: a demand-strength taxonomy on
every signal (Phase A) and a first-class procurement entity for a claim to be
about (Phase A). The ledger itself is Phase B.

The market's single question is: which government opportunities are real,
versus which are only announcements, MOUs, and letters of intent. Every design
choice below sharpens that answer and proves we get it right over time.

## 1. Hard rules (non-negotiable, enforced structurally)

- **Additive only.** Nothing here touches a collector, a collection workflow,
  or the extraction path. The ledger is new tables, new modules, new pages.
  Collector and coverage work continues on its own interleaved PRs. The ledger
  is worthless without volume flowing through it, so collection never pauses
  for it.
- **Immutable claims.** A prediction, once written, is frozen. No update, no
  delete, ever. Corrections are new rows. Reconciliation outcomes live in a
  separate append-only table so the claim itself never changes. This is what
  makes the track record provable rather than editable after the fact.
- **Public provenance absolute.** A prediction cannot exist without at least
  one linked public evidence document, enforced the same way discovery
  proposals enforce it (NOT NULL plus an array-length check). Every basis
  document is a publisher URL already in the corpus. This structurally
  inherits the standing government-capacity firewall: a claim can rest only on
  public record, never on anything learned in an official capacity.
- **Propose, predict, approve, reconcile.** The current propose-then-approve
  loop gains two nodes. The engine may draft candidate predictions from strong
  signal clusters (propose), a human promotes a candidate into a logged claim
  (predict and approve), and a weekly job proposes outcomes for open claims
  that a human confirms (reconcile). The engine never self-certifies a claim
  or its outcome.
- **Audience-neutral engine.** The prediction tables know nothing about who
  reads them. A seller view and a later, gated investor view are produced by a
  separate export layer over the same neutral engine. See section 6.
- **Canadian-hosted.** All ledger tables live in the existing Canadian-region
  Postgres. No new data processor, no new residency surface. Any future
  investor delivery mechanism gets its own residency review before it ships.

## 2. Current state this builds on

- `documents` (typed by `doc_type`, provenance-locked, content-hashed,
  event-dated with `date_precision`).
- `signals` (typed by a 24-value `signal_type` enum; scored today on two axes,
  `confidence` in {confirmed, probable, speculative} and `materiality` 1 to 5;
  linked to `organizations` and to a source `document`).
- `organizations`, `vendors`, `contract_awards`, `prospects`, and the
  `discovered_*` proposal tables with their propose-only discipline.

The key insight from the audit: `confidence` answers "how sure are we this
event is true," which is a different axis from "how much does this event prove
real demand." Phase A adds that second axis. It does not touch the first.

## 3. Phase A1: demand-strength taxonomy

A deterministic grade on every signal, answering the market's question
directly. Five rungs, weakest to strongest:

| Grade | Rung | Meaning |
|---|---|---|
| 1 | `chatter` | Announcements, opinion, political pressure, media waves. Talk. |
| 2 | `intent` | Programs forming, commitments, reforms, funding announcements. Something is taking shape. |
| 3 | `commitment` | Budget line, capital plan, board approval, grant award, renewal window. Money or authority is committed. |
| 4 | `in_market` | RFI or pre-RFP, posted tender. A real procurement is live. |
| 5 | `awarded` | Contract awarded. Money moved on a procurement. |

The grade is derived, not model-guessed, so it is defensible and never drifts.
It is the maximum of two deterministic lookups:

- **signal_type to grade.** For example `media_coverage_wave`,
  `political_pressure`, `policy_announcement`, `election_commitment` map to
  `chatter`; `funding_program`, `pilot_program`, `procurement_reform` map to
  `intent`; `budget_allocation`, `capital_plan_item`, `board_decision`,
  `contract_expiry` map to `commitment`; `rfi_pre_rfp`, `tender_published` map
  to `in_market`; `contract_award` maps to `awarded`.
- **doc_type floor.** The document a signal came from sets a floor: an
  `award_notice` document floors at `awarded`, a `tender_notice` at
  `in_market`, a `grant_award` at `commitment`, a `news_release` or
  `grant_program` at `intent`, a `media_article` at `chatter`.

A deliberate nuance to record: a `grant_award` is money moved, but it is a
grant, not a procurement contract. On the "is this procurement real" axis it
is a strong upstream leading indicator, so it grades `commitment`, not
`awarded`. Grading it `awarded` would falsely claim a procurement outcome.

**Shape (illustrative, not a migration).** A lookup table
`signal_evidence_grade(signal_type, base_grade)` plus a `doc_type_grade_floor`
lookup, and a stored `signals.evidence_grade smallint` written at extraction
time and backfilled once for existing rows. Storing it (rather than computing
on read) means the grade at the moment of prediction is frozen alongside the
claim, which matters for the immutable record. A regrade is a new migration
with a new taxonomy version, never an in-place rewrite of history.

**Surfacing.** The review page shows the grade as a chip next to the existing
materiality and confidence chips. This is the "surface it explicitly on every
record" requirement.

## 4. Phase A2: the procurement spine

A prediction says "Company X will advance on Procurement Y." Today there is no
Y. Signals attach to documents and organizations, but there is no entity for a
named opportunity that accumulates evidence over time as it climbs the grade
ladder. Phase A2 adds it.

**`procurements` (net-new).** A named opportunity: buyer organization,
title, jurisdiction, category, a free-text description, and a `current_stage`
that mirrors the five-rung ladder (the stage is the highest grade of any
signal linked to it). Provenance stays intact because a procurement is only
ever built from linked signals, never invented.

**`procurement_signals` (net-new link table).** Many-to-many between
`procurements` and `signals`. This is how an opportunity accumulates its
evidence trail and how its stage advances.

**The hard data problem, flagged.** Deciding that two signals concern the same
procurement is the org-resolution problem again, one rung harder. The design
keeps a human in the loop: candidate procurements are proposed from clustered
signals (same buyer org, similar title, same category, within a window) and a
reviewer merges or splits them in the app, exactly the discipline already used
for unresolved organizations. No autonomous merging.

## 5. Phase B: the prediction ledger

### 5.1 `predictions` (net-new, append-only, immutable)

One row per falsifiable claim. Illustrative fields:

- `id`, `made_at` (the authoritative timestamp, the crux of the whole asset),
  `made_by` (version stamp, for example `ledger@v1`).
- `subject_kind` in {procurement, organization_category}. A claim may be about
  a named procurement (the sharp product) or, earlier-stage, about a company
  in a category ("Company X will win federal attention in body-worn video
  within N months"). See open question 2.
- `subject_organization_id`, `subject_procurement_id`, `subject_category_id`
  (the relevant ones set for the subject_kind).
- `predicted_outcome` (structured: the claim is that the subject reaches at
  least grade in_market, or awarded, within the horizon).
- `horizon_months`, and a derived `horizon_ends_on`.
- `rationale` (the human-readable claim text).
- `claim_hash`: a sha256 over the canonical claim fields plus the sorted basis
  evidence IDs plus `made_at`. Stored so any later tampering with the row is
  detectable even by someone with database access. Tamper-evidence, not
  tamper-proofing.

Immutability is enforced two ways: no update or delete grant to the
`authenticated` role, and a database trigger that raises on any UPDATE or
DELETE of a `predictions` row. Defense in depth.

### 5.2 `prediction_evidence` (net-new, immutable)

Links a prediction to the signals and documents it rests on. NOT NULL and an
array-length check guarantee at least one public evidence document, so a
baseless claim cannot exist. This is the provenance rule and the
government-capacity firewall, made structural.

### 5.3 `prediction_outcomes` (net-new, append-only reconciliation log)

Kept separate so the claim stays frozen. One row per reconciliation event
(a prediction can go unresolved, then resolved). Fields: `prediction_id`,
`resolved_on`, `outcome` in {correct, partial, incorrect, expired,
unresolved}, `settling_document_id` (the public document that settled it), a
note, and a `proposed_by` or `confirmed_by` stamp. The hit-rate view reads the
latest confirmed outcome per prediction.

### 5.4 `src/reconcile.py` (net-new, weekly, propose-only)

Reads open predictions (no confirmed outcome, horizon not yet expired), looks
for strong-grade evidence (in_market or awarded) on the subject procurement or
organization-category within the horizon, and proposes an outcome row for
human confirmation. Predictions whose horizon has passed with no settling
evidence get a proposed `expired` or `incorrect` outcome. The module's only
write surface is proposed rows in `prediction_outcomes`. It touches no
collector and schedules nothing. It rides the existing weekly workflow after
discovery, behind the same guard and concurrency group.

### 5.5 Hit-rate and lead-time (net-new, reviewer-facing only)

A view over confirmed outcomes: correct over the settled total, plus the
metric that actually proves the thesis, **lead time**: days between a
prediction's `made_at` and the `published_on` of the public evidence that
settled it. A positive lead time is the machine-checkable proof that the call
was made before the market saw it. This view is reviewer-facing in Phase B and
becomes the spine of the seller and (gated) investor track-record outputs in
Phase C.

### 5.6 The evolved loop

Propose (discovery and, now, candidate predictions), predict (a reviewer
promotes a candidate into a logged immutable claim), approve (the existing
signal approve, plus prediction approval), reconcile (weekly proposed
outcomes, human confirmed). A new Predictions page in the app, next to Review,
Prospects, and Discovery, carries the predict and reconcile actions. No delete
anywhere, consistent with the rest of the app.

### 5.7 Per-jurisdiction demand-arc backtest (calibration layer, Wave 2, post-award-history)

A future calibration layer on top of the ledger. NOT built now. Prerequisite:
sufficient AWARD history per jurisdiction, which begins flowing once the
municipal tender/award collectors land (Peel via bids&tenders,
`docs/peel-tenders-design.md`).

What it does. Once award history exists, walk each AWARDED procurement BACKWARD
along the procurement spine to its originating commitment/budget signal, and
measure the lag at each rung transition:
  * commitment -> in_market (a budgeted/approved need becomes an open tender),
  * in_market -> awarded (an open tender becomes an award).
Aggregate per jurisdiction to learn that jurisdiction's REAL demand rhythm:
  * conversion RHYTHM: the measured lag distribution at each rung transition, and
  * conversion RATE: which commitments actually became procurements versus
    fizzled (the denominator matters as much as the lag).

Two payoffs:
  1. Ground prediction HORIZON DEFAULTS in each jurisdiction's measured history
     instead of the current fixed per-rung guesses (`src/predictions.py`
     `default_horizon_months`, and the app's `DEFAULT_HORIZON`). "Peel
     commitment -> tender" would default to Peel's measured median lag, not a
     global constant.
  2. Surface a conversion-rate PRIOR on procurement candidates: "Peel
     commitments of this type historically reach tender X% of the time in Y
     months." A prior, shown to inform the human author, never an auto-claim.

DESIGN IMPLICATION TO PRESERVE NOW (actionable today, not deferred). Walking the
arc is only possible if the procurement spine's HARD-KEY wiring stays clean: the
`procurement_id` hard key that links a tender document to its award
(`documents.reference_number` carrying `procurement_id`, section 4), and the
`procurement_signals` links from a procurement back to its commitment-stage
signals. Every collector and the proposer must keep that linkage intact and
unambiguous, because a broken or fuzzy tender-to-award link makes the backward
walk impossible. This is the one part of the future feature that constrains work
being done now: keep the hard key clean.

Honesty rules still bind: lags are measured from frozen event dates
(`published_on`), never collection dates; a jurisdiction with too little history
shows no prior rather than a fabricated one ("None beats a wrong number").

## 6. Two-sided seam (designed, not built)

The engine tables above are audience-neutral. Audience lives only in an export
layer:

- **Seller export (built in Phase C).** For a prospect and a named
  procurement: probability of advancing (from the grade trajectory and any
  open prediction), who decides (buyer authority mapping, public official
  roles only), and what would shift the odds (the next stronger grade rung not
  yet observed).
- **Investor export (designed, unbuilt seam).** A stub module with a
  documented output schema, no route, gated off by default. It reads the same
  neutral engine. It ships dark alongside the legal-seam document
  (`docs/legal-seam-investor.md`) so counsel can review the shape before a
  single investor-facing byte is produced.

Keeping audience out of the engine and in the export layer is what makes the
product two-sided-capable without building the second side now.

## 7. Build order and the interleave guarantee

A (taxonomy and procurement spine), then B (ledger), then C (seller outputs
and the seam), then D (neighbouring questions: incumbent vulnerability, timing
windows, competitor positioning). Every one of these is new tables, modules,
and pages. Between each ledger PR, collector and coverage PRs land on their own
branches: federal awards (PR #36, in flight), then new provinces and source
types. The ledger and the collectors never compete for the same PR, and
collection is never paused to build the ledger.

## 8. Open questions for the operator

1. **Who authors predictions initially.** Recommendation: the engine drafts
   candidates from strong signal clusters (propose), and a human promotes them
   (predict and approve). Keeps volume up while keeping a human on every
   logged claim. Pure-manual authoring is the fallback.
2. **Claim subject.** Recommendation: allow both procurement-level and
   company-plus-category-level claims via `subject_kind`. Procurement-level is
   the sharp seller product; company-level captures earlier-stage calls and
   feeds the track record sooner.
3. **Default horizon and expiry.** Recommendation: 12-month default horizon,
   auto-expire a claim 3 months past its horizon if still unsettled.
4. **Confirming-evidence bar.** Recommendation: a claim counts as correct when
   the subject reaches grade in_market (posted tender) or awarded, matching the
   predicted outcome. This is deliberately a public, high-grade bar.
5. **Procurement identity.** The hardest problem (section 4). Recommendation:
   propose candidate procurements from clustered signals, human merge or split
   in the app, no autonomous merging. Same discipline as org resolution.
