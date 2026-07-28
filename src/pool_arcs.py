"""Partial pooling for demand-arc horizons (docs/partial-pooling-design.md,
operator approved 2026-07-28, decision points P1-P4 as recommended).

The near-cell drain experiment proved depth does not convert to per-cell
significance, so this pass is the significance route: each (organization,
transition) cell borrows strength from the population of cells measuring the
same transition. Two-level empirical Bayes on log-lags:

The pooled summary statistic is the LOG-MEDIAN, not the mean of log-lags:
the house quantity of record is the median, and the first-cut geometric-mean
version collapsed under low-outlier lags (the flagship cell's raw median 363d
pooled to 84d, an estimate no reader should ever see labeled "median").

  * per cell: y = log1p(median(lags)); within-cell uncertainty v = the
    bootstrap variance of that log-median (fixed seed). Cells at n=1 have no
    v; it is imputed as c/n where c is the group's mean of v*n (bootstrap
    median variance scales roughly as 1/n);
  * population per (transition, stratum): PAULE-MANDEL estimate of the grand
    mean mu and between-cell variance tau^2 over the cells' (y, v)
    (operator 2026-07-28: DerSimonian-Laird's truncation collapsed the first
    corpus run to complete pooling, sector averages dressed as cell figures;
    PM keeps cells' identity where heterogeneity is estimable, and at the
    tau^2 = 0 boundary the pipeline reports pool_uninformative rather than
    the sector mean). P1 strata: public-safety services and boards vs
    municipalities; a stratum with fewer than MIN_PRIOR_CELLS contributing
    cells falls back to the unstratified transition pool, labeled as such;
  * cell: precision-weighted shrinkage
      theta = w * y + (1 - w) * mu,   w = tau^2 / (tau^2 + v)
    so a data-rich cell keeps its own signal and a thin cell leans on the
    sector prior;
  * intervals: two-level bootstrap (resample sibling cells, then lags within
    cells, recomputing the whole pipeline) with a fixed seed. Deterministic:
    same corpus, same output.

Lags include legitimate 0-day observations, so the log transform is
log1p/expm1; reported pooled medians are expm1(theta).

P2 gate (two tiers, never blended): a pooled cell may publish when local
n >= MIN_LOCAL_N AND the credible half-width is <= CI_WIDTH_FRAC of the
pooled median. The unpooled n >= 8 direct-measurement gate in demand_arc is
the stricter tier and is untouched here.

P3, NON-NEGOTIABLE (operator 2026-07-28): a pooled figure NEVER appears in
the same register as a direct measurement. Every pooled number carries its
provenance label ("pooled: n=X local + sector prior (k cells)"); the
pooled_* columns exist precisely so renderers can never confuse the two.
Task #53's client_released human gate still stands ahead of any
member-visible publish; clearing P2 is statistics, not release.

Read-only analysis, no LLM. --dry-run prints the full unpooled-vs-pooled
table and writes nothing; --apply stamps the pooled_* columns onto the
LATEST demand_arc_profiles batch (idempotent: same corpus, same values).

    python -m src.pool_arcs --dry-run
    python -m src.pool_arcs --apply
"""
import argparse
import logging
import math
import random
import sys
from collections import defaultdict

from . import demand_arc, supabase_client
from .demand_arc import GRADE_LABEL, _percentile, bootstrap_median_ci, significance
from .public_safety import PUBLIC_SAFETY_ORG_TYPES

log = logging.getLogger(__name__)

MIN_LOCAL_N = 3       # P2: below this a cell never publishes as a cell
MIN_PRIOR_CELLS = 3   # P1: smallest group that counts as a usable prior
CI_WIDTH_FRAC = 0.5   # same half-width rule as the direct gate
OUTER_ITERS = 1000    # two-level bootstrap for the pooled CI
CELL_ITERS = 500      # bootstrap of the log-median for the point estimate
CELL_ITERS_FAST = 100 # ... and inside each outer iteration
BOOTSTRAP_SEED = 42


def stratum(org_type: str | None) -> str:
    """P1 strata: police services/boards (and the other public-safety org
    types) pool together; everything else pools as municipal/other."""
    return "service" if org_type in PUBLIC_SAFETY_ORG_TYPES else "municipal"


