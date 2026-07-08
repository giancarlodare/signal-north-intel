import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.vendors import extract_contract_terms, normalize_vendor_name


def test_extract_date_range_and_option_years():
    text = (
        "Contract period: 2024-04-01 to 2026-03-31, with two (2) one-year "
        "option periods to extend the contract."
    )
    terms = extract_contract_terms(text)
    assert terms.start_on == date(2024, 4, 1)
    assert terms.end_on == date(2026, 3, 31)
    assert terms.option_years == 2
    assert terms.final_end_on == date(2028, 3, 31)


def test_extract_contract_terms_with_no_recognizable_term_returns_nones():
    terms = extract_contract_terms("Standard supply agreement, no term specified.")
    assert terms.start_on is None
    assert terms.end_on is None
    assert terms.option_years is None
    assert terms.final_end_on is None


def test_normalize_vendor_name_strips_legal_suffix_and_whitespace():
    assert normalize_vendor_name("  IBM Canada   Ltd.  ") == "IBM Canada"
    assert normalize_vendor_name("Acme Corp") == "Acme"
    assert normalize_vendor_name("Solo Vendor") == "Solo Vendor"
