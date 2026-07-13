"""Prediction-ledger helpers (Phase B).

Pure functions shared by the claim-authoring UI (the predict action) and the
reconcile job, so a claim's hash, its default horizon, and its gating are
computed one way and unit-tested without a database.

Decisions encoded (docs/prediction-ledger-design.md, operator 2026-07-13):
  * A claim predicts the subject reaches a strong rung (commitment 3, in_market
    4, or awarded 5). Chatter and intent can never be a predicted outcome.
  * The default horizon varies by the subject's CURRENT rung: a weaker current
    rung gets a longer runway to advancement. The human may override.
  * Company-level (organization_category) claims are gated behind the investor
    seam; procurement-level claims are not.
  * The claim hash is a tamper-evident sha256 over the claim's identifying
    fields plus the sorted evidence ids plus the authoritative timestamp.
"""
import hashlib

# Default horizon in months by the subject's CURRENT demand rung (1..5). A
# chatter-grade subject needs the longest runway to advancement; a subject
# already in_market needs little. The human may override per claim.
DEFAULT_HORIZON_BY_RUNG = {
    1: 18,   # chatter
    2: 12,   # intent
    3: 9,    # commitment
    4: 4,    # in_market
    5: 3,    # awarded (already there; a short window for any further movement)
}

MIN_PREDICTED_RUNG = 3   # commitment; a claim must predict commitment or higher
MAX_RUNG = 5


def default_horizon_months(current_rung: int) -> int:
    """Default horizon for a subject at the given current rung."""
    return DEFAULT_HORIZON_BY_RUNG.get(current_rung, 12)


def is_valid_predicted_rung(rung: int) -> bool:
    """A predicted outcome must be commitment (3) or stronger, never a press
    release (Q4)."""
    return isinstance(rung, int) and MIN_PREDICTED_RUNG <= rung <= MAX_RUNG


def gated_for(subject_kind: str) -> bool:
    """Company-level claims are gated behind the investor seam (Q2)."""
    return subject_kind == "organization_category"


def claim_hash(*, subject_kind: str, subject_id: str, predicted_rung: int,
               horizon_months: int, evidence_signal_ids, made_at: str) -> str:
    """Tamper-evident hash of a frozen claim. Evidence ids are sorted so the
    hash is order-independent; made_at is the authoritative timestamp, so two
    otherwise-identical claims made at different times hash differently."""
    ev = ",".join(sorted(str(e) for e in (evidence_signal_ids or [])))
    canonical = "|".join([
        subject_kind or "", str(subject_id or ""), str(predicted_rung),
        str(horizon_months), ev, str(made_at or ""),
    ])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
