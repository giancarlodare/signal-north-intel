"""Tests for the bids&tenders collector's pure logic: bid-name and date parsing,
header-driven column mapping, and document payload construction (hard key,
defence tagging, dedup hash). The Playwright render path is exercised by a
dry-run from a runner, not unit-tested here."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import tenders_bidsandtenders as bt
from src.filters import Keywords

KW = Keywords(general=("watermain", "audio visual"), defence=("police", "security"))


# --- parse_bid_name ----------------------------------------------------------
def test_parse_bid_name_splits_reference_and_title():
    ref, title = bt.parse_bid_name("2026-104P - Pre-Purchase of Flow Meters, Control Panels")
    assert ref == "2026-104P"
    assert title == "Pre-Purchase of Flow Meters, Control Panels"


def test_parse_bid_name_keeps_hyphens_in_title():
    ref, title = bt.parse_bid_name("2026-353T - INTERIOR RENOVATIONS - 180 DERRY ROAD EAST")
    assert ref == "2026-353T"
    assert title == "INTERIOR RENOVATIONS - 180 DERRY ROAD EAST"  # only the first delimiter splits


def test_parse_bid_name_no_reference_is_all_title():
    ref, title = bt.parse_bid_name("Notice of intended procurement")
    assert ref is None
    assert title == "Notice of intended procurement"


# --- parse_event_date --------------------------------------------------------
def test_parse_event_date_full_datetime():
    assert bt.parse_event_date("Wed Jul 15, 2026 12:00:00 PM (EDT)") == ("2026-07-15", "day")


def test_parse_event_date_unparseable_is_none():
    # None beats a wrong date.
    assert bt.parse_event_date("Ongoing") == (None, None)
    assert bt.parse_event_date("") == (None, None)


# --- header-driven column mapping --------------------------------------------
def test_map_columns_and_col_lookup():
    idx = bt.map_columns(["Bid Name", "Bid Status", "Bid Closing Date", "Days Left"])
    row = ["2026-104P - Flow Meters", "Open", "Wed Jul 15, 2026 12:00:00 PM (EDT)", "0"]
    assert bt._col(idx, row, "bid status") == "Open"
    assert bt._col(idx, row, "bid closing date") == "Wed Jul 15, 2026 12:00:00 PM (EDT)"
    # falls through name alternatives (awarded view uses a different header)
    assert bt._col(idx, row, "award date", "bid closing date") == "Wed Jul 15, 2026 12:00:00 PM (EDT)"


# --- build_payload -----------------------------------------------------------
def _row(ref="2026-063V", title="MEETING ROOM AUDIO VISUAL", status="Open",
         date="Wed Jul 15, 2026 12:00:00 PM (EDT)", guid="ef40d844-0608-4389-ae7a-30da54cf1705"):
    return {"ref": ref, "title": title, "status": status, "date": date, "guid": guid,
            "raw": f"{ref} | {title} | {status}"}


MUNI = {"org_key": "peel", "subdomain": "peelregion", "name": "Region of Peel"}


def test_build_payload_open_tender_maps_to_in_market_doctype_and_hard_key():
    p = bt.build_payload(MUNI, "src-1", "tender_notice", _row(), KW)
    assert p["doc_type"] == "tender_notice"
    assert p["reference_number"] == "2026-063V"          # the hard key
    assert p["published_on"] == "2026-07-15"             # close date = future event
    assert p["url"].endswith("/Tender/Preview/ef40d844-0608-4389-ae7a-30da54cf1705")
    assert p["status"] == "captured"
    assert p["defence_relevant"] is False                # 'audio visual' is general, not defence


def test_build_payload_tags_defence_but_keeps_everything():
    p = bt.build_payload(MUNI, "src-1", "tender_notice",
                         _row(ref="2026-353T", title="INTERIOR RENOVATIONS FOR PEEL REGIONAL POLICE"), KW)
    assert p["defence_relevant"] is True                 # matched 'police' -> tagged, still kept
    assert p["reference_number"] == "2026-353T"


def test_build_payload_dedup_hash_changes_with_status():
    # A bid moving Open -> Awarded is a new document (the lifecycle is the signal).
    open_p = bt.build_payload(MUNI, "s", "tender_notice", _row(status="Open"), KW)
    awarded_p = bt.build_payload(MUNI, "s", "award_notice", _row(status="Awarded"), KW)
    assert open_p["content_hash"] != awarded_p["content_hash"]


def test_build_payload_no_guid_falls_back_to_portal_url():
    p = bt.build_payload(MUNI, "s", "tender_notice", _row(guid=None), KW)
    assert p["url"] == "https://peelregion.bidsandtenders.ca/Module/Tenders/en"


def test_build_payload_unparseable_date_is_null():
    p = bt.build_payload(MUNI, "s", "tender_notice", _row(date="Ongoing"), KW)
    assert p["published_on"] is None and p["date_precision"] is None
