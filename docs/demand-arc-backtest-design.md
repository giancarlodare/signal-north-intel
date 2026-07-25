# Per-jurisdiction demand-arc backtest engine: design

Status: PROPOSED (design-first, 2026-07-25), build starting now. Front 3 of
the mid-August scope. Upgrades the ROADMAP stub ("Per-jurisdiction demand-arc
backtest, calibration layer") into a build. It reads award history that is
actively extracting (Toronto 7,583, Peel 2,758, boards draining), so the
engine builds now and its numbers sharpen daily as the backfill lands. It does
not wait for a complete corpus; it calibrates continuously.

## 0. North star: the prediction table is the product (operator 2026-07-25)

The engine's deliverable is not a report, it is a first-class product surface:
a per-service (later per-ministry) PREDICTION TABLE. This section sets what
"done" means; the engine keeps building as-is and folds these in as the volume
lands, no retrofit.

**Rows** are services (police services + boards across Ontario first, then
ministries/departments). **Columns** are the arc transitions:

    incident -> council -> budget -> tender -> award

which is the domain reading of the abstract demand ladder (incident =
pressure_signal / leading indicator; council = chatter/intent; budget =
commitment; tender = in_market; award = awarded). Each column is one
transition; a cell is that service's calibrated horizon for that transition.

**Each cell reports four things, and nothing softer:**

- (a) **median lag** (days) for the transition;
- (b) a **bootstrapped confidence interval** on the median. Procurement lags
  are right-skewed and heavy-tailed, NOT normal, so we never report a bare
  mean or a normal-theory interval. A percentile bootstrap (resample the
  service's lag observations with replacement, recompute the median, take the
  2.5/97.5 or 10/90 percentiles of the bootstrap distribution) gives an honest
  interval that makes no distributional assumption;
- (c) **explicit n**, always shown, never hidden;
- (d) a **significance verdict** (see the gate).

**The significance gate (min-n AND interval-width):** a cell shows a prediction
ONLY when `n >= N_MIN` AND the CI is narrower than `W_MAX` (a set width, e.g.
the CI half-width under a fraction of the median). Otherwise the cell shows
`pending, n=X`, never a soft number. The table visibly FILLS as data extracts,
and the empty cells are the credibility: a gap is an honest "not yet", not a
guess dressed as a prediction. N_MIN and W_MAX are operator-set constants,
tunable as the corpus grows.

**Later: measured error.** Once the horizons feed the prediction ledger
(section 6), each published cell gains a fifth attribute, backtested error
(hit-rate + lead-time MAE against settled actuals), so a cell reads "N days,
CI [a,b], n=k, error +/-E". That is the further credibility layer, banked; the
initial surface is (a) through (d).

## 0a. Ministry rollup (banked, spec early so it is not a retrofit)

The ministry/department table is the same engine aggregated one level up, and
its ONLY new dependency is a clean buyer -> ministry rollup in org resolution.
Spec now:

- Org resolution gains a `parent_ministry` (or `rollup_org_id`) attribute on
  organizations, mapping each buying service/agency to its ministry or
  department (OPP -> Ministry of the Solicitor General; a hospital -> its
  health envelope; a federal agency -> its department). Non-destructive,
  additive, human-confirmed like every other org edit.
- The engine then aggregates arcs across all services under a ministry into the
  ministry row, using the SAME bootstrap + gate. Partial pooling (below) lets a
  ministry row exist before every child service is significant.
- Because the rollup is an org-resolution attribute, not a demand-arc concept,
  the ministry table needs no engine rewrite: it is the service engine grouped
  by `parent_ministry` instead of `organization_id`.

## 0b. Every service gets an honest row (partial pooling)

Many services buy too rarely to reach `N_MIN` on their own. Rather than leave
them blank forever, the mature engine uses hierarchical / partial-pooling
estimation: a thin service borrows strength from the population of similar
services (same rollup / type), so it still carries a calibrated horizon with
wide-but-honest bars that shrink toward its own signal as its data grows. The
significance gate still governs what is labeled published vs pending; pooling
only stabilizes the estimate, it never manufactures confidence. This is a later
addition, noted here so the schema and gate anticipate it.

## 1. What it computes

For each award, walk BACKWARD along the procurement_id spine to the earliest
linked signal at each demand-strength level, and measure the lag at each
transition:

    pressure_signal -> chatter -> intent -> commitment -> in_market -> awarded

Each arrow is a dated transition. The lag is the day count between the
earliest signal at one level and the earliest at the next. Aggregated per
service (organization / jurisdiction), the lag distribution IS that service's
measured demand rhythm, and the intent->awarded lag distribution IS its
calibrated prediction horizon (how far ahead an intent signal calls an award,
with a confidence band).

## 2. Inputs (all existing spine entities)

- `procurements` (Phase A) as the spine key; `signals.procurement_id` links
  signals to a procurement; `signals.demand_strength` and event date carry the
  level and timing; `signals.organization_id` carries the service.
- `contract_awards` / `award_notice` documents for the terminal `awarded`
  event and its date.
- The upstream intent layer (Front 2) supplies the pre-solicitation levels
  (chatter/intent/commitment) and `pressure_signal` inputs; where that layer
  is not yet live for a service, the arc computes over the levels present
  (in_market -> awarded) and lengthens as upstream lands. Partial arcs are
  first-class, not errors.

## 3. The walk (src/demand_arc.py)

For each procurement with an award:
1. Gather its linked signals, grouped by demand_strength, each with its
   earliest event date (none-dated signals are skipped for lag math; never
   fabricate a date).
2. Emit per-transition lags for the consecutive levels present.
3. Attribute to the service via `organization_id` (falling back to the buyer
   org on the award).

Aggregation per service:
- Per transition: n, median lag, p25/p75, p90 (the rhythm).
- intent->awarded and commitment->awarded: median + band = the prediction
  horizon; n gates whether the horizon is reportable (a minimum sample, e.g.
  n >= 8, below which it is "insufficient history", never a fabricated number).

## 4. Output (schema, in two steps)

`demand_arc_profiles`, one row per (organization, transition). Recomputed by a
scheduled job; `computed_at` makes the continuous calibration visible.

- **v1 (built now):** `organization_id, from_grade, to_grade, n,
  lag_median_days, lag_p25, lag_p75, lag_p90, computed_at`. Percentiles are the
  descriptive spread while the bootstrap lands.
- **v2 (the north-star cell, additive follow-on migration):** add
  `ci_low, ci_high, ci_method` (percentile-bootstrap median CI),
  `significance` (`published` | `pending`), and the gate params in effect
  (`n_min, w_max`) so a stored row is self-describing. A later v3 adds
  `backtest_error_days` once the ledger loop (section 6) is closed.

The per-service and per-ministry PREDICTION TABLES (section 0) read this table:
service rows group by `organization_id`, ministry rows group by the
`parent_ministry` rollup; each cell renders (median, CI, n, verdict) and shows
`pending, n=X` wherever the gate is not met.

## 5. Calibration cadence (continuous)

A `demand-arc` workflow (weekly + on-demand) recomputes the profiles from the
current corpus. As the Toronto/Peel/board award history drains and the
upstream layer lands, n grows and the bands tighten, run over run. The engine
reports its own sample sizes so a thin arc is never mistaken for a confident
one. This is a read-only analysis job (no LLM): cheap to run often.

## 6. How it feeds the product

The calibrated horizons feed the prediction ledger (Phase B): a fresh intent
signal for a service with a measured intent->awarded horizon becomes a dated,
reconcilable prediction with a real lead time, instead of a guess. The rhythm
per service tells the brief which services are "due" based on their measured
cadence. This is the calibration layer the ledger was designed to consume.

## 7. Build order

DONE: `demand_arc_profiles` v1 migration; `src/demand_arc.py` walk +
aggregation with dry-run; first per-service table brought to the operator
(Peel arcs, all n<8 flagged insufficient). This established the spine.

Next, folding in section 0 as volume lands (no rush ahead of the sprint gates):
1. **Bootstrap CI** on the median per (org, transition), added to the engine
   and to the profiles schema (v2).
2. **Significance gate** (`n >= N_MIN AND ci_width <= W_MAX`) driving the
   `published` / `pending, n=X` verdict; the gate replaces the bare `n<8` flag.
3. **Prediction-table view** (service, then ministry via the org rollup) as the
   product surface reading the profiles.
4. **Ledger loop** (section 6) to earn the v3 backtested-error column.
5. **Partial pooling** (section 0b) once enough services exist to define the
   population, so thin services get honest wide-barred rows.

Validation gate holds throughout: no cell is ever soft-filled; a gap shows
`pending, n=X`. Each schema step is additive and brought to the operator before
it applies.
