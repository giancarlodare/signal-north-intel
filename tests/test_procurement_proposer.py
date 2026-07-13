"""Tests for the procurement proposer's clustering (Phase A2, propose-only)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import procurement_proposer as pp


def _sig(sid, org, grade, category=None, title="", doc_title="", doc_url="",
         doc_reference=None):
    return {
        "id": sid,
        "organization_id": org,
        "evidence_grade": grade,
        "category_id": (category or {}).get("id") if category else None,
        "title": title,
        "organizations": {"canonical_name": "Toronto Police Service Board"},
        "categories": category,
        "documents": {"title": doc_title, "url": doc_url, "published_on": None,
                      "reference_number": doc_reference},
    }


CAT_BWV = {"id": "cat-1", "slug": "body_worn_video", "name": "Body-worn video"}
CAT_DRONE = {"id": "cat-2", "slug": "drones", "name": "Drones"}


def test_reference_is_conservative():
    assert pp.parse_reference("Solicitation No. ON-2026-0098") == "ON-2026-0098"
    assert pp.parse_reference("see RFP #45210-B for details") == "45210-B"
    # no explicit label, or no digit token -> nothing (avoids false hard keys)
    assert pp.parse_reference("the reference implementation") is None
    assert pp.parse_reference("body-worn cameras for police") is None
    assert pp.parse_reference("") is None
    # a too-short token is rejected: a 4-char bare number is not enough to risk
    # hard-keying unrelated signals together
    assert pp.parse_reference("RFP #4521") is None


def test_reference_is_the_hard_key_across_buyers_and_scope():
    """Two signals sharing a solicitation number are one procurement even with
    different buyers or scope text."""
    signals = [
        _sig("s1", "org-A", 4, CAT_BWV, doc_title="Tender No. GC-2026-77"),
        _sig("s2", "org-B", 5, CAT_DRONE, doc_title="award for Tender No. gc-2026-77"),
    ]
    groups = pp.cluster(signals)
    assert len(groups) == 1
    g = groups[0]
    assert g["reference_number"] == "GC-2026-77"
    assert set(g["signal_ids"]) == {"s1", "s2"}
    assert g["stage"] == 5                       # strongest rung wins


def test_structured_document_reference_is_the_hard_key():
    """The wiring that makes awards and tenders cluster: a structured
    documents.reference_number (a contract's procurement_id, a tender's
    solicitation number) is the hard key, so an award and a tender for the same
    solicitation land in ONE procurement even across buyers and categories."""
    signals = [
        # a contract award (awarded) with procurement_id D999 in the doc field
        _sig("award", "org-A", 5, CAT_DRONE, doc_reference="D999"),
        # a tender (in_market) for the same solicitation, different category text
        _sig("tender", "org-B", 4, CAT_BWV, doc_reference="D999"),
    ]
    groups = pp.cluster(signals)
    assert len(groups) == 1
    g = groups[0]
    assert g["reference_number"] == "D999"
    assert set(g["signal_ids"]) == {"award", "tender"}
    assert g["stage"] == 5


def test_structured_reference_beats_text_parse():
    """When a source provides a structured reference, it wins over any number
    that might be text-parsed from the title."""
    s = _sig("s1", "org-A", 5, CAT_BWV, doc_title="Solicitation No. ON-2026-0098",
             doc_reference="D555")
    groups = pp.cluster([s])
    assert groups[0]["reference_number"] == "D555"


def test_buyer_plus_scope_fallback_groups_and_separates():
    signals = [
        _sig("s1", "org-A", 2, CAT_BWV),
        _sig("s2", "org-A", 3, CAT_BWV),         # same buyer+scope -> same group
        _sig("s3", "org-A", 4, CAT_DRONE),       # same buyer, different scope
        _sig("s4", "org-B", 4, CAT_BWV),         # different buyer, same scope
    ]
    groups = {tuple(sorted(g["signal_ids"])): g for g in pp.cluster(signals)}
    assert ("s1", "s2") in groups
    assert ("s3",) in groups
    assert ("s4",) in groups
    assert groups[("s1", "s2")]["stage"] == 3    # commitment


def test_should_propose_thresholds():
    # a lone chatter/intent signal is not proposed
    assert pp.should_propose({"size": 1, "max_grade": 2}) is False
    # two signals is enough
    assert pp.should_propose({"size": 2, "max_grade": 1}) is True
    # a lone commitment-or-higher signal is a real opportunity on its own
    assert pp.should_propose({"size": 1, "max_grade": 3}) is True
    assert pp.should_propose({"size": 1, "max_grade": 5}) is True


def test_unresolved_buyer_signals_are_skipped():
    signals = [_sig("s1", None, 4, CAT_BWV), _sig("s2", None, 5, CAT_DRONE)]
    assert pp.cluster(signals) == []


def test_lone_weak_signal_produces_no_proposal():
    groups = pp.cluster([_sig("s1", "org-A", 1, CAT_BWV)])
    assert len(groups) == 1                       # it clusters
    assert pp.should_propose(groups[0]) is False  # but is not proposed


def test_similar_titles_do_not_merge_without_a_shared_key():
    """Fuzzy similarity is not identity: same buyer, same category text but the
    proposer keys on category, so lookalike free-text titles never force a
    merge on their own."""
    signals = [
        _sig("s1", "org-A", 3, CAT_BWV, title="body camera program phase 1"),
        _sig("s2", "org-A", 3, {"id": "cat-9", "slug": "surveillance", "name": "Surveillance"},
             title="body camera program phase 2"),
    ]
    groups = pp.cluster(signals)
    assert len(groups) == 2                       # different category -> different key
