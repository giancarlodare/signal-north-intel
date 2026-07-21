"""Tests for the MERX-Ottawa collector's pure logic: solicitation-link and
pagination detection on the listing tabs, abstract field parsing, the id-keyed
identity hash, and payload construction. The network path is exercised by a
CI dry-run, not unit-tested here."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import tenders_merx as tm
from src.filters import Keywords

KW = Keywords(general=("janitorial",), defence=("wps", "ops/"))

BASE = "https://www.merx.com/cityofottawa/solicitations/open-bids?pageNumber=1&selectedContent=BUYER"

# Both link shapes the probe saw (2026-07-20): the tabbed path and the
# buyer-6700 path, plus the Next link and decoys (disclaimer, no-id slug).
LISTING = """
<html><body>
<a href="/cityofottawa/solicitations/open-bids/PWD-PFS-Tending-and-Planting/0000327960?purchasingGroupId=1493">PWD/PFS Tending and Planting</a>
<a href="/cityofottawa/buyer-6700/solicitations/EPS-OPS-Supply-and-Deliver-Medical-Oxygen/0000325256?purchasingGroupId=1493">EPS/OPS/ Supply and Deliver Medical Oxygen and Cylinders</a>
<a href="/cityofottawa/solicitations/open-bids/PWD-PFS-Tending-and-Planting/0000327960">duplicate id link</a>
<a href="/cms-view.jsa?page=/cms/public/disclaimer">Disclaimer</a>
<a href="/cityofottawa/solicitations/open-bids?pageNumber=2&amp;selectedContent=BUYER">Next Next</a>
</body></html>
"""

ABSTRACT_TEXT = (
    "MERX City of Ottawa Solicitation Type RFT - Request for Tender "
    "Solicitation Number 19224-68051-T01 Title OPS/Breaching Kits "
    "Closing Date 2024/12/02 03:00:00 PM EST This solicitation is CLOSED "
    "Contact name purchasing officer"
)


# --- listing parsing ---------------------------------------------------------
def test_solicitation_links_both_shapes_deduped():
    links = tm.solicitation_links(LISTING, BASE)
    assert [mid for mid, _, _ in links] == ["0000327960", "0000325256"]
    assert links[0][1].startswith("https://www.merx.com/cityofottawa/solicitations/")
    assert links[1][2].startswith("EPS/OPS/")


def test_solicitation_links_ignore_non_id_links():
    links = tm.solicitation_links(LISTING, BASE)
    assert all(mid.isdigit() for mid, _, _ in links)
    assert not any("disclaimer" in url for _, url, _ in links)


def test_has_next_page_reads_the_query_not_the_text():
    assert tm.has_next_page(LISTING, BASE, "open-bids", 1) is True
    assert tm.has_next_page(LISTING, BASE, "open-bids", 2) is False
    assert tm.has_next_page(LISTING, BASE, "awarded-bids", 1) is False


# --- abstract parsing --------------------------------------------------------
def test_parse_abstract_solicitation_number_and_closing_date():
    a = tm.parse_abstract(ABSTRACT_TEXT)
    assert a["sol_num"] == "19224-68051-T01"
    assert a["closing_on"] == "2024-12-02"
    assert a["status"] == "CLOSED"


def test_parse_abstract_missing_fields_stay_none():
    # None beats a wrong date, and a reference is never fabricated.
    a = tm.parse_abstract("Some unrelated page text")
    assert a == {"sol_num": None, "closing_on": None, "status": None}


def test_parse_abstract_number_token_requires_a_digit():
    a = tm.parse_abstract("Solicitation Number Title something 2024")
    assert a["sol_num"] is None


def test_parse_abstract_title_fallback_for_unlabeled_pages():
    # IWSD-style abstracts omit the labeled field; the page title carries it
    # (CI diagnostic 2026-07-21).
    text = ("Iwsd/is/dcmb Cp000860 Shadow Ridge Sanitary Sewer Rehabilitation "
            "- 41826-91345-T05 | MERX Loading... "
            "Closing Date 2026/08/05 03:00:00 PM EDT")
    a = tm.parse_abstract(text)
    assert a["sol_num"] == "41826-91345-T05"
    assert a["closing_on"] == "2026-08-05"


def test_parse_abstract_closing_tolerates_digitless_gap():
    # The gap window is digit-free by design (it can never eat into a date),
    # which covers the observed label-to-value gaps.
    a = tm.parse_abstract("Closing Date : Amended 2026/06/11 03:00:00 PM EDT")
    assert a["closing_on"] == "2026-06-11"


def test_parse_abstract_previous_amendment_close_is_not_current():
    # The only date on this page is the PREVIOUS amendment's close; taking it
    # would record a wrong current close. None beats a wrong date.
    a = tm.parse_abstract(
        "Closing Date A - Previous Amendment 2026/06/11 03:00:00 PM EDT")
    assert a["closing_on"] is None


# --- identity hash -----------------------------------------------------------
def test_hash_keyed_on_merx_id_and_doc_type():
    # Computable from the listing alone, so known ids skip the abstract fetch.
    assert tm.merx_hash("0000327960", "tender_notice") \
        != tm.merx_hash("0000327960", "award_notice")   # lifecycle inserts fresh
    assert tm.merx_hash("0000327960", "award_notice") \
        == tm.merx_hash("0000327960", "award_notice")   # awarded/bidresults dedupe


# --- payloads ----------------------------------------------------------------
def test_payload_reference_close_date_and_defence_tag():
    a = tm.parse_abstract(ABSTRACT_TEXT)
    p = tm.build_payload("0000281771",
                         "https://www.merx.com/cityofottawa/solicitations/x/0000281771",
                         "OPS/Breaching Kits", "award_notice", a, ABSTRACT_TEXT,
                         "src-1", KW)
    assert p["reference_number"] == "19224-68051-T01"
    assert p["published_on"] == "2024-12-02"
    assert p["date_precision"] == "day"
    assert p["buyer_name"] == "City of Ottawa"
    assert p["defence_relevant"] is True    # "OPS/" is a defence keyword


def test_payload_without_closing_date_is_null():
    a = tm.parse_abstract("Solicitation Number 19224-1 no dates here")
    p = tm.build_payload("1", "u", "Title", "tender_notice", a, "body", None, KW)
    assert p["published_on"] is None
    assert p["date_precision"] is None


# --- the operator's absolute copy rule ---------------------------------------
def test_no_em_dash_in_module_source():
    path = os.path.join(os.path.dirname(__file__), "..", "src", "tenders_merx.py")
    with open(path, encoding="utf-8") as f:
        assert "—" not in f.read()
