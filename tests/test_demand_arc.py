"""Tests for the demand-arc engine's pure logic: earliest-date-per-rung,
ladder transitions (including gaps and the intent/commitment->awarded spans),
percentiles, and per-(org, transition) aggregation. The DB read path is
exercised by a CI dry-run, not unit-tested here."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import demand_arc as da


def test_earliest_by_grade_takes_min_date_and_skips_undated():
    sigs = [
        {"evidence_grade": 2, "published_on": "2026-03-10"},
        {"evidence_grade": 2, "published_on": "2026-02-01"},   # earlier wins
        {"evidence_grade": 5, "published_on": "2026-06-01"},
        {"evidence_grade": 4, "published_on": None},           # undated: skipped
    ]
    e = da.earliest_by_grade(sigs)
    assert e == {2: "2026-02-01", 5: "2026-06-01"}


def test_transitions_consecutive_and_awarded_spans():
    # intent (2), commitment (3), awarded (5): consecutive 2->3, 3->5, plus the
    # 2->5 headline span. No fabricated 4.
    e = {2: "2026-01-01", 3: "2026-02-01", 5: "2026-04-01"}
    trs = set(da.transitions(e))
    assert (2, 3, 31) in trs        # Jan->Feb
    assert (3, 5, 59) in trs        # Feb->Apr (28+31)
    assert (2, 5, 90) in trs        # the intent->awarded horizon span
    # 3->5 is a consecutive step here, so it is not double-counted by the span
    assert len([t for t in trs if t[0] == 3 and t[1] == 5]) == 1


def test_transitions_ignores_negative_and_missing():
    assert da.transitions({}) == []
    assert da.transitions({5: "2026-01-01"}) == []   # single rung, no transition


def test_percentile_basic():
    vals = [10, 20, 30, 40]
    assert da._percentile(vals, 0.5) == 25
    assert da._percentile([42], 0.9) == 42
    assert da._percentile([], 0.5) == 0


def test_aggregate_counts_and_medians():
    per = {("org-A", 2, 5): [30, 60, 90], ("org-B", 4, 5): [10]}
    rows = {(r["organization_id"], r["from_grade"], r["to_grade"]): r
            for r in da.aggregate(per)}
    a = rows[("org-A", 2, 5)]
    assert a["n"] == 3 and a["lag_median_days"] == 60
    b = rows[("org-B", 4, 5)]
    assert b["n"] == 1 and b["lag_median_days"] == 10


def test_compute_attributes_to_buyer_and_walks():
    buyer = {"p1": "org-peel"}
    links = [
        {"procurement_id": "p1", "signals": {
            "evidence_grade": 2, "organization_id": "org-peel",
            "documents": {"published_on": "2026-01-01"}}},
        {"procurement_id": "p1", "signals": {
            "evidence_grade": 5, "organization_id": "org-peel",
            "documents": {"published_on": "2026-04-01"}}},
    ]
    profiles, coverage = da.compute(buyer, links)
    assert coverage == {"procurements": 1, "with_transition": 1}
    row = next(r for r in profiles if r["from_grade"] == 2 and r["to_grade"] == 5)
    assert row["organization_id"] == "org-peel"
    assert row["n"] == 1 and row["lag_median_days"] == 90


def test_bootstrap_ci_brackets_median_and_is_deterministic():
    lags = [30, 45, 50, 55, 60, 70, 90, 120, 150, 200]
    lo1, hi1 = da.bootstrap_median_ci(lags)
    lo2, hi2 = da.bootstrap_median_ci(lags)
    assert (lo1, hi1) == (lo2, hi2)          # fixed seed -> deterministic
    med = da._percentile(sorted(lags), 0.5)
    assert lo1 <= med <= hi1
    assert da.bootstrap_median_ci([42]) == (42, 42)
    assert da.bootstrap_median_ci([]) == (0, 0)


def test_significance_gate_min_n_and_width():
    # n below MIN_N: pending regardless of width
    assert da.significance(3, 100, 90, 110) == "pending"
    # n ok, tight CI: published (half-width 10 <= 0.5*100)
    assert da.significance(10, 100, 90, 110) == "published"
    # n ok, CI too wide: pending (half-width 80 > 50)
    assert da.significance(10, 100, 20, 180) == "pending"


def test_aggregate_carries_ci_and_verdict():
    per = {("org-A", 2, 5): [30, 60, 90]}
    row = da.aggregate(per)[0]
    assert {"ci_low", "ci_high", "significance"} <= set(row)
    assert row["significance"] == "pending"   # n=3 < MIN_N


def test_compute_falls_back_to_signal_org_when_no_buyer():
    buyer = {"p1": None}
    links = [
        {"procurement_id": "p1", "signals": {
            "evidence_grade": 4, "organization_id": "org-x",
            "documents": {"published_on": "2026-01-01"}}},
        {"procurement_id": "p1", "signals": {
            "evidence_grade": 5, "organization_id": "org-x",
            "documents": {"published_on": "2026-01-20"}}},
    ]
    profiles, _ = da.compute(buyer, links)
    assert profiles[0]["organization_id"] == "org-x"
    assert profiles[0]["lag_median_days"] == 19