def cell_stats(lags: list, iters: int = CELL_ITERS) -> tuple:
    """(n, y, v): y = log1p(median), v = bootstrap variance of y (fixed seed;
    floored so an all-identical cell never gets infinite weight). v is None
    below n=2."""
    sv = sorted(max(0, l) for l in lags)
    n = len(sv)
    y = math.log1p(_percentile(sv, 0.5))
    if n < 2:
        return n, y, None
    rng = random.Random(BOOTSTRAP_SEED)
    ms = []
    for _ in range(iters):
        s = sorted(rng.choice(sv) for _ in range(n))
        ms.append(math.log1p(_percentile(s, 0.5)))
    mean = sum(ms) / len(ms)
    v = sum((m - mean) ** 2 for m in ms) / (len(ms) - 1)
    return n, y, max(v, 1e-6)


def _effective_vars(cells: list) -> list:
    """Per-cell v with imputation for n=1 cells: bootstrap median variance
    scales roughly as 1/n, so c = mean(v*n) over known cells and the
    imputed v is c/n."""
    known = [v * n for n, _, v in cells if v is not None]
    c = (sum(known) / len(known)) if known else 1.0
    return [max(v if v is not None else c / max(n, 1), 1e-6)
            for n, _, v in cells]


def dl_pool(cells: list) -> tuple:
    """DerSimonian-Laird over [(n, y, v), ...] -> (mu, tau2). Retained for
    reference and tests; the pipeline uses pm_pool (operator 2026-07-28:
    DL's truncation collapsed the first corpus run to complete pooling)."""
    ys = [y for _, y, _ in cells]
    vs = _effective_vars(cells)
    k = len(cells)
    if k == 1:
        return ys[0], 0.0
    w = [1.0 / v for v in vs]
    sw = sum(w)
    mu_fixed = sum(wi * y for wi, y in zip(w, ys)) / sw
    q = sum(wi * (y - mu_fixed) ** 2 for wi, y in zip(w, ys))
    denom = sw - sum(wi * wi for wi in w) / sw
    tau2 = max(0.0, (q - (k - 1)) / denom) if denom > 0 else 0.0

    w2 = [1.0 / (v + tau2) for v in vs]
    mu = sum(wi * y for wi, y in zip(w2, ys)) / sum(w2)
    return mu, tau2


def _q_at(tau2: float, ys: list, vs: list) -> tuple:
    """Generalized Q statistic and its weighted mean at a given tau2."""
    w = [1.0 / (v + tau2) for v in vs]
    mu = sum(wi * y for wi, y in zip(w, ys)) / sum(w)
    return sum(wi * (y - mu) ** 2 for wi, y in zip(w, ys)), mu


def pm_pool(cells: list) -> tuple:
    """Paule-Mandel over [(n, y, v), ...] -> (mu, tau2): bisection for the
    tau2 whose generalized Q equals its expectation k-1. Q(tau2) is
    decreasing, so the root is unique when Q(0) > k-1.

    BOUNDARY (operator 2026-07-28): when Q(0) <= k-1 the observed spread is
    already within noise and PM, like DL, returns tau2 = 0. The pipeline
    treats that as POOLING UNINFORMATIVE, never as complete pooling:
    "cannot prove services differ" is not "services are identical", so no
    cell is snapped to the sector mean. See compute_pooled."""
    ys = [y for _, y, _ in cells]
    vs = _effective_vars(cells)
    k = len(cells)
    if k == 1:
        return ys[0], 0.0
    q0, mu0 = _q_at(0.0, ys, vs)
    if q0 <= k - 1:
        return mu0, 0.0

    lo, hi = 0.0, max(vs) + 1.0
    while _q_at(hi, ys, vs)[0] > k - 1:
        hi *= 2.0
        if hi > 1e6:
            break
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _q_at(mid, ys, vs)[0] > k - 1:
            lo = mid
        else:
            hi = mid
    tau2 = (lo + hi) / 2.0
    return _q_at(tau2, ys, vs)[1], tau2


def shrink(y: float, v: float, mu: float, tau2: float) -> float:
    """The pooled cell estimate theta on the log scale. At the tau2 = 0
    boundary the cell KEEPS ITS OWN y (w = 1), never the sector mean: the
    boundary means heterogeneity is not estimable, and snapping to mu there
    is the complete-pooling overclaim the operator rejected 2026-07-28."""
    if tau2 <= 0:
        return y
    w = tau2 / (tau2 + v) if (tau2 + v) > 0 else 1.0
    return w * y + (1.0 - w) * mu


