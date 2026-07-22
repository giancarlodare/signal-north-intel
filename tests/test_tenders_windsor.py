"""Tests for the Windsor open-data collector's pure logic: item segmentation
(with the phantom-header guard), date parsing, link assignment, and payload
construction (hard key, close-date-free identity hash, defence tagging). The
network path is exercised by a CI dry-run, not unit-tested here."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import tenders_windsor as tw
from src.filters import Keywords

KW = Keywords(general=("sewer",), defence=("wps", "ops/"))

# Two items shaped like the probe's ITEM SPANs (2026-07-20): the first
# extended with unofficial results, the second plain. The first item's
# description also NAMES the second item's reference without an Open: marker
# nearby, which must not split a phantom third item.
PAGE = """
<html><body>
<div>
  <h3>RFP 86-26, Retaining Wall (West) Design Services Riverside Dr E</h3>
  <p>Open: Jul 08, 2026 12:00 AM EST Close: Aug 05, 2026 11:30 AM EST (Extended)</p>
  <a href="/Tools/DownloadTender/abc-123">86-26 LETTER Retaining Wall.pdf</a>
  <a href="/Tools/Results/abc-123">View Unofficial Results</a>
  <p>Electronic bid submissions only. Related to earlier work under
     RFT 25-26, which closed previously.</p>
</div>
<div>
  <h3>RFT 92-26, WPS Collision Repair</h3>
  <p>Open: Jun 01, 2026 12:00 AM EST Close: Jun 30, 2026 11:30 AM EST</p>
  <a href="/Tools/DownloadTender/def-456">92-26 LETTER.pdf</a>
  <p>Body and paint repair services for police fleet vehicles.</p>
