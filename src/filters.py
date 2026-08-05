"""Keyword + category-code relevance filtering.

A notice is KEPT if either:
  - its UNSPSC code falls in a segment we always treat as in-scope
    (config.RELEVANT_UNSPSC_SEGMENTS), or
  - its title/description contains a keyword from config/keywords.txt
    (either section).

A kept notice is additionally marked defence_relevant=True if it matched
one of the dual-use defence keywords specifically.

Matching is WHOLE-WORD, case-insensitive (operator 2026-07-28): substring
matching tagged a CMHC "Default Real Estate Services" tender defence_relevant
(the same failure class as public_safety's Bendix 'ems'-in-"Systems"), and a
false defence tag flows through apply_public_safety into member-facing and
public surfaces. Precision over recall is the accepted tradeoff for the
keep-vs-skip collectors that also route through this predicate.
"""
import re
from dataclasses import dataclass

from . import config

DEFENCE_MARKER = "# ---DEFENCE---"
# Corridor vertical (operator 2026-08-05): construction/civil-works terms are
# a third pack, not additions to general. The section keeps the DOMAIN a
# dimension (construction alongside police/fire/EMS/defence), and it is what
# lets a construction-ONLY keep insert under a status the daily extraction
# pass never selects -- collection turns on with zero LLM cost.
CONSTRUCTION_MARKER = "# ---CONSTRUCTION---"


@dataclass(frozen=True)
class Keywords:
    general: tuple[str, ...]
    defence: tuple[str, ...]
    construction: tuple[str, ...] = ()


def load_keywords(path: str | None = None) -> Keywords:
    path = path or config.KEYWORDS_FILE
    general: list[str] = []
    defence: list[str] = []
    construction: list[str] = []
    target = general

    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line == DEFENCE_MARKER:
                target = defence
                continue
            if line == CONSTRUCTION_MARKER:
                target = construction
                continue
            if line.startswith("#"):
                continue
            target.append(line.lower())

    return Keywords(
        general=tuple(general),
        defence=tuple(defence),
        construction=tuple(construction),
    )


def _word_pattern(kw: str) -> re.Pattern:
    # Word-boundary guards only on edges that ARE word characters: 'ops/'
    # (the "OPS/..." Ottawa Police Service prefix) must still match with a
    # word directly after the slash, while 'uas' must not match inside
    # "quashed". Lookarounds rather than \b so the guard is one-sided.
    #
    # PLURAL TOLERANCE (operator 2026-07-28): each word token accepts an
    # optional s/es INSIDE the boundary, so 'forensic' matches "forensics"
    # and 'port of entry' matches "ports of entry" (phrases pluralize the
    # head noun, not the last word). The boundary guards are unchanged, so
    # the Bendix substring class stays closed: 'ems' still cannot match
    # inside "Systems" because the lookbehind blocks it, plural or not.
    pre = r"(?<!\w)" if re.match(r"\w", kw[:1]) else ""
    post = r"(?!\w)" if re.match(r"\w", kw[-1:]) else ""
    body = r"\s+".join(
        re.escape(tok) + r"(?:e?s)?" for tok in kw.split(" ") if tok)
    return re.compile(pre + body + post, re.IGNORECASE)


def _matches_any(text: str, keywords: tuple[str, ...]) -> str | None:
    lower = text.lower()
    for kw in keywords:
        if _word_pattern(kw).search(lower):
            return kw
    return None


def _substring_matches_any(text: str, keywords: tuple[str, ...]) -> str | None:
    """The PRE-2026-07-28 substring matcher, kept ONLY so the deterministic
    re-tag pass (src.retag_defence) can distinguish a verified false positive
    (substring hit, no whole-word hit) from a tag whose source text is not
    stored. Never call this from a collector."""
    lower = text.lower()
    for kw in keywords:
        if kw in lower:
            return kw
    return None


def unspsc_segment(unspsc_code: str) -> str | None:
    """First two digits of an 8-digit UNSPSC code (the 'segment')."""
    digits = "".join(ch for ch in (unspsc_code or "") if ch.isdigit())
    if len(digits) < 2:
        return None
    return digits[:2]


@dataclass(frozen=True)
class FilterResult:
    kept: bool
    defence_relevant: bool
    matched_keyword: str | None
    matched_unspsc_segment: str | None
    # Corridor (operator 2026-08-05): matched a construction-pack term.
    construction_relevant: bool = False
    # Kept ONLY because of the construction pack -- no core (general/defence/
    # UNSPSC) match. This is the flag the status split keys on: a document the
    # public-safety pipeline would have dropped must not enter its extraction
    # budget.
    construction_only: bool = False


# The status a collector writes for a kept document. Core keeps stay
# 'captured' (today's pipeline, byte-identical behavior). Construction-ONLY
# keeps get their own status so the daily forward pass and extract-backfill --
# both of which select status='captured' -- never see them: the Corridor
# corpus accrues at zero LLM cost until its own envelope targets this status.
# Same mechanism as the 2026-07-09 'irrelevant' quarantine; documents.status
# is unconstrained text, so no migration is involved.
CONSTRUCTION_HOLD_STATUS = "captured_construction"


def document_status(result: FilterResult) -> str:
    return CONSTRUCTION_HOLD_STATUS if result.construction_only else "captured"


def evaluate(title: str, description: str, unspsc_code: str, keywords: Keywords) -> FilterResult:
    text = f"{title} {description}"

    segment = unspsc_segment(unspsc_code)
    segment_match = segment in config.RELEVANT_UNSPSC_SEGMENTS if segment else False

    defence_match = _matches_any(text, keywords.defence)
    general_match = _matches_any(text, keywords.general)
    construction_match = _matches_any(text, keywords.construction)

    core = bool(segment_match or defence_match or general_match)
    kept = bool(core or construction_match)
    return FilterResult(
        kept=kept,
        defence_relevant=bool(defence_match),
        matched_keyword=defence_match or general_match or construction_match,
        matched_unspsc_segment=segment if segment_match else None,
        construction_relevant=bool(construction_match),
        construction_only=bool(construction_match and not core),
    )
