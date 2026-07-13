"""Procurement-spine helpers (Phase A2).

Pure functions shared by the proposer (next PR) and the review app: how a
procurement's identity is keyed, and how its stage is derived. No I/O, so both
sides compute identity and stage the same way and both are unit-tested without
a database.

Identity (operator decision Q5, 2026-07-13): keyed on resolved buyer plus
scope plus reference-number WHERE PRESENT, human-confirmed, never auto-merged
on fuzzy match. A reference number is the hard key when present; buyer plus
scope is the proposal basis when it is absent. Fuzzy title similarity (not
here) only ranks candidates for the reviewer and merges nothing.

Stage mirrors the demand-strength ladder (src/taxonomy): a procurement's stage
is the strongest rung any of its active signals has reached.
"""
from typing import Optional

from . import taxonomy


def normalize_reference(reference_number: Optional[str]) -> Optional[str]:
    """Canonical form of a reference number for matching: collapse whitespace,
    lowercase. Mirrors the migration's `lower(reference_number)` unique index,
    so Python-side identity and the DB constraint agree. None/blank -> None."""
    if not reference_number:
        return None
    collapsed = " ".join(reference_number.split()).lower()
    return collapsed or None


def normalize_scope(scope: Optional[str]) -> str:
    """Canonical scope text for the buyer+scope fallback key."""
    return " ".join((scope or "").split()).lower()


def procurement_identity(buyer_organization_id: Optional[str],
                         scope: Optional[str],
                         reference_number: Optional[str]) -> tuple:
    """A hashable identity key for a candidate procurement.

    ('ref', <normalized reference>) when a reference number is present: the
    hard key, one procurement per reference. Otherwise
    ('buyer_scope', <buyer id>, <normalized scope>): the human-reviewed
    proposal basis. Two candidates sharing a key are the SAME procurement;
    candidates that only look similar by title never collide here (fuzzy
    matching is a ranking hint for the reviewer, not an identity).
    """
    ref = normalize_reference(reference_number)
    if ref:
        return ("ref", ref)
    return ("buyer_scope", buyer_organization_id, normalize_scope(scope))


def derive_stage(evidence_grades) -> int:
    """A procurement's current stage: the strongest rung among its active
    signals (1..5), or 1 when it has none yet. Never exceeds the ladder."""
    grades = [g for g in evidence_grades if isinstance(g, int) and 1 <= g <= 5]
    return max(grades) if grades else 1


def stage_label(stage: int) -> str:
    """Human label for a stage, reusing the taxonomy rungs."""
    return taxonomy.rung(stage)
