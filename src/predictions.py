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
    fields, the frozen evidence basis, and the authoritative timestamp.

The claim_hash here MIRRORS the database trigger predictions_freeze()
(migration 2026-07-13_prediction_hash_trigger.sql), which is what actually
computes the stored hash at insert. This function exists to INDEPENDENTLY
VERIFY a stored claim: recompute from the row and compare. The canonical form
is ASCII-only (uuids, integers, ISO-second timestamps) so Postgres, Python,
and any other verifier agree byte for byte.
"""
import hashlib
from datetime import datetime, timezone

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


def canonical_timestamp(made_at) -> str:
    """A timestamp to ISO second-precision UTC 'YYYY-MM-DDTHH:MM:SSZ', matching
    the trigger's to_char(... 'YYYY-MM-DD"T"HH24:MI:SS"Z"'). Accepts a datetime
    or an ISO string. Truncating to seconds avoids sub-second/format drift
    between what was hashed and what Postgres stores and returns."""
    if isinstance(made_at, str):
        s = made_at.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return made_at            # already canonical or unparseable; use as-is
    else:
        dt = made_at
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_evidence(evidence_snapshot) -> str:
    """The evidence basis, sorted by signal_id, as 'sid,grade,doc,pubdate'
    joined by ';'. ASCII-only and identical to the trigger's string_agg. Binds
    each cited signal's id, grade, document, and event date; the free-text
    title/summary live in the snapshot for humans but are not hashed."""
    def field(e, k):
        v = e.get(k)
        return "" if v is None else str(v)
    items = sorted((dict(e) for e in (evidence_snapshot or [])),
                   key=lambda e: field(e, "signal_id"))
    return ";".join(",".join([field(e, "signal_id"), field(e, "evidence_grade"),
                              field(e, "document_id"), field(e, "published_on")])
                    for e in items)


def claim_hash(*, subject_kind: str, subject_procurement_id=None,
               subject_organization_id=None, subject_category_id=None,
               predicted_rung: int, horizon_months: int, evidence_snapshot,
               made_at) -> str:
    """Recompute a claim's tamper-evident hash for verification, byte-identical
    to the predictions_freeze() DB trigger. Binds the subject, predicted rung,
    horizon, the frozen evidence basis, and the authoritative second-precision
    made_at, so any later edit to the claim or a cited signal's grade/document
    breaks the hash."""
    subject = ",".join([str(subject_procurement_id or ""),
                        str(subject_organization_id or ""),
                        str(subject_category_id or "")])
    canonical = "|".join([
        subject_kind or "", subject, str(predicted_rung), str(horizon_months),
        canonical_evidence(evidence_snapshot), canonical_timestamp(made_at),
    ])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
