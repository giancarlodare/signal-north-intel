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

## 0c. Backward historical reconstruction (operator reframe, 2026-07-26)

The path to statistical significance is BACKWARD RECONSTRUCTION, not forward
accumulation. Complete demand arcs already exist in the historical record:
past procurements (opened and closed), historical budgets, archived board and
council minutes, old announcements. A 2021 incident -> council pressure ->
budget line -> 2023 tender -> award is a fully-formed, measurable arc sitting
in the archives NOW. The binding constraint on significance is EXTRACTION
DEPTH and HISTORICAL REACH, not time. Program, per service (and provincial /
federal entity):

1. **Inventory**: how far back each source actually goes (bids&tenders award
   history, board minutes archives, council minutes archives, newsroom
   archives, budget documents) vs how much we have COLLECTED and EXTRACTED.
   Report the collected-vs-available gap (`scripts/inventory_corpus_depth.py`
   is the collected/extracted side; archive-reach probes fill the available
   side).
2. **Deepen**: where archives extend past our collection, deepen the backfill
   to the full available history, prioritizing sources richest in linkable
   arc events (budgets, board capital plans, closed procurements with
   references).
3. **Re-run the engine** against the deepened history; per-service n per
   transition should climb sharply once years of history extract instead of a
   recent slice.
4. **Coverage report**: n, CI width, significance verdict per service x
   transition. The test: with full historical extraction, how many cells
   reach significance? That number, not the passage of time, is the
   predictive floor, and it tells us where to point more collection.

**PILOT-FIRST (operator 2026-07-26): Toronto + Peel before the fleet.** The
biggest services pilot the method: densest history = where significance is
actually reachable and where the hard arc-linking problems surface cheapest.
Sequence: pilot Toronto + Peel (York/Ottawa as secondaries) -> deepen their
history -> reconstruct arcs -> re-run the engine -> their per-transition
n / CI / significance verdict. The pilot answers three things at once: how
hard arc reconstruction actually is; whether significance is achievable on
dense data at all; and a sellable demo result. The full-fleet historical
extraction spend is approved only AFTER the pilot proves the method and the
real per-service cost is known: validate on two services before committing
across thirty.

Pilot pipeline (all existing machinery): (1) the extract-backfill drain
converts the pilot's captured history into graded signals (Toronto's 9.7k
awards + the boards' minutes are already in its scope, running on cadence);
(2) the procurement proposer links signals to procurements
(propose-then-approve: the operator confirms links, nothing auto-merges);
(3) the engine (with the v2 bootstrap CI + significance gate, built
2026-07-26) emits the pilot coverage report.

## 0d. Two claims and the convergence indicator (client-facing product design, operator 2026-07-26)

Status: BANKED, design-thinking only. Gated on the pilot (section 0c) proving
significance on Toronto + Peel. Nothing here is built, wired, or shown to a
client ahead of that gate.

The claim "we have a statistically significant predictive tool" needs the
next sentence: predicting WHAT, and what does the client DO with it. The
answer is two claims of different precision, sold as one credibility system:

**Claim 1: the specific hard prediction (the ledger).** "Service X will issue
a tender for Y within window Z." Precise, dated, reconcilable against
actuals, anchored (Phase B ledger + OpenTimestamps). Rare by nature: the gate
publishes a hard call only when a cell is significant AND a live upstream
signal sits on a measured horizon. Claim 1 is not the volume product; it is
the PROOF product. Its verified track record (hit-rate, lead-time error
against settled actuals) is what makes Claim 2 credible.

**Claim 2: the convergence / movement prediction (the client-facing
feature).** "Independent upstream sources are converging on [service] +
[domain]; based on that service's measured demand rhythm, expect movement in
roughly N months, confidence X." Makeable far more often than Claim 1,
because it predicts movement in a domain, not a named instrument. This is
what the subscriber watches daily. The two claims reinforce: Claim 1's
audited ledger is the reason a client believes Claim 2's softer call; Claim 2
is the reason the product is useful between rare hard calls.

**The convergence indicator (the dashboard / Weekly Signal feature):** a
per-service, per-domain indicator with these properties, all mandatory:

- **Rises on independent stacking.** The indicator strengthens as upstream
  signals from INDEPENDENT sources (board minutes, council minutes, budget
  lines, Hansard, newsroom, tender pre-signals) stack on the same
  service + domain pair. Independence matters: five echoes of one press
  release are one signal, not five.
- **Never a black box.** The indicator always shows the specific converging
  signals behind it, each provenance-linked to its publisher document, the
  same way every other surface works. A subscriber can click through and
  read exactly what is converging.
- **Attaches the expected window.** The window comes from the service's
  measured demand-arc lag for the relevant transition (the section 0 cell),
  with that cell's CI as the confidence band and its significance verdict
  governing whether a window is shown at all. A pending cell means the
  indicator can show convergence but NOT a window: honest gaps carry through
  to the client surface.
- **Sharpens progressively.** As more signals land, the indicator sharpens
  the predicted INSTRUMENT: from "movement" to grant vs tender vs
  legislation vs program change, narrowing as the signal mix disambiguates
  (a budget line + board capital item points at a tender; a ministry
  announcement + formula stream points at a grant). Progressive sharpening
  IS the product experience: the subscriber watches a prediction come into
  focus, and each sharpening step is dated and logged.

**Bound by the client-facing gate (docs/client-facing-gate.md):** both
claims cross to a client only through that gate; a prediction requires a
PUBLISHED cell AND every underlying signal itself gate-cleared.

**Where it lands when the gate opens:** (a) the Wave 3 subscriber dashboard
(docs/wave3-portal-design.md) gains the indicator as a first-class view next
to the watchlist, with match events feeding the same append-only event log;
(b) the Weekly Signal brief (docs/published-brief-design.md) gains a
convergence section reporting the week's risers and sharpenings, under the
same honesty rules (explicit n, CI, pending cells shown as pending). Both are
folded into those designs as banked cross-references now, built only after
the pilot proves significance and the operator approves the surface.

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
