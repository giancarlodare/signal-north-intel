"""Vendor name normalization and contract-term extraction from free text.

CanadaBuys award notice CSVs don't reliably carry clean start/end date
columns - contract length, option years, and extension terms are usually
stated in the notice's free-text description or comments field instead
(e.g. "Contract period: 2024-04-01 to 2026-03-31, with two (2) one-year
option periods"). This module extracts what it confidently can from that
text and leaves fields as None rather than guessing when it can't.
"""
import re
from dataclasses import dataclass
from datetime import date

from dateutil import parser as dateparser
from dateutil.relativedelta import relativedelta

_DATE_TOKEN = r"[A-Za-z]+\.?\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}"

_RANGE_RE = re.compile(
    rf"(?P<start>{_DATE_TOKEN})\s*(?:to|through|[-–—])\s*(?P<end>{_DATE_TOKEN})",
    re.IGNORECASE,
)

_OPTION_YEARS_RES = [
    re.compile(r"(?P<n>\d+|one|two|three|four|five)\s*(?:\(\d+\))?\s*(?:x\s*)?(?:one|1)[\s-]*year\s+option", re.IGNORECASE),
    re.compile(r"option(?:s)?\s+(?:to\s+extend\s+)?(?:for\s+)?(?:up\s+to\s+)?(?P<n>\d+|one|two|three|four|five)\s+(?:additional\s+)?year", re.IGNORECASE),
    re.compile(r"(?P<n>\d+|one|two|three|four|five)\s+one[\s-]year\s+option\s+period", re.IGNORECASE),
]

_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

_LEGAL_SUFFIXES = (
    " inc.", " inc", " ltd.", " ltd", " llc", " corp.", " corp",
    " corporation", " limited", " co.", " lp", " llp",
)


def _to_int(token: str) -> int | None:
    token = token.lower().strip()
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token)


def _safe_parse_date(token: str) -> date | None:
    try:
        return dateparser.parse(token, fuzzy=True, dayfirst=False).date()
    except (ValueError, OverflowError):
        return None


def extract_date_range(text: str) -> tuple[date | None, date | None]:
    match = _RANGE_RE.search(text or "")
    if not match:
        return None, None
    return _safe_parse_date(match.group("start")), _safe_parse_date(match.group("end"))


def extract_option_years(text: str) -> int | None:
    for pattern in _OPTION_YEARS_RES:
        match = pattern.search(text or "")
        if match:
            n = _to_int(match.group("n"))
            if n is not None:
                return n
    return None


def compute_final_end_on(end_on: date | None, option_years: int | None) -> date | None:
    if end_on is None or not option_years:
        return None
    return end_on + relativedelta(years=option_years)


@dataclass(frozen=True)
class ContractTerms:
    start_on: date | None
    end_on: date | None
    option_years: int | None
    final_end_on: date | None


def extract_contract_terms(text: str) -> ContractTerms:
    start_on, end_on = extract_date_range(text)
    option_years = extract_option_years(text)
    final_end_on = compute_final_end_on(end_on, option_years)
    return ContractTerms(
        start_on=start_on,
        end_on=end_on,
        option_years=option_years,
        final_end_on=final_end_on,
    )


def normalize_vendor_name(name: str) -> str:
    """Light normalization used only for alias comparison, not for display."""
    normalized = " ".join((name or "").strip().split())
    lowered = normalized.lower()
    for suffix in _LEGAL_SUFFIXES:
        if lowered.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
            lowered = normalized.lower()
    return normalized
