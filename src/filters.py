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


@dataclass(frozen=True)
class Keywords:
    general: tuple[str, ...]
    defence: tuple[str, ...]


def load_keywords(path: str | None = None) -> Keywords:
    path = path or config.KEYWORDS_FILE
    general: list[str] = []
    defence: list[str] = []
    in_defence_section = False

    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.strip() == DEFENCE_MARKER:
                in_defence_section = True
                continue
            if line.startswith("#"):
                continue
            target = defence if in_defence_section else general
            target.append(line.lower())

    return Keywords(general=tuple(general), defence=tuple(defence))


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


def evaluate(title: str, description: str, unspsc_code: str, keywords: Keywords) -> FilterResult:
    text = f"{title} {description}"

    segment = unspsc_segment(unspsc_code)
    segment_match = segment in config.RELEVANT_UNSPSC_SEGMENTS if segment else False

    defence_match = _matches_any(text, keywords.defence)
    general_match = _matches_any(text, keywords.general)

    kept = bool(segment_match or defence_match or general_match)
    return FilterResult(
        kept=kept,
        defence_relevant=bool(defence_match),
        matched_keyword=defence_match or general_match,
        matched_unspsc_segment=segment if segment_match else None,
    )
