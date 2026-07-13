"""Tests for the prediction-ledger helpers (Phase B)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import predictions as pd


def test_predicted_rung_must_be_commitment_or_higher():
    # commitment, in_market, awarded are valid predicted outcomes
    assert pd.is_valid_predicted_rung(3) is True
    assert pd.is_valid_predicted_rung(4) is True
    assert pd.is_valid_predicted_rung(5) is True
    # chatter and intent are never valid predicted outcomes (never a press release)
    assert pd.is_valid_predicted_rung(2) is False
    assert pd.is_valid_predicted_rung(1) is False
    assert pd.is_valid_predicted_rung(6) is False
    assert pd.is_valid_predicted_rung(None) is False


def test_default_horizon_varies_by_current_rung():
    # weaker current rung -> longer runway to advancement
    assert pd.default_horizon_months(1) == 18
    assert pd.default_horizon_months(2) == 12
    assert pd.default_horizon_months(3) == 9
    assert pd.default_horizon_months(4) == 4
    assert pd.default_horizon_months(0) == 12   # unknown -> a sane default


def test_company_level_claims_are_gated_procurement_level_not():
    assert pd.gated_for("organization_category") is True
    assert pd.gated_for("procurement") is False


def _snap(sid, grade, title="t"):
    return {"signal_id": sid, "evidence_grade": grade, "title": title,
            "document_url": f"https://ex.gc.ca/{sid}"}


def test_claim_hash_is_stable_and_order_independent():
    a = pd.claim_hash(subject_kind="procurement", subject_id="p1",
                      predicted_rung=4, horizon_months=9,
                      evidence_snapshot=[_snap("s2", 4), _snap("s1", 3)],
                      made_at="2026-07-13T00:00:00Z")
    b = pd.claim_hash(subject_kind="procurement", subject_id="p1",
                      predicted_rung=4, horizon_months=9,
                      evidence_snapshot=[_snap("s1", 3), _snap("s2", 4)],  # reordered
                      made_at="2026-07-13T00:00:00Z")
    assert a == b
    assert len(a) == 64


def test_claim_hash_binds_evidence_content_not_just_ids():
    """A later edit to a cited signal's content (its grade here) must change the
    hash, so the frozen basis cannot be retroactively altered undetectably."""
    h_low = pd.claim_hash(subject_kind="procurement", subject_id="p1",
                          predicted_rung=4, horizon_months=9,
                          evidence_snapshot=[_snap("s1", 3)],
                          made_at="2026-07-13T00:00:00Z")
    h_high = pd.claim_hash(subject_kind="procurement", subject_id="p1",
                           predicted_rung=4, horizon_months=9,
                           evidence_snapshot=[_snap("s1", 5)],   # same id, different grade
                           made_at="2026-07-13T00:00:00Z")
    assert h_low != h_high


def test_claim_hash_changes_with_any_field():
    base = dict(subject_kind="procurement", subject_id="p1", predicted_rung=4,
                horizon_months=9, evidence_snapshot=[_snap("s1", 3)],
                made_at="2026-07-13T00:00:00Z")
    h0 = pd.claim_hash(**base)
    assert pd.claim_hash(**{**base, "made_at": "2026-07-14T00:00:00Z"}) != h0
    assert pd.claim_hash(**{**base, "predicted_rung": 5}) != h0
    assert pd.claim_hash(**{**base, "evidence_snapshot": [_snap("s1", 3), _snap("s2", 4)]}) != h0
    assert pd.claim_hash(**{**base, "subject_id": "p2"}) != h0
