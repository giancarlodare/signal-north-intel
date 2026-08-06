"""Tests for the Weekly Signal brief generator: timing window, threshold gate,
clustering (procurement -> org -> standalone), and ranking."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import brief_generator as bg

TODAY = date(2026, 7, 15)  # a Wednesday


def _sig(sid, published_on, doc_type="award_notice", materiality=3, grade=3,
         org=None, amount=None, title="t", defence=False, doc_id=None,
         org_type=None, relevance=None):
    return {"id": sid, "signal_type": "contract_award", "confidence": "confirmed",
            "materiality": materiality, "evidence_grade": grade,
            "amount_max_cad": amount, "expected_timing": None,
            "organization_id": org, "title": title, "document_id": doc_id,
            "relevance": relevance,
            "organizations": {"canonical_name": org and f"Org {org}",
                              "org_type": org_type},
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


def test_future_award_uses_default_35_day_lead():
    # +35 aligns the imminent edge with the scorer curve's 21-35-day peak
    # (operator ruling 2026-08-02; +30 was excluding days 31-35).
    assert bg.timing_path("2026-08-10", TODAY, "award_notice") == "imminent"  # +26d
    assert bg.timing_path("2026-08-19", TODAY, "award_notice") == "imminent"  # +35d
    assert bg.timing_path("2026-08-20", TODAY, "award_notice") is None        # +36d > 35


def test_grants_get_a_90_day_imminent_window():
    # Grants carry the horizon a service needs to assemble an application
    # (operator ruling 2026-08-02: 45 was tight; chiefs are the segment).
    assert bg.timing_path("2026-08-24", TODAY, "grant_program") == "imminent"  # +40d
    assert bg.timing_path("2026-08-24", TODAY, "award_notice") is None
    assert bg.timing_path("2026-10-12", TODAY, "grant_program") == "imminent"  # +89d
    assert bg.timing_path("2026-10-14", TODAY, "grant_program") is None        # +91d
    assert bg.lead_days_for("grant_program") == 90
    assert bg.lead_days_for("award_notice") == 35


def test_undated_is_out_of_window():
    assert bg.timing_path(None, TODAY, "grant_program") is None


# --- recent window anchored to the last published issue ----------------------
def test_recent_window_stretches_with_recent_back():
    # A 12-day-old event is out at the 7-day floor but in when the anchor
    # says the last issue published 12 days ago: nothing skips on a late or
    # missed issue.
    assert bg.timing_path("2026-07-03", TODAY, "award_notice") is None
    assert bg.timing_path("2026-07-03", TODAY, "award_notice",
                          recent_back=12) == "recent"


def test_recent_anchor_falls_back_to_floor_without_published_issues(monkeypatch):
    monkeypatch.setattr(bg.supabase_client, "fetch_rows_where",
                        lambda *a, **k: [])
    assert bg.recent_anchor_days(TODAY) == bg.RECENT_BACK_DAYS


def test_recent_anchor_reaches_back_to_last_published_issue(monkeypatch):
    monkeypatch.setattr(bg.supabase_client, "fetch_rows_where",
                        lambda *a, **k: [{"week_start": "2026-07-03"}])
    assert bg.recent_anchor_days(TODAY) == 12


def test_recent_anchor_never_narrows_below_the_floor(monkeypatch):
    # An issue published two days ago must not SHRINK the window below 7.
    monkeypatch.setattr(bg.supabase_client, "fetch_rows_where",
                        lambda *a, **k: [{"week_start": "2026-07-13"}])
    assert bg.recent_anchor_days(TODAY) == bg.RECENT_BACK_DAYS


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


def test_weighted_score_ranks_by_actionable_window_not_soonest_deadline():
    # Weighted scoring (lens-redesign-design.md, approved 2026-08-06): timing
    # paths are no longer an absolute partition. actionable_window peaks at
    # 21-35 days, so a deadline 36 days out scores higher than one at 17 days.
    # TODAY = 2026-07-15; "soon"=2026-08-20 is 36 days out (peak ≈0.97),
    # "sooner"=2026-08-01 is 17 days out (ramp ≈0.78), both score above the
    # recent cluster (win=0.5). With all other factors equal (no relevance,
    # no org_type, single-member arcs), actionable_window decides the order.
    included = [
        (_sig("recent", "2026-07-14", org="o1"), "recent"),
        (_sig("soon", "2026-08-20", doc_type="grant_program", org="o2"), "imminent"),
        (_sig("sooner", "2026-08-01", doc_type="grant_program", org="o3"), "imminent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={}, today=date(2026, 7, 15))
    ranks = {c["cluster_ref"]: c["rank"] for c in clusters}
    assert ranks["soon"] == 1     # 36-day deadline: peak of the window curve
    assert ranks["sooner"] == 2   # 17-day deadline: rising ramp, lower than peak
    assert ranks["o1"] == 3       # recent (past-event, win=0.5): lowest here


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
    assert kinds == [("document", "g1"),         # grant: one item per program document
                     ("organization", "peel"),   # the two board_minutes as one story
                     ("procurement", "proc9"),   # t3 follows its procurement link
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
def test_lens_uses_relevance_floor_not_materiality():
    # Lens ruling 2026-08-06: admission gates on relevance >= 3, not
    # materiality or public_safety. Defence-tagged always keeps.
    # A high-materiality watermain (relevance=1) is held; a police item
    # at relevance=3 keeps; an unscored (relevance=None) item is held.
    included = [
        (_sig("d1", "2026-07-14", materiality=3, defence=True), "recent"),
        (_sig("police_rel3", "2026-07-14", materiality=2, relevance=3,
              org_type="police_board"), "recent"),
        (_sig("watermain", "2026-07-14", materiality=5, relevance=1,
              org_type="municipality", title="watermain replacement"), "recent"),
        (_sig("unscored", "2026-07-14", materiality=4), "recent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    held = bg.apply_lens(clusters)
    by_id = {c["lead_signal_id"]: c for c in clusters}
    assert by_id["d1"]["included"] is True             # defence tag always keeps
    assert by_id["police_rel3"]["included"] is True    # relevance >= floor
    assert by_id["watermain"]["included"] is False     # high materiality, low relevance: held
    assert by_id["unscored"]["included"] is False      # unscored treated as 0: held
    assert held == 2
    # Held clusters keep their rank: the lens sets the starting selection only.
    assert by_id["watermain"]["rank"] > 0
    assert by_id["unscored"]["rank"] > 0


def test_lens_uses_strongest_member_relevance_not_the_lead():
    # The lead is picked grade-first, so a non-lead member can carry the
    # cluster's highest relevance. The lens reads max_relevance across ALL
    # members, so a cluster is admitted if ANY member clears the floor.
    included = [
        (_sig("lead", "2026-07-14", org="o1", grade=5, relevance=2), "recent"),
        (_sig("member", "2026-07-14", org="o1", grade=3, relevance=4), "recent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    assert len(clusters) == 1
    assert clusters[0]["max_relevance"] == 4  # member's score, not the lead's
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


# --- grant nuance: streams from one program document are ONE item -------------
def test_grant_streams_from_one_document_cluster_as_one_item():
    # The extractor split one program page (one deadline, one application)
    # into per-stream signals; the brief must show ONE item with the streams
    # enumerated, not one item per stream.
    included = [
        (_sig("s1", "2026-09-01", doc_type="grant_program", doc_id="fire-doc",
              title="Fire Protection Grant: equipment stream"), "imminent"),
        (_sig("s2", "2026-09-01", doc_type="grant_program", doc_id="fire-doc",
              title="Fire Protection Grant: training stream", grade=2), "imminent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    assert len(clusters) == 1
    c = clusters[0]
    assert (c["cluster_kind"], c["cluster_ref"]) == ("document", "fire-doc")
    assert c["members"] == 2
    assert c["stream_titles"] == ["Fire Protection Grant: equipment stream",
                                  "Fire Protection Grant: training stream"]


def test_grant_programs_from_different_documents_stay_separate():
    included = [
        (_sig("a", "2026-09-01", doc_type="grant_program", doc_id="doc-a"), "imminent"),
        (_sig("b", "2026-08-15", doc_type="grant_program", doc_id="doc-b"), "imminent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    assert len(clusters) == 2
    assert {c["cluster_ref"] for c in clusters} == {"doc-a", "doc-b"}
    # A single-signal program carries no stream list: nothing to enumerate.
    assert all(c["stream_titles"] is None for c in clusters)


def test_tenders_from_same_buyer_remain_standalone_per_signal():
    # The nuance is grants-only: each tender is a separate bid.
    included = [
        (_sig("t1", "2026-08-01", doc_type="tender_notice", org="peel", doc_id="d1"), "imminent"),
        (_sig("t2", "2026-08-05", doc_type="tender_notice", org="peel", doc_id="d2"), "imminent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    assert {(c["cluster_kind"], c["cluster_ref"]) for c in clusters} == \
        {("signal", "t1"), ("signal", "t2")}


def test_grant_missing_document_id_degrades_to_standalone_never_wrong_merge():
    included = [
        (_sig("x", "2026-09-01", doc_type="grant_program"), "imminent"),
        (_sig("y", "2026-09-01", doc_type="grant_program"), "imminent"),
    ]
    clusters = bg.cluster(included, proc_by_signal={})
    assert len(clusters) == 2   # no shared document_id, no merge