def _theta_of(target: list, siblings: list, iters: int) -> tuple:
    """(theta, tau2) for the target cell against its sibling group, PM."""
    cells = [cell_stats(ls, iters) for ls in siblings] + [cell_stats(target, iters)]
    vs = _effective_vars(cells)
    mu, tau2 = pm_pool(cells)
    return shrink(cells[-1][1], vs[-1], mu, tau2), tau2


def pooled_estimate(target_lags: list, sibling_lags: list) -> dict | None:
    """theta + two-level-bootstrap CI for one cell against its prior group.
    `sibling_lags` is a list of lag lists for the OTHER cells in the group.
    Returns day-scale {'median': int, 'ci_low': int, 'ci_high': int}, or
    None when PM lands on the tau2 = 0 boundary: pooling is uninformative
    for this group and no pooled figure exists to report."""
    point, tau2 = _theta_of(target_lags, sibling_lags, CELL_ITERS)
    if tau2 <= 0:
        return None

    rng = random.Random(BOOTSTRAP_SEED)
    thetas = []
    for _ in range(OUTER_ITERS):
        t_b = [rng.choice(target_lags) for _ in target_lags]
        # Cluster level: resample WHICH sibling cells inform the prior, then
        # within-cell: resample each chosen cell's lags.
        sibs = [sibling_lags[rng.randrange(len(sibling_lags))]
                for _ in sibling_lags] if sibling_lags else []
        s_b = [[rng.choice(ls) for _ in ls] for ls in sibs]
        thetas.append(_theta_of(t_b, s_b, CELL_ITERS_FAST)[0])
    thetas.sort()
    return {
        "median": round(math.expm1(point)),
        "ci_low": round(math.expm1(_fpercentile(thetas, 0.10))),
        "ci_high": round(math.expm1(_fpercentile(thetas, 0.90))),
    }


