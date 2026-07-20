"""Tests for the Weekly Signal brief generator: timing window, threshold gate,
clustering (procurement -> org -> standalone), and ranking."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import brief_generator as bg

TODAY = date(2026, 7, 15)  # a Wednesday


def _sig(sid, published_on, doc_type="award_notice", materiality=3, grade=3,
         org=None, amount=None, title="t", defence=False):
    return {"id": sid, "signal_type": "contract_award", "confidence": "confirmed",
            "materiality": materiality, "evidence_grade": grade,
            "amount_max_cad": amount, "expected_timing": None,
            "organization_id": org, "title": title,
            "organizations": {"canonical_name": org and f"Org {org}"},
            "documents": {"doc_type": doc_type, "published_on": published_on,
                          "date_precision": "day", "url": "http://x",
                          "defence_relevant": defence}}


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
    # grants are standalone action items now, so their cluster_ref is the
    # signal id; the recent award still org-clusters. Ranking is unchanged:
    # imminent first, by soonest deadline, then the recent story.
    included = [
        (_sig("recent", "2026-07-14", org="o1"), "recent"),
        (_sig("soon", "2026-08-20", doc_type="grant_program", org="o2"), "imminent"),
        (_sig("sooner", "2026-08-01", doc_type="grant_program", org="o3"), "imminent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    ranks = {c["cluster_ref"]: c["rank"] for c in clusters}
    assert ranks["sooner"] == 1   # nearest deadline first
    assert ranks["soon"] == 2     # then the later imminent
    assert ranks["o1"] == 3       # recent story last


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


def test_action_items_never_org_cluster():
    # Deadline-bearing action items (tenders, grant programs) stay separate
    # items even for the same buyer: the close date IS the story. Upstream
    # signals (board minutes) still group into one org story, and an action
    # item linked to a procurement still joins that procurement cluster.
    included = [
        (_sig("t1", "2026-08-01", doc_type="tender_notice", org="peel"), "imminent"),
        (_sig("t2", "2026-08-05", doc_type="tender_notice", org="peel"), "imminent"),
        (_sig("g1", "2026-08-20", doc_type="grant_program", org="peel"), "imminent"),
        (_sig("n1", "2026-07-14", doc_type="board_minutes", org="peel"), "recent"),
        (_sig("n2", "2026-07-14", doc_type="board_minutes", org="peel"), "recent"),
        (_sig("t3", "2026-08-06", doc_type="tender_notice", org="peel"), "imminent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={"t3": "proc9"})
    kinds = sorted((c["cluster_kind"], str(c["cluster_ref"])) for c in clusters)
    assert kinds == [("organization", "peel"),   # the two board_minutes as one story
                     ("procurement", "proc9"),   # t3 follows its procurement link
                     ("signal", "g1"),           # grant standalone, own deadline
                     ("signal", "t1"), ("signal", "t2")]  # tenders standalone
    org_cluster = next(c for c in clusters if c["cluster_kind"] == "organization")
    assert org_cluster["members"] == 2


def test_cluster_lead_is_strongest_member():
    included = [
        (_sig("weak", "2026-07-14", org="o1", grade=3, materiality=3), "recent"),
        (_sig("strong", "2026-07-14", org="o1", grade=5, materiality=4), "recent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    assert len(clusters) == 1
    assert clusters[0]["lead_signal_id"] == "strong"
    assert clusters[0]["members"] == 2


# --- relevance lens: draft-only starting selection ----------------------------
def test_lens_defaults_defence_in_and_holds_small_non_defence():
    included = [
        (_sig("d1", "2026-07-14", materiality=3, defence=True), "recent"),
        (_sig("big", "2026-07-14", materiality=4), "recent"),
        (_sig("small", "2026-07-14", materiality=3), "recent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    held = bg.apply_lens(clusters)
    by_id = {c["lead_signal_id"]: c for c in clusters}
    assert by_id["d1"]["included"] is True       # defence tag, any materiality
    assert by_id["big"]["included"] is True      # non-defence at the lens bar
    assert by_id["small"]["included"] is False   # held, recoverable in editor
    assert held == 1
    # Held clusters keep their rank: the lens sets the starting selection only.
    assert by_id["small"]["rank"] > 0


def test_lens_uses_strongest_member_materiality_not_the_lead():
    # The lead is picked grade-first, so a non-lead member can carry the
    # cluster's highest materiality; the lens must see it.
    included = [
        (_sig("lead", "2026-07-14", org="o1", grade=5, materiality=3), "recent"),
        (_sig("member", "2026-07-14", org="o1", grade=3, materiality=4), "recent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    assert len(clusters) == 1
    assert bg.apply_lens(clusters) == 0
    assert clusters[0]["included"] is True


def test_lens_defence_tag_on_any_member_spares_the_cluster():
    included = [
        (_sig("a", "2026-07-14", org="o1", grade=4, materiality=3), "recent"),
        (_sig("b", "2026-07-14", org="o1", grade=3, materiality=3, defence=True), "recent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    assert bg.apply_lens(clusters) == 0
    assert clusters[0]["included"] is True


# --- previously featured: new vs carried across published briefs --------------
def test_previously_featured_marks_signal_and_cluster_matches():
    included = [
        (_sig("s1", "2026-07-14", materiality=4), "recent"),              # same signal
        (_sig("s2", "2026-07-14", org="o1", materiality=4), "recent"),    # same org cluster
        (_sig("s3", "2026-07-14", materiality=4), "recent"),              # genuinely new
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    carried = bg.mark_previously_featured(
        clusters,
        prior_signal_ids={"s1"},
        # the org story ran last week under a different lead signal
        prior_cluster_keys={("organization", "o1")})
    by_id = {c["lead_signal_id"]: c for c in clusters}
    assert by_id["s1"]["previously_featured"] is True
    assert by_id["s2"]["previously_featured"] is True
    assert by_id["s3"]["previously_featured"] is False
    assert carried == 2


def test_previously_featured_is_display_only():
    # Marking never changes rank or the lens's included decision.
    included = [(_sig("s1", "2026-07-14", materiality=4), "recent")]
    clusters = bg.cluster(included, proc_by_signal={})
    bg.apply_lens(clusters)
    before = [(c["rank"], c["included"]) for c in clusters]
    bg.mark_previously_featured(clusters, {"s1"}, set())
    assert [(c["rank"], c["included"]) for c in clusters] == before
