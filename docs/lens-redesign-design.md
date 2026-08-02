# Lens redesign: weighted score replacing the lexicographic sort

Status: PROPOSED 2026-08-02, design only. Nothing changes until the
operator approves the factors and coefficients below. `amount` is left
untouched as ruled (measured inert: zero contribution in the top 30).

## Why (the decomposition finding)

`rank_key` is lexicographic, so a later factor matters only on an exact
tie of every earlier one. Run 30750539470 measured the consequence:
closing date decided 13 of the top-30 adjacent orderings, materiality 9,
everything else zero. Relevance is not underweighted; it is structurally
unreachable. That is not tunable, hence replacement.

## The score

score(cluster) =
      w_cat * category_relevance
    + w_buyer * buyer_type
    + w_arc * arc_connection
    + w_window * actionable_window
    + w_mat * materiality_norm
    + w_grade * grade_norm

Proposed starting coefficients, chosen so arc connection and category
relevance together outweigh everything else (they are the product thesis),
and normalized so each factor is 0..1 before weighting:

| factor | weight | definition |
|---|---|---|
| category_relevance | 0.25 | per-category coefficient table: core vendor categories (RMS, CAD, digital evidence, body-worn, ALPR, radio, forensics, dispatch, fleet, use-of-force...) = 1.0; facilities/construction AT a police/fire/EMS service = 0.4 (real, but any GC bids them); civil works = 0.0 and a **hard floor**: a 0.0 category never reaches the brief regardless of total score, even with public_safety=true |
| buyer_type | 0.15 | typed buyer, not string match (the PSPC lesson): police/fire/EMS service or board = 1.0; federal safety/defence department = 1.0; municipality general = 0.3; other = 0.0 |
| arc_connection | 0.30 | heaviest single factor. Precursors in the corpus for the same buyer x category: 0 precursors = 0; 1 = 0.6; 2+ dated deep-linked = 1.0. This is what makes the brief a story rather than a tender feed |
| actionable_window | 0.15 | a CURVE, not soonest-first: 0 at <=3 days (too late to act), rising to 1.0 at 21-35 days, easing to ~0.5 at 60, ~0.2 beyond. Soonest-first was actively wrong for subscribers who need time to respond |
| materiality_norm | 0.10 | the size/significance score (see the split below), /5 |
| grade_norm | 0.05 | evidence grade /5. Kept small but present -- my one addition to the operator's list: grade is the record-quality floor and dropping it entirely would let a rung-2 rumor outrank a rung-4 tender on relevance alone. Selection bars already gate entry; this just breaks ties toward stronger evidence |

Timing paths stop being an absolute partition: imminent/recent become an
input to actionable_window rather than the outer sort. Determinism: ties
break on (grade, soonest_date, signal id) so ordering is stable run-to-run.

Dependencies stated honestly: category_relevance needs the categorization
work (8 largest arc-ready cells are currently `(uncategorized)`; an
uncategorized cluster scores the table's DEFAULT 0.5, not zero, so
categorization gaps do not silently bury items). buyer_type needs the
resolution work. Both are already queued ahead of this.

## The materiality/relevance split (Fix 2) -- my view: yes, and it is the
root fix

Agreed without reservation. materiality currently conflates "how big is
this" with "does a public-safety vendor care", and the model has no way to
express the difference because we never asked. A $40M watermain is
genuinely material and completely irrelevant; today those collapse into
one 1..5 integer. Proposed:

- `materiality` keeps its meaning: size/significance of the procurement.
- new `relevance` 1..5: "how much does this matter to someone selling
  into public safety?" -- with anchors in the prompt (5: core public-safety
  vendor category; 3: dual-use/adjacent; 1: no public-safety vendor would
  bid this). The civil false-tag class scores 1 by definition.
- The lens inclusion bar then reads relevance, not materiality:
  defence_relevant OR (public_safety AND relevance >= 4), and
  category_relevance in the score above can be seeded from measured
  relevance averages per category rather than hand-tuned forever.

Cost, estimated for the operator's decision (measured probe before any
spend, as always): this is a schema change (gated migration: one integer
column on signals) plus a prompt change. Backfill across ~12,000 live
signals is a SHORT prompt per signal (title + summary in, one integer
out), which is cascade-triage shaped, not extraction shaped. At
Haiku-class pricing that is on the order of **$5-15 total**; even priced
at the full Opus extraction rate it stays under ~$40. Recommendation:
backfill everything -- forward-only would leave the existing corpus (the
material the census and arcs read) permanently unscored, for a saving of
at most tens of dollars. A 200-signal calibration batch runs first and
its agreement with human judgment is reported before the full pass, per
the cascade discipline: if the false-negative rate is unacceptable, we do
not ship it, whatever it saves.

## Out of scope here

The civil false-tag gate (categorization design doc). The demand-voice
layer's asker weighting (its own doc; that layer never enters this
ranking).

## Rollout

1. Operator approves factors + coefficients (this doc).
2. relevance schema + prompt change + calibration batch (gated).
3. `rank_key` replaced behind a test suite that pins ordering on fixture
   clusters; old and new rankings printed side by side for two cycles
   (report-only shadow) before the new order drives the draft.
