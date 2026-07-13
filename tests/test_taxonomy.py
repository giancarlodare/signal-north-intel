"""Tests for the demand-strength taxonomy (Phase A1)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import taxonomy
from src.signal_extractor import SIGNAL_TYPES, build_signal_payload


def test_every_signal_type_enum_value_is_graded_explicitly():
    """A new signal_type enum value must be graded on purpose, never fall to
    the default by omission."""
    missing = [t for t in SIGNAL_TYPES if t not in taxonomy.SIGNAL_TYPE_GRADE]
    assert missing == [], f"ungraded signal_types: {missing}"
    # and no stray keys that are not real enum values
    stray = [t for t in taxonomy.SIGNAL_TYPE_GRADE if t not in SIGNAL_TYPES]
    assert stray == [], f"unknown signal_types in map: {stray}"


def test_all_grades_are_valid_rungs():
    for g in taxonomy.SIGNAL_TYPE_GRADE.values():
        assert g in taxonomy.RUNGS
    for g in taxonomy.DOC_TYPE_FLOOR.values():
        assert g in taxonomy.RUNGS


def test_ladder_anchors():
    # weakest and strongest signal types
    assert taxonomy.grade("media_coverage_wave", "media_article") == 1
    assert taxonomy.grade("contract_award", "award_notice") == 5
    # a posted tender is in_market
    assert taxonomy.grade("tender_published", "tender_notice") == 4
    # a budget line is commitment
    assert taxonomy.grade("budget_allocation", "board_minutes") == 3


def test_doc_type_floor_raises_a_weak_signal():
    """An award_notice document floors at awarded even if the model typed the
    signal weakly."""
    assert taxonomy.grade("media_coverage_wave", "award_notice") == 5
    assert taxonomy.grade("policy_announcement", "tender_notice") == 4


def test_signal_type_raises_above_a_weak_doc_floor():
    """Board minutes floor at chatter; a real board_decision carries it up."""
    assert taxonomy.grade("board_decision", "board_minutes") == 3
    assert taxonomy.grade("media_coverage_wave", "board_minutes") == 1


def test_grant_award_is_commitment_not_awarded():
    """A grant is money moved but upstream of procurement, so it never claims
    an awarded procurement outcome."""
    assert taxonomy.grade("funding_announcement", "grant_award") == 3
    assert taxonomy.RUNGS[taxonomy.grade("funding_announcement", "grant_award")] == "commitment"


def test_unmapped_inputs_default_to_chatter_never_overstate():
    assert taxonomy.grade("some_new_type", "some_new_doc") == 1
    assert taxonomy.grade("", "") == 1
    # an unmapped signal type still gets the doc floor
    assert taxonomy.grade("some_new_type", "tender_notice") == 4


def test_rung_labels():
    assert taxonomy.rung(1) == "chatter"
    assert taxonomy.rung(5) == "awarded"
    assert taxonomy.rung(0) == "ungraded"
    assert taxonomy.rung(None) == "ungraded"


def test_build_signal_payload_carries_grade_and_version():
    raw = {"signal_type": "tender_published", "title": "T", "summary": "s",
           "confidence": "probable", "materiality": 4}
    p = build_signal_payload(raw, "doc-1", "extraction@v1",
                             lambda n: None, lambda n: None, doc_type="news_release")
    # tender_published (4) beats news_release floor (2)
    assert p["evidence_grade"] == 4
    assert p["evidence_grade_version"] == taxonomy.TAXONOMY_VERSION


def test_build_signal_payload_uses_doc_floor_when_signal_is_weak():
    raw = {"signal_type": "media_coverage_wave", "title": "T", "summary": "s"}
    p = build_signal_payload(raw, "doc-2", "extraction@v1",
                             lambda n: None, lambda n: None, doc_type="award_notice")
    assert p["evidence_grade"] == 5


def test_build_signal_payload_defaults_doc_type_none_to_chatter():
    raw = {"signal_type": "policy_announcement", "title": "T", "summary": "s"}
    p = build_signal_payload(raw, "doc-3", "extraction@v1",
                             lambda n: None, lambda n: None)
    assert p["evidence_grade"] == 1
