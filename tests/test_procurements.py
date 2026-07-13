"""Tests for the procurement-spine identity and stage helpers (Phase A2)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import procurements as pr


def test_reference_number_is_the_hard_key_when_present():
    # same reference, different buyer/scope -> same identity (the hard key wins)
    a = pr.procurement_identity("buyer-1", "body-worn cameras", "GC-2026-Q1-007")
    b = pr.procurement_identity("buyer-2", "different scope text", "gc-2026-q1-007  ")
    assert a == b == ("ref", "gc-2026-q1-007")


def test_reference_normalization_is_case_and_space_insensitive():
    assert pr.normalize_reference("  ON-00123  ") == "on-00123"
    assert pr.normalize_reference("on 00123") == "on 00123"
    assert pr.normalize_reference("") is None
    assert pr.normalize_reference(None) is None


def test_falls_back_to_buyer_plus_scope_when_no_reference():
    a = pr.procurement_identity("buyer-1", "Body-Worn  Cameras", None)
    b = pr.procurement_identity("buyer-1", "body-worn cameras", "")
    assert a == b == ("buyer_scope", "buyer-1", "body-worn cameras")


def test_same_scope_different_buyer_is_a_different_procurement():
    a = pr.procurement_identity("buyer-1", "drones", None)
    b = pr.procurement_identity("buyer-2", "drones", None)
    assert a != b


def test_similar_titles_do_not_collide_without_a_shared_key():
    """Fuzzy similarity is not identity: two candidates only collide on the
    hard key or on identical buyer+scope, never on lookalike titles."""
    a = pr.procurement_identity("buyer-1", "police body cameras program", None)
    b = pr.procurement_identity("buyer-1", "police body-worn camera project", None)
    assert a != b


def test_derive_stage_is_the_strongest_active_rung():
    assert pr.derive_stage([1, 3, 2]) == 3          # commitment beats chatter/intent
    assert pr.derive_stage([4, 5, 1]) == 5          # awarded
    assert pr.derive_stage([]) == 1                 # no signals yet -> chatter
    assert pr.derive_stage([None, 0, 9, 2]) == 2    # ignores out-of-range/null


def test_stage_label_reuses_the_taxonomy_rungs():
    assert pr.stage_label(1) == "chatter"
    assert pr.stage_label(4) == "in_market"
    assert pr.stage_label(5) == "awarded"
