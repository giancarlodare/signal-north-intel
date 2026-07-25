# Per-jurisdiction demand-arc backtest engine: design

Status: PROPOSED (design-first, 2026-07-25), build starting now. Front 3 of
the mid-August scope. Upgrades the ROADMAP stub ("Per-jurisdiction demand-arc
backtest, calibration layer") into a build. It reads award history that is
actively extracting (Toronto 7,583, Peel 2,758, boards draining), so the
engine builds now and its numbers sharpen daily as the backfill lands. It does
not wait for a complete corpus; it calibrates continuously.

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

## 4. Output (one small schema addition)

A `demand_arc_profiles` table, one row per (organization, transition):
`organization_id, from_level, to_level, n, lag_median_days, lag_p25, lag_p75,
lag_p90, computed_at`. Recomputed by a scheduled job; `computed_at` makes the
continuous-calibration visible. A per-service view reads it into a demand-arc
profile (rhythm + horizons + sample sizes).

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

## 7. Build order (starting now)

1. `demand_arc_profiles` migration (one table, additive).
2. `src/demand_arc.py`: the walk + aggregation, dry-run first (report the
   profiles it WOULD write, per service, with n and lags), so the first
   numbers are inspected before anything is stored.
3. Wire the demand-arc workflow (weekly + dispatch).
4. Read the profiles into a per-service view and the ledger horizon.

Validation gate: the dry-run's first profile table is brought to the operator
(per-service transitions, n, median/percentile lags) before the schema applies
and the job enables. Thin arcs are labeled insufficient, never smoothed over.