</div>
</body></html>
"""


def _items():
    items, markers = tw.parse_items(PAGE)
    return items, markers


# --- segmentation ------------------------------------------------------------
def test_parse_items_finds_both_items_and_no_phantom():
    items, markers = _items()
    # "RFT 25-26," inside the first description has no Open: marker of its
    # own, so it must not start a third item.
    assert [it["ref"] for it in items] == ["86-26", "92-26"]
    assert markers == 2


def test_parse_items_titles_and_prefixes():
    items, _ = _items()
    assert items[0]["prefix"] == "RFP"
    assert items[0]["title"].startswith("Retaining Wall (West)")
    assert items[1]["prefix"] == "RFT"
    assert items[1]["title"] == "WPS Collision Repair"


def test_parse_items_dates_are_close_dates():
    items, _ = _items()
    assert items[0]["open_on"] == "2026-07-08"
    assert items[0]["close_on"] == "2026-08-05"   # the (Extended) close is truth
    assert items[1]["close_on"] == "2026-06-30"


def test_parse_items_links_assigned_to_their_item():
    items, _ = _items()
    assert "/Tools/DownloadTender/abc-123" in items[0]["letter_url"]
    assert "/Tools/Results/abc-123" in items[0]["results_url"]
    assert "/Tools/DownloadTender/def-456" in items[1]["letter_url"]
    assert items[1]["results_url"] is None        # no unofficial results yet


# Header shapes the CI diagnostic surfaced (2026-07-21): no-space refs, the
# PREQUAL family (incl. the doubled PREQUAL/TENDER form), and a Notice with a
# 4-digit year.
DIAG_PAGE = """
<html><body>
<h3>RFT59-26, RESIDENTIAL MILL AND PAVE I</h3>
<p>Open: May 01, 2026 12:00 AM EST Close: May 20, 2026 11:30 AM EST</p>
<h3>PREQUAL 69-26, PEACE FOUNTAIN REPLACEMENT PROJECT</h3>
<p>Open: Apr 02, 2026 12:00 AM EST Close: Apr 30, 2026 11:30 AM EST</p>
<h3>Prequal Tender 92-26, COLLISION REPAIR SERVICES WINDSOR POLICE FLEET</h3>
<p>Open: Mar 03, 2026 12:00 AM EST Close: Mar 31, 2026 11:30 AM EST</p>
<h3>PREQUAL/TENDER 34-26 PREQUAL - TENDER 34-26, ELECTRICAL SERVICES</h3>
<p>Open: Feb 04, 2026 12:00 AM EST Close: Feb 25, 2026 11:30 AM EST</p>
<h3>PREQUALIFICATION 157-25, REPLACEMENT OF PRIVATE DRAIN CONNECTIONS</h3>
<p>Open: Jan 05, 2026 12:00 AM EST Close: Jan 28, 2026 11:30 AM EST</p>
<h3>Notice 001-2026, Enterprise Resource Planning (ERP) Solution</h3>
<p>Open: Jun 06, 2026 12:00 AM EST Close: Jun 24, 2026 11:30 AM EST</p>
</body></html>
"""


def test_parse_items_diagnostic_header_shapes():
    items, markers = tw.parse_items(DIAG_PAGE)
    assert markers == 6
    assert [it["ref"] for it in items] == \
        ["59-26", "69-26", "92-26", "34-26", "157-25", "001-2026"]
    assert all(it["close_on"] for it in items)


def test_doubled_prequal_tender_header_yields_one_item():
    items, _ = tw.parse_items(DIAG_PAGE)
    doubled = [it for it in items if it["ref"] == "34-26"]
    assert len(doubled) == 1
    assert doubled[0]["title"] == "ELECTRICAL SERVICES"


def test_windsor_police_prequal_title():
    items, _ = tw.parse_items(DIAG_PAGE)
    wps = next(it for it in items if it["ref"] == "92-26")
    assert wps["prefix"] == "Prequal Tender"
    assert wps["title"].startswith("COLLISION REPAIR SERVICES")


# --- payloads ----------------------------------------------------------------
def test_tender_payload_hard_key_and_close_date():
    items, _ = _items()
    p = tw.build_payload(items[0], "src-1", "tender_notice", KW)
    assert p["reference_number"] == "86-26"
    assert p["published_on"] == "2026-08-05"
    assert p["date_precision"] == "day"
    assert p["buyer_name"] == "City of Windsor"
    assert "/Tools/DownloadTender/abc-123" in p["url"]


def test_award_payload_uses_results_url_same_reference():
    items, _ = _items()
    p = tw.build_payload(items[0], "src-1", "award_notice", KW)
    assert p["reference_number"] == "86-26"
    assert "/Tools/Results/abc-123" in p["url"]
    # No award date is published; the close date stands (never fabricate).
    assert p["published_on"] == "2026-08-05"


def test_hash_excludes_date_but_splits_lifecycle():
    items, _ = _items()
    tender = tw.build_payload(items[0], "s", "tender_notice", KW)
    award = tw.build_payload(items[0], "s", "award_notice", KW)
    # Same reference, different rung: distinct rows.
    assert tender["content_hash"] != award["content_hash"]
    # An extended close date must find the SAME tender row (refresh in place).
    extended = dict(items[0], close_on="2026-09-01")
    assert tw.build_payload(extended, "s", "tender_notice", KW)["content_hash"] \
        == tender["content_hash"]


def test_wps_title_tags_defence_relevant():
    items, _ = _items()
    p = tw.build_payload(items[1], "s", "tender_notice", KW)
    assert p["defence_relevant"] is True


def test_missing_close_date_is_null_not_fabricated():
    items, _ = _items()
    undated = dict(items[1], close_on=None)
    p = tw.build_payload(undated, "s", "tender_notice", KW)
    assert p["published_on"] is None
    # published_on carries the null-date signal; date_precision stays a valid
    # non-null value ('day') for the NOT NULL documents column.
    assert p["date_precision"] == "day"


# --- the operator's absolute copy rule ---------------------------------------
def test_no_em_dash_in_module_source():
    path = os.path.join(os.path.dirname(__file__), "..", "src", "tenders_windsor.py")
    with open(path, encoding="utf-8") as f:
        assert "—" not in f.read()
