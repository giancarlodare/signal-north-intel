"""Tests for the Biddingo buyer-page collector (probe-derived JSON shapes).

The sample rows mirror run 30356971071's captured bidding/list/noauthorize
response for DRPS (field names verbatim)."""
import pytest

from src.tenders_biddingo import (
    BASE, bid_detail_url, build_payload, buyer_page_url, map_row,
    parse_us_date, read_bid_list)
from src.filters import Keywords


KW = Keywords(general=("police",), defence=("drone",))
BUYER = {"slug": "drps", "name": "Durham Regional Police Service"}


def jr(**over):
    row = {
        "tenderNumber": "DRPS-2026-002",
        "tenderName": "Supply and Delivery of Vehicle Towing and Storage Services",
        "bidStatus": "Awarded",
        "tenderClosingDate": "04/24/2026 02:00:00 PM",
        "tenderClosingDateTimeZone": "ET",
        "publishedDate": "03/23/2026",
        "tenderId": 41228828,
    }
    row.update(over)
    return row


def test_parse_us_date_datetime_and_bare():
    assert parse_us_date("04/24/2026 02:00:00 PM") == "2026-04-24"
    assert parse_us_date("03/23/2026") == "2026-03-23"


def test_parse_us_date_unparseable_is_none():
    assert parse_us_date("") is None
    assert parse_us_date(None) is None
    assert parse_us_date("13/40/2026") is None
    assert parse_us_date("TBD") is None


def test_map_row_awarded_is_award_notice_on_verbatim_ref():
    row = map_row(jr(), "drps", "1", "41137979")
    assert row["ref"] == "DRPS-2026-002"
    assert row["doc_type"] == "award_notice"
    assert row["url"] == f"{BASE}/drps/bid/1/41137979/41228828/verification"


def test_map_row_ref_kept_verbatim_not_reformatted():
    # The printed forms vary (space form, bare form); we normalize whitespace
    # only and never rewrite the publisher's own key.
    row = map_row(jr(tenderNumber="DRPS  2025-003"), "drps", "1", "41137979")
    assert row["ref"] == "DRPS 2025-003"
    row = map_row(jr(tenderNumber="2023-0002"), "drps", "1", "41137979")
    assert row["ref"] == "2023-0002"


def test_map_row_open_closed_unknown_are_tender_notice():
    for status in ("Open", "Closed", "Cancelled", "SomethingNew", ""):
        row = map_row(jr(bidStatus=status), "drps", "1", "41137979")
        assert row["doc_type"] == "tender_notice", status


def test_map_row_missing_tender_id_falls_back_to_buyer_page():
    row = map_row(jr(tenderId=None), "drps", "1", "41137979")
    assert row["url"] == buyer_page_url("drps")


def test_build_payload_hard_keys_reference_and_stores_closing_date():
    row = map_row(jr(), "drps", "1", "41137979")
    p = build_payload(BUYER, "src-1", row, KW)
    assert p["reference_number"] == "DRPS-2026-002"
    assert p["published_on"] == "2026-04-24"          # closing, not posted
    assert p["doc_type"] == "award_notice"
    assert p["buyer_name"] == "Durham Regional Police Service"
    assert "posted 03/23/2026" in p["content"]
    assert "closes 04/24/2026 02:00:00 PM ET" in p["content"]


def test_build_payload_hash_changes_with_status_lifecycle():
    open_row = map_row(jr(bidStatus="Open"), "drps", "1", "41137979")
    awarded = map_row(jr(), "drps", "1", "41137979")
    a = build_payload(BUYER, "src-1", open_row, KW)
    b = build_payload(BUYER, "src-1", awarded, KW)
    assert a["content_hash"] != b["content_hash"]     # lifecycle inserts fresh


def test_build_payload_closing_missing_falls_back_to_posted():
    row = map_row(jr(tenderClosingDate=""), "drps", "1", "41137979")
    p = build_payload(BUYER, "src-1", row, KW)
    assert p["published_on"] == "2026-03-23"


def test_build_payload_defence_tagging_rides_the_shared_matcher():
    row = map_row(jr(tenderName="Supply of Drone Detection Systems"),
                  "drps", "1", "41137979")
    p = build_payload(BUYER, "src-1", row, KW)
    assert p["defence_relevant"] is True


class FakeResponse:
    def __init__(self, url, status, body):
        self.url, self.status, self._body = url, status, body

    def text(self):
        return self._body


class FakePage:
    """Replays a canned response through the handler on goto(), the way
    Playwright fires response events during navigation."""

    def __init__(self, responses):
        self._responses = responses
        self._handler = None

    def on(self, _event, handler):
        self._handler = handler

    def goto(self, url, **kw):
        for r in self._responses:
            self._handler(r)

    def wait_for_timeout(self, _ms):
        pass


LIST_URL = "https://api.biddingo.com/restapi/bidding/list/noauthorize/1/41137979"


def test_read_bid_list_parses_captured_response():
    body = ('{"bidCount": 2, "bidInfoList": ['
            '{"tenderNumber": "DRPS-2026-002", "tenderId": 1},'
            '{"tenderNumber": "DRPS-2026-001", "tenderId": 2}]}')
    rows, count, sys_id, org_id = read_bid_list(
        FakePage([FakeResponse(LIST_URL, 200, body)]), "drps")
    assert (len(rows), count, sys_id, org_id) == (2, 2, "1", "41137979")


def test_read_bid_list_never_observed_raises():
    with pytest.raises(RuntimeError, match="never observed"):
        read_bid_list(FakePage([FakeResponse(
            "https://api.biddingo.com/restapi/setting/noauthorize/x", 200,
            "{}")]), "drps")


def test_read_bid_list_zero_rows_raises():
    with pytest.raises(RuntimeError, match="0 bids"):
        read_bid_list(FakePage([FakeResponse(
            LIST_URL, 200, '{"bidCount": 0, "bidInfoList": []}')]), "drps")


def test_read_bid_list_undercount_means_paging_appeared_raises():
    body = ('{"bidCount": 50, "bidInfoList": ['
            '{"tenderNumber": "DRPS-2026-002", "tenderId": 1}]}')
    with pytest.raises(RuntimeError, match="paging"):
        read_bid_list(FakePage([FakeResponse(LIST_URL, 200, body)]), "drps")


def test_read_bid_list_non_200_raises():
    with pytest.raises(RuntimeError, match="HTTP 403"):
        read_bid_list(FakePage([FakeResponse(LIST_URL, 403, "denied")]),
                      "drps")
