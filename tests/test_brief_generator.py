"""Tests for the Weekly Signal brief generator: timing window, threshold gate,
clustering (procurement -> org -> standalone), and ranking."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import brief_generator as bg

TODAY = date(2026, 7, 15)  # a Wednesday


def _sig(sid, published_on, doc_type="award_notice", materiality=3, grade=3,
         org=None, amount=None, title="t"):
    return {"id": sid, "signal_type": "contract_award", "confidence": "confirmed",
            "materiality": materiality, "evidence_grade": grade,
            "amount_max_cad": amount, "expected_timing": None,
            "organization_id": org, "title": title,
            "organizations": {"canonical_name": org and f"Org {org}"},
            "documents": {"doc_type": doc_type, "published_on": published_on,
                          "date_precision": "day", "url": "http://x"}}


# --- timing_path: the event-date window around today --------------------------
def test_recent_event_is_path_a():
    assert bg.timing_path("2026-07-10", TODAY, "award_notice") == "recent"  # 5 days ago
    assert bg.timing_path("2026-07-15", TODAY, "award_notice") == "recent"  # today


def test_old_event_is_out_of_window():
    assert bg.timing_path("2026-06-01", TODAY, "award_notice") is None      # 6 weeks ago
    # backfill-safe: a 2024 award ingested now has a 2024 published_on
    assert bg.timing_path("2024-05-01", TODAY, "award_notice") is None


def test_future_award_uses_default_30_day_lead():
    assert bg.timing_path("2026-08-10", TODAY, "award_notice") == "imminent"  # +26d
    assert bg.timing_path("2026-08-20", TODAY, "award_notice") is None        # +36d > 30


def test_grants_get_a_45_day_imminent_window():
    # A grant deadline 40 days out is imminent (grants=45), where an award is not.
    assert bg.timing_path("2026-08-24", TODAY, "grant_program") == "imminent"  # +40d
    assert bg.timing_path("2026-08-24", TODAY, "award_notice") is None
    assert bg.lead_days_for("grant_program") == 45
    assert bg.lead_days_for("award_notice") == 30


def test_undated_is_out_of_window():
    assert bg.timing_path(None, TODAY, "grant_program") is None


# --- select: PATH-SPECIFIC threshold gate + exclusion tally ------------------
def test_recent_path_uses_full_bar():
    signals = [
        _sig("keep", "2026-07-14", materiality=3, grade=3),        # above full bar
        _sig("weakmat", "2026-07-14", materiality=2, grade=3),     # below materiality
        _sig("weakgrade", "2026-07-14", materiality=3, grade=2),   # below grade
        _sig("old", "2026-01-01", materiality=5, grade=5),         # out of window
    ]
    included, excluded, breakdown = bg.select(signals, TODAY)
    assert [s["id"] for s, _ in included] == ["keep"]
    assert excluded == 2                                            # old not counted
    assert breakdown == {"below_materiality": 1, "below_grade": 1}


def test_imminent_path_uses_relaxed_bar():
    # Path B (imminent): grade>=2 AND materiality>=2. A grant deadline in +40d.
    signals = [
        _sig("g2m2", "2026-08-24", doc_type="grant_program", materiality=2, grade=2),  # in
        _sig("g1", "2026-08-24", doc_type="grant_program", materiality=3, grade=1),    # below floor
        _sig("m1", "2026-08-24", doc_type="grant_program", materiality=1, grade=3),    # below floor
    ]
    included, excluded, breakdown = bg.select(signals, TODAY)
    assert [s["id"] for s, _ in included] == ["g2m2"]     # relaxed bar admits 2/2
    assert excluded == 2
    assert breakdown == {"below_grade": 1, "below_materiality": 1}


def test_imminent_grade2_would_fail_the_recent_bar():
    # The point of B: a 2/2 signal is admitted when imminent, excluded when
    # recent (same signal, different event date).
    imminent = _sig("x", "2026-08-24", doc_type="grant_program", materiality=2, grade=2)
    recent = _sig("x", "2026-07-14", doc_type="grant_program", materiality=2, grade=2)
    assert len(bg.select([imminent], TODAY)[0]) == 1
    assert len(bg.select([recent], TODAY)[0]) == 0


def test_bar_for_paths():
    assert bg.bar_for("recent") == (3, 3)
    assert bg.bar_for("imminent") == (2, 2)


# --- cluster: procurement > organization > standalone ------------------------
def test_clustering_prefers_procurement_then_org_then_standalone():
    included = [
        (_sig("a", "2026-07-14", org="org1"), "recent"),
        (_sig("b", "2026-07-14", org="org1"), "recent"),   # same org as a
        (_sig("c", "2026-07-14", org=None), "recent"),     # standalone
    ]
    # a is linked to a procurement; b and c are not.
    clusters = bg.cluster(included, proc_by_signal={"a": "proc1"})
    kinds = {(c["cluster_kind"], c["cluster_ref"]) for c in clusters}
    assert ("procurement", "proc1") in kinds   # a
    assert ("organization", "org1") in kinds   # b (a left the org group for its procurement)
    assert ("signal", "c") in kinds            # c standalone
    # b clustered by org, alone (a went to the procurement cluster)
    org_cluster = next(c for c in clusters if c["cluster_kind"] == "organization")
    assert org_cluster["members"] == 1


def test_imminent_clusters_rank_before_recent_and_by_soonest():
    included = [
        (_sig("recent", "2026-07-14", org="o1"), "recent"),
        (_sig("soon", "2026-08-20", doc_type="grant_program", org="o2"), "imminent"),
        (_sig("sooner", "2026-08-01", doc_type="grant_program", org="o3"), "imminent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    ranks = {c["cluster_ref"]: c["rank"] for c in clusters}
    assert ranks["o3"] == 1   # sooner imminent first
    assert ranks["o2"] == 2   # then the later imminent
    assert ranks["o1"] == 3   # recent last


# --- regen_decision: the force / published-brief safety invariant -------------
def test_regen_creates_when_no_brief_exists():
    assert bg.regen_decision(None, force=False) == "create"
    assert bg.regen_decision(None, force=True) == "create"


def test_regen_skips_existing_without_force():
    # create-if-absent: an existing brief is left alone (operator edits protected)
    assert bg.regen_decision("draft", force=False) == "skip"
    assert bg.regen_decision("published", force=False) == "skip"


def test_regen_replaces_only_a_draft_under_force():
    assert bg.regen_decision("draft", force=True) == "replace"


def test_regen_refuses_to_touch_a_published_brief_even_with_force():
    # the invariant: force NEVER deletes a published brief
    assert bg.regen_decision("published", force=True) == "refuse"


def test_cluster_lead_is_strongest_member():
    included = [
        (_sig("weak", "2026-07-14", org="o1", grade=3, materiality=3), "recent"),
        (_sig("strong", "2026-07-14", org="o1", grade=5, materiality=4), "recent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    assert len(clusters) == 1
    assert clusters[0]["lead_signal_id"] == "strong"
    assert clusters[0]["members"] == 2
