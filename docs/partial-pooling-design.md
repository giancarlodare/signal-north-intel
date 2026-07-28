# Partial pooling for demand-arc horizons (Phase 2 design)

Status: DESIGN, awaiting operator approval. Nothing is built.
Program: coverage program Phase 2 (operator approved 2026-07-28).

## The problem this solves, and the one it does not

The near-cell drain experiment (docs/near-cell-experiment-report-2026-07-27.md)
settled the fork: extraction depth does not convert to per-cell significance.
The flagship Peel RP intent-to-commitment cell sat at n=4 with an unchanged
CI after 635 fresh signals landed in its own service. The binding constraint
is the structural rarity of linkable long-lag arcs, so no realistic drain
reaches the per-cell publication gate (n >= 8 and bootstrap CI half-width
<= 0.5 x median) cell by cell.

Partial pooling is the significance route: cells borrow strength from the
population of cells measuring the SAME transition, so a defensible interval
exists at n=3-4 local observations. It is a statistics change, not a data
change. It does NOT make thin data thick; it makes the uncertainty honest
and the estimate stable instead of leaving the cell unusable.

Standing framing (operator, locked): the fleet drain remains a coverage,
depth, and completeness investment, never a significance play. This design
does not depend on it.

## The model, concretely

Universe: the per-(organization, transition) lag lists demand_arc already
computes. Lags are right-skewed and heavy-tailed, so everything happens on
log-lags.

Two-level empirical-Bayes model on the cells' LOG-MEDIANS (build note
2026-07-28: the first cut pooled means of log-lags, i.e. geometric means,
and low-outlier lags dragged a 363d-median cell to a "pooled median" of
84d; the house quantity of record is the median, so the median is what
pools). Per cell, y = log1p(median(lags)) and v = the bootstrap variance
of that log-median.

* Population level, per transition and per stratum (see P1): grand mean mu
  and between-cell variance tau^2 from the cells' (y, v), estimated by
  PAULE-MANDEL (build note 2026-07-28, second correction: the first corpus
  run used DerSimonian-Laird, whose truncation collapsed every group to
  tau^2 = 0, complete pooling, sector averages dressed as cell figures;
  operator rejected that as the overclaim this design exists to avoid).
  BOUNDARY RULE: when even PM lands at tau^2 = 0, heterogeneity is not
  estimable and the pass reports pool_uninformative for the group's cells;
  a cell keeps its own unpooled figure and is never snapped to the sector
  mean, because "cannot prove services differ" is not "services are
  identical" (operator 2026-07-28).
* Cell level: the pooled cell estimate is the precision-weighted blend
    theta_cell = w x y_cell + (1 - w) x mu,
    w = tau^2 / (tau^2 + v_cell)
  which is the classic shrinkage estimator: a cell with rich local data
  keeps its own signal (w near 1); a thin cell leans on the sector prior
  (w near 0). Reported medians are exp(theta), back on the day scale.
* Intervals: parametric bootstrap over both levels with a fixed seed
  (same discipline as bootstrap_median_ci), reported as a credible
  interval on the day scale. Deterministic runs: same corpus, same output.

No new dependencies, no MCMC, no LLM calls: pure Python like demand_arc.
Compute cost is nil; the only spend is my build time.

## Decision points for the operator (recommendations first)

* **P1, pooling strata.** Recommend: pool within a transition ACROSS
  organizations, stratified by org class (police services and boards in one
  stratum; municipalities in another). Alternative: one unstratified pool
  per transition, which is simpler but lets municipal rhythm contaminate
  police-board rhythm. The stratified run degrades gracefully: a stratum
  with fewer than 3 contributing cells falls back to the unstratified pool
  for its prior, labeled as such.
* **P2, publication gate for pooled cells.** Recommend: a pooled cell may
  publish when local n >= 3 AND the pooled credible interval half-width is
  <= 0.5 x the pooled median. Below local n=3 a cell never publishes as a
  cell: at most the sector prior itself is shown, labeled as a sector
  figure, not a cell figure. The existing per-cell gate (n >= 8 unpooled)
  stays as the stricter tier: a cell that clears it publishes as a direct
  measurement with no prior in the number.
* **P3, honesty labels.** Every pooled figure carries its provenance:
  "pooled: n=4 local observations + sector prior (k cells)". A pooled
  number is never displayed in the same visual register as a direct
  measurement without the label. This is the same discipline as
  date_precision: the reader always knows what kind of number they hold.
* **P4, where results live.** Recommend: new nullable columns on
  demand_arc_profiles (pooled_median_days, pooled_ci_low, pooled_ci_high,
  pooled_local_n, pooled_prior_cells, pooled_method) written by a separate
  read-only pass, src/pool_arcs.py, run weekly after demand_arc. Keeps one
  table of record; the unpooled columns stay untouched, so the direct
  measurements remain auditable next to the pooled view.

## What ships on approval

1. src/pool_arcs.py: pure estimator functions plus a --dry-run/--apply
   runner in the house pattern (loud failure on an empty read, idempotent
   writes of diffs only).
2. Tests on the pure functions: shrinkage weights, stratum fallback,
   determinism, and a fixture reproducing the Peel RP n=4 cell to show the
   before/after.
3. A migration adding the P4 columns (paste-ready, guarded, idempotent).
4. A dry-run report over the real corpus: every cell's unpooled vs pooled
   median and interval, which cells newly clear the P2 gate, and which
   stay unpublishable. That report comes to you BEFORE the apply run and
   before anything is wired into the weekly job.

Gate reminder: task #53 (client_released hard gate) still stands ahead of
any member-visible demand-arc publication; pooling changes the estimator,
not the release gate.
