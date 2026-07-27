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
- The rollup aggregates WITHIN a track (section 0e): political-signal-fed
  and operational-signal-fed arcs under the same ministry never blend into
  one ministry number.
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

**Flagship visualization (banked):** the interactive prediction pathway
(docs/wave3-portal-design.md), a click-to-expand timeline of the
reconstructed arc with the measured rhythm above it and the projection as
a widening CI cone. Strictly downstream of this engine: it renders only
verified arcs and PUBLISHED cells.

**Where it lands when the gate opens:** (a) the Wave 3 subscriber dashboard
(docs/wave3-portal-design.md) gains the indicator as a first-class view next
to the watchlist, with match events feeding the same append-only event log;
(b) the Weekly Signal brief (docs/published-brief-design.md) gains a
convergence section reporting the week's risers and sharpenings, under the
same honesty rules (explicit n, CI, pending cells shown as pending). Both are
folded into those designs as banked cross-references now, built only after
the pilot proves significance and the operator approves the surface.

## 0e. Terminal-action profiles keyed to the arc's nature, not the entity (operator, 2026-07-26)

Status: BANKED, design-only. Folds into the engine's aggregation; gated on
the pilot like the rest of section 0. (The per-buyer terminal-action profile
had lived only in discussion until now; this section records the concept and
its correction together, with the keying right from the start.)

**The profile.** For each buyer, the engine learns what its arcs TERMINATE
in (grant, procurement/tender, legislation, program change) and at what
rhythm. This is what the convergence indicator's progressive sharpening
(section 0d) reads: the sharpened instrument is the terminal action the
buyer's measured history says this kind of arc ends in.

**The correction: key on the ARC'S NATURE, not just the entity name.** One
entity can host multiple distinct arc types, and averaging them produces a
blended muddy number that predicts neither. SOLGEN is the proof, with TWO
separate predictive tracks that must never be averaged together:

1. **SOLGEN-as-ministry (the minister's own actions).** Politically driven.
   Fed by POLITICAL signals: Hansard, premier and minister statements,
   budget priorities. Terminates in GRANTS and LEGISLATION.
2. **SOLGEN-as-procurement-channel (operational buying flowing through it,
   including the OPP).** Operationally driven. Fed by OPERATIONAL signals:
   capacity needs, capital plans, equipment cycles. Terminates in
   PROCUREMENT.

Same entity, two arcs, two rhythms, two terminal profiles. A prediction
therefore reads "SOLGEN ministry track -> grant likely in ~N months" or
"SOLGEN/OPP operational track -> procurement likely in ~M months", never a
blend of the two.

**Design consequences (for the engine, when the pilot gate opens):**

- The profile key is (buyer, TRACK), where the track is classified from the
  NATURE of the feeding signals (political-signal-fed vs
  operational-signal-fed), not from the entity name. Most municipal buyers
  have one track; an entity hosting more than one gets one profile per
  track.
- Aggregation, the bootstrap CI, and the significance gate all apply PER
  TRACK: each track has its own n and its own CI. A thin track is pending
  on its own merits; tracks are never merged to reach N_MIN, because a
  merged n would be confidence manufactured from two different processes.
- The ministry rollup (section 0a) inherits the same rule: a ministry row
  aggregates arcs within a track, so SOLGEN's political rhythm and the
  operational rhythm of services under it never blend in the rollup either.
- Track classification follows the standing discipline: proposed from the
  signal mix, operator-confirmable, never silently guessed where the mix is
  ambiguous.

## 0f. Domain rhythms vs traced arcs (operator doctrine, 2026-07-26)

The pilot's first staging measured arc-linking difficulty directly: zero
cross-rung links formed on a hard key (board documents never quote tender
references), so every cross-rung cluster stood on the coarse buyer+scope
basis. The operator's linking doctrine, from that finding:

1. **Domain-thread linking (Option 1) is the pilot's rhythm instrument, and
   its output is RENAMED accordingly.** What it produces are DOMAIN RHYTHMS
   ("TPS fleet-domain budget->award lag ~X months"), never specific causal
   arcs. Every output, significance verdict, and label downstream says
   domain-rhythm measurement; the word "arc" is reserved for traced chains.
2. **Traced arcs require per-instrument accuracy (Option 2) and are
   deferred.** Anything client-facing that shows a traced chain (the
   interactive prediction pathway, any Claim-1 prediction) REQUIRES
   Option-2 per-instrument reconstruction. Banked as the mandatory
   approach; domain rhythms never masquerade as traced chains.
3. **Coherence before measurement.** A domain thread only measures rhythm
   if the cluster is a coherent domain: clusters mixing distinct
   instruments are split before confirmation, and advocacy / pressure
   signals NEVER link to a specific award at any granularity (a fabricated
   link). Pressure feeds rung 1 as a domain-pressure indicator only.
   Uncategorized-scope clusters are incoherent by construction and are
   excluded until categorized.

## 0h. Actor-vs-publisher attribution (banked design question, operator 2026-07-27)

The corpus contamination audit (correctness gap, R3) surfaced a distinction
to RESOLVE AS WE SCALE, not now: when a board agenda discusses ANOTHER
entity's business (a Greater Sudbury board agenda summarizing a SOLGEN budget
consultation, an OPP-managed tool, a City of Mississauga service contract),
the extractor correctly attributes the signal to the ACTOR (SOLGEN, OPP,
Mississauga), not the publishing board. That actor attribution is right. The
open question is what the signal means for DEMAND RHYTHM:

- Option A: it feeds the OTHER entity's demand rhythm (a real SOLGEN signal,
  wherever it was published).
- Option B: it is AMBIENT DISCUSSION in the board's own rhythm (the board
  noting external context, not the actor's own procurement intent).

The two are not always the same: a board minute recording that SOLGEN
announced funding is weaker evidence of SOLGEN's procurement demand than
SOLGEN's own budget document would be. Getting this wrong either inflates an
entity's rhythm with second-hand mentions or drops real cross-published
signal. Decide the rule (likely: keep the actor attribution but weight/flag
second-hand mentions by publisher distance) when the multi-entity corpus is
large enough to measure the effect. Banked; not solved now. Only the one true
mis-attribution (751bc4fb, WRPS demand filed under Peel) is fixed in this
pass.

## 0g. Confirmation pairs vs long-lag observations (operator doctrine, 2026-07-27)

The pilot's first confirm pass surfaced a distinction the engine MUST
report, or it will mistake n-growth for predictive power. Two kinds of
transition observation carry very different value:

- **CONFIRMATION PAIRS (~0-day, arc-validating).** A board approves an
  item in the SAME meeting (or same document) where it appears, so the
  agenda->minutes or same-document pair measures a near-zero lag. These
  are REAL links and they grow n, but they carry NO predictive lead time.
  They validate that the arc machinery works; they do not feed a sellable
  prediction.
- **LONG-LAG OBSERVATIONS (the sellable signal).** A transition measured
  ACROSS separate documents over real calendar time (a budget line in one
  cycle, an award in a later one; a grant receipt and its later
  program conclusion). These carry the 6-18 month lead time the product
  sells on.

Board documents are RICH in confirmation pairs and THIN in long-lag arcs;
the long lags live in budget-to-award spans (the rhythm groups) and in
cross-document instrument threads (the T4 "Countering Hate" shape). The
engine therefore reports the two SEPARATELY: a cell's n is split into
(confirmation_n, longlag_n), and the significance gate and any published
horizon are computed on the LONG-LAG observations only. A cell rich in
0-day pairs but empty of long-lag spans is honestly "pending" no matter
how high its raw n. Never let confirmation-pair volume dress a cell as
predictive.

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
