import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pool_arcs import (
    cell_stats,
    compute_pooled,
    dl_pool,
    pooled_estimate,
    pooled_status,
    shrink,
    stratum,
)


def test_stratum_split():
    assert stratum("police_service") == "service"
    assert stratum("police_board") == "service"
    assert stratum("municipality") == "municipal"
    assert stratum(None) == "municipal"


def test_cell_stats_is_log_median():
    n, y, v = cell_stats([0, 0, 0])
    assert n == 3 and y == 0.0 and v == 1e-6   # floored, never infinite weight
    n, y, v = cell_stats([364])
    assert n == 1 and abs(y - math.log1p(364)) < 1e-9 and v is None
    # The summary is the MEDIAN: one low outlier must not crush it the way
    # it crushes a mean of logs (the first-cut 363d -> 84d failure).
    n, y, v = cell_stats([1, 363, 364, 365, 366])
    assert abs(y - math.log1p(364)) < 1e-9


def test_shrinkage_rich_cell_keeps_its_signal():
    # Precise cell (small v) far from the prior mean barely moves; a noisy
    # cell (large v) pulls toward mu.
    mu, tau2 = 5.0, 0.05
    theta_rich = shrink(6.0, 0.001, mu, tau2)
    theta_thin = shrink(6.0, 0.5, mu, tau2)
    assert abs(theta_rich - 6.0) < 0.05
    assert abs(theta_thin - 6.0) > abs(theta_rich - 6.0)
    assert theta_thin < 6.0  # pulled toward mu


def test_dl_pool_zero_spread_means_zero_tau():
    cells = [cell_stats([100, 110, 90]), cell_stats([100, 110, 90])]
    mu, tau2 = dl_pool(cells)
    assert tau2 == 0.0
    assert abs(mu - cell_stats([100, 110, 90])[1]) < 1e-9


def test_pooled_estimate_deterministic_and_median_true():
    target = [363, 364, 365, 385]           # the Peel RP flagship shape
    sibs = [[155, 744, 300], [120, 200], [400, 500, 450, 380]]
    a = pooled_estimate(target, sibs)
    b = pooled_estimate(target, sibs)
    assert a == b                            # fixed seed, same corpus
    assert a["ci_low"] <= a["median"] <= a["ci_high"]
    # A tight n=4 cell must stay recognizably near its own median, not be
    # dragged to a fraction of it by the prior.
    assert 250 <= a["median"] <= 450


def test_p2_gate():
    assert pooled_status(2, 300, 250, 350) == "prior_only"     # below local n
    assert pooled_status(4, 300, 250, 350) == "pooled_published"
    assert pooled_status(4, 300, 50, 900) == "pooled_pending"  # too wide


def test_stratum_fallback_and_no_pool():
    # One service cell (stratum group of 1 -> falls back to the flat pool of
    # 3) and a lone transition (group of 1 everywhere -> no_pool).
    cells = {
        ("svc1", 2, 3): [363, 364, 365, 385],
        ("mun1", 2, 3): [155, 300, 250],
        ("mun2", 2, 3): [120, 200, 180],
        ("svc1", 3, 5): [500, 600],
    }
    meta = {"svc1": ("Peel RP", "police_service"),
            "mun1": ("Town A", "municipality"),
            "mun2": ("Town B", "municipality")}
    rows = {(r["organization_id"], r["from_grade"], r["to_grade"]): r
            for r in compute_pooled(cells, meta)}
    flagship = rows[("svc1", 2, 3)]
    assert flagship["pooled_method"] == "eb_dl_unstratified_fallback"
    assert flagship["prior_cells"] == 3
    assert flagship["pooled"] is not None
    lone = rows[("svc1", 3, 5)]
    assert lone["pooled_status"] == "no_pool"
    assert lone["pooled"] is None
