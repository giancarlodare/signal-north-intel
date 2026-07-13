"""Demand-strength taxonomy (Phase A1 of the prediction ledger).

Answers the market's one question on every signal: is this opportunity real,
or is it only an announcement? A deterministic five-rung grade, weakest to
strongest:

    1 chatter     announcements, opinion, political pressure, media waves
    2 intent      programs forming, commitments, reforms, funding announced
    3 commitment  budget line, capital plan, board approval, grant award
    4 in_market   RFI / pre-RFP, posted tender: a real procurement is live
    5 awarded     contract awarded: money moved on a procurement

The grade is DERIVED, never model-guessed, so it is defensible and never
drifts. It is the maximum of two lookups: the signal's own type, and a floor
set by the document it came from (an award_notice document floors at awarded
no matter what the model called the signal). Storing the result on each signal
(rather than computing on read) freezes the grade at the moment it is written,
which the immutable prediction ledger relies on.

A regrade is a NEW taxonomy version (bump TAXONOMY_VERSION) plus a fresh
backfill, never an in-place edit of this map, so history stays auditable.

Design note on grant_award: it is money moved, but it is a grant, not a
procurement contract. On the "is this procurement real" axis it is a strong
upstream leading indicator, so it grades commitment, not awarded. Grading it
awarded would falsely claim a procurement outcome.
"""

TAXONOMY_VERSION = "taxonomy@v1"

# Ordinal rungs. Kept here as the single source of truth; the migration seeds a
# reference table with the same rows for in-database display and SQL joins.
RUNGS = {
    1: "chatter",
    2: "intent",
    3: "commitment",
    4: "in_market",
    5: "awarded",
}

# signal_type -> base grade. Every value of the signals.signal_type enum is
# listed explicitly so a new enum value can never be graded by accident; an
# unmapped type falls to the conservative floor (1) and is a test failure.
SIGNAL_TYPE_GRADE = {
    # 5 awarded
    "contract_award": 5,
    # 4 in_market
    "rfi_pre_rfp": 4,
    "tender_published": 4,
    # 3 commitment: money or authority actually committed
    "budget_allocation": 3,
    "capital_plan_item": 3,
    "board_decision": 3,
    "contract_expiry": 3,      # a known renewal window is a committed re-buy
    # 2 intent: something forming, not yet committed
    "mandate_direction": 2,
    "legislative_change": 2,
    "procurement_reform": 2,
    "funding_program": 2,
    "funding_announcement": 2,
    "transfer_program": 2,
    "pilot_program": 2,
    "vehicle_refresh": 2,      # an aging-fleet timing signal, not yet budgeted
    # 1 chatter: talk, no mechanism yet
    "policy_announcement": 1,
    "election_commitment": 1,
    "political_pressure": 1,
    "media_coverage_wave": 1,
    "inquiry_recommendation": 1,
    "oversight_recommendation": 1,
    "leadership_change": 1,    # context, not demand on its own
    "vendor_activity": 1,      # context, not demand on its own
    "other": 1,
}

# doc_type -> floor grade. The document's own authority sets a floor the signal
# grade cannot fall below. Unmapped doc types floor at 1 (see grade()).
DOC_TYPE_FLOOR = {
    "award_notice": 5,     # a posted award is an awarded procurement
    "tender_notice": 4,    # a posted tender is a live procurement
    "grant_award": 3,      # money moved, but a grant (upstream) -> commitment
    "grant_program": 2,    # a program exists / opens -> intent
    "news_release": 2,     # an official announcement -> intent floor
    "board_minutes": 1,    # spans chatter..decision; signal_type carries it up
    "media_article": 1,    # coverage
}

DEFAULT_GRADE = 1


def grade(signal_type: str, doc_type: str) -> int:
    """Deterministic demand-strength grade (1..5) for a signal.

    max(signal_type grade, doc_type floor). Both default to 1 when unmapped,
    so the result is always a valid rung and never overstates demand.
    """
    st = SIGNAL_TYPE_GRADE.get(signal_type or "", DEFAULT_GRADE)
    floor = DOC_TYPE_FLOOR.get(doc_type or "", DEFAULT_GRADE)
    return max(st, floor)


def rung(grade_value: int) -> str:
    """Rung label for a stored grade, or 'ungraded' for null/out-of-range."""
    return RUNGS.get(grade_value or 0, "ungraded")