def _fpercentile(sorted_vals: list, p: float) -> float:
    """Interpolated percentile WITHOUT demand_arc._percentile's day-scale
    rounding; thetas live on the log scale where rounding is destructive."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def pooled_status(local_n: int, median: int, ci_low: int, ci_high: int) -> str:
    """P2 verdict for a pooled cell. 'prior_only' below MIN_LOCAL_N: the cell
    never publishes as a cell; at most the sector figure is shown, labeled."""
    if local_n < MIN_LOCAL_N:
        return "prior_only"
    half = (ci_high - ci_low) / 2.0
    if median > 0 and half <= CI_WIDTH_FRAC * median:
        return "pooled_published"
    return "pooled_pending"


def _org_meta() -> dict:
    rows = supabase_client.fetch_rows("organizations", "id,canonical_name,org_type")
    return {r["id"]: (r.get("canonical_name"), r.get("org_type")) for r in rows}


def compute_pooled(per_org_transition: dict, org_meta: dict) -> list:
    """The full unpooled-vs-pooled table, one row per cell."""
    groups_strat = defaultdict(list)   # (from, to, stratum) -> [cell keys]
    groups_flat = defaultdict(list)    # (from, to) -> [cell keys]
    for key in per_org_transition:
        org_id, g, h = key
        st = stratum((org_meta.get(org_id) or (None, None))[1])
        groups_strat[(g, h, st)].append(key)
        groups_flat[(g, h)].append(key)

    rows = []
    for key, lags in sorted(per_org_transition.items(),
                            key=lambda kv: (kv[0][1], kv[0][2], -len(kv[1]))):
        org_id, g, h = key
        name, org_type = org_meta.get(org_id) or (None, None)
        st = stratum(org_type)
        sv = sorted(lags)
        med = _percentile(sv, 0.5)
        ci_lo, ci_hi = bootstrap_median_ci(sv)

        group = groups_strat[(g, h, st)]
        method = "eb_pm_stratified"
        if len(group) < MIN_PRIOR_CELLS:
            group = groups_flat[(g, h)]
            method = "eb_pm_unstratified_fallback"

        row = {
            "organization_id": org_id, "org_name": name or "(unattributed)",
            "stratum": st, "from_grade": g, "to_grade": h,
            "n": len(sv), "median": med, "ci_low": ci_lo, "ci_high": ci_hi,
            "significance": significance(len(sv), med, ci_lo, ci_hi),
        }
        siblings = [per_org_transition[k] for k in group if k != key]
        if not siblings:
            # A group of one has no population to pool against; the pooled
            # columns stay empty rather than dressing the cell up as pooled.
            row.update({"pooled": None, "pooled_status": "no_pool",
                        "pooled_method": None, "prior_cells": 0})
        else:
            est = pooled_estimate(lags, siblings)
            if est is None:
                # PM boundary: the group's spread is within noise, so tau2
                # is not estimable. No pooled figure exists; the cell keeps
                # only its unpooled measurement. NEVER the sector mean.
                row.update({"pooled": None,
                            "pooled_status": "pool_uninformative",
                            "pooled_method": method,
                            "prior_cells": len(group)})
            else:
                row.update({
                    "pooled": est,
                    "pooled_status": pooled_status(len(sv), est["median"],
                                                   est["ci_low"], est["ci_high"]),
                    "pooled_method": method,
                    "prior_cells": len(group),
                })
        rows.append(row)
    return rows


def _report(rows: list) -> None:
    log.info("POOL-ARCS: %d cells", len(rows))
    log.info("%-34s %-22s %-9s | unpooled n/median/CI | pooled median/CI (local n + prior cells) | verdict",
             "service", "transition", "stratum")
    for r in rows:
        tr = f"{GRADE_LABEL.get(r['from_grade'], r['from_grade'])}->" \
             f"{GRADE_LABEL.get(r['to_grade'], r['to_grade'])}"
        if r["pooled"] is None and r["pooled_status"] == "pool_uninformative":
            pooled = (f"pool uninformative (tau2=0 boundary, {r['prior_cells']} "
                      f"cells: spread within noise; cell keeps its own figure)")
        elif r["pooled"] is None:
            pooled = "no pool (group of 1)"
        else:
            p = r["pooled"]
            pooled = (f"{p['median']}d CI[{p['ci_low']},{p['ci_high']}] "
                      f"(pooled: n={r['n']} local + sector prior "
                      f"({r['prior_cells']} cells), {r['pooled_method']})")
        log.info("  %-32s %-22s %-9s | n=%-3d %5sd CI[%s,%s] %s | %s | %s",
                 r["org_name"][:32], tr, r["stratum"], r["n"], r["median"],
                 r["ci_low"], r["ci_high"], r["significance"], pooled,
                 r["pooled_status"])


def run(dry_run: bool = True) -> dict:
    buyer, links = demand_arc._load_spine()
    per_org_transition, coverage = demand_arc.compute_lags(buyer, links)
    if not per_org_transition:
        raise SystemExit("pool_arcs: zero demand-arc cells computed; "
                         "refusing to report success on an empty read.")
    rows = compute_pooled(per_org_transition, _org_meta())
    _report(rows)

    written = 0
    if not dry_run:
        profiles = supabase_client.fetch_all_rows_where(
            "demand_arc_profiles",
            "id,organization_id,from_grade,to_grade,computed_at", {})
        if profiles:
            latest = max(p["computed_at"] for p in profiles)
            by_cell = {(p["organization_id"], p["from_grade"], p["to_grade"]): p["id"]
                       for p in profiles if p["computed_at"] == latest}
            for r in rows:
                if r["pooled"] is None:
                    continue
                rid = by_cell.get((r["organization_id"], r["from_grade"],
                                   r["to_grade"]))
                if not rid:
                    continue
                supabase_client.update_row("demand_arc_profiles", rid, {
                    "pooled_median_days": r["pooled"]["median"],
                    "pooled_ci_low": r["pooled"]["ci_low"],
                    "pooled_ci_high": r["pooled"]["ci_high"],
                    "pooled_local_n": r["n"],
                    "pooled_prior_cells": r["prior_cells"],
                    "pooled_method": r["pooled_method"],
                    "pooled_status": r["pooled_status"],
                })
                written += 1
        log.info("pool_arcs: stamped pooled columns on %d profile rows", written)
    else:
        log.info("pool_arcs: %d cells (DRY RUN, nothing written)", len(rows))
    return {"cells": len(rows), "written": written, **coverage}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Partial pooling over demand-arc cells")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="full table, no writes")
    group.add_argument("--apply", action="store_true",
                       help="stamp pooled_* columns on the latest profiles")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    run(dry_run=not args.apply)
    sys.exit(0)
