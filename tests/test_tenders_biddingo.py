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


class FakeRequest:
    def __init__(self, url, method="POST", post_data='{"startResult":0,"maxRow":10}'):
        self.url, self.method, self.post_data = url, method, post_data

    def all_headers(self):
        return {"content-type": "application/json;charset=UTF-8",
                ":authority": "api.biddingo.com"}


class FakeResponse:
    def __init__(self, url, status, body):
        self.url, self.status, self._body = url, status, body

    def text(self):
        return self._body

    def json(self):
        import json as _json
        return _json.loads(self._body)


class FakeRequestContext:
    """Serves canned paged replay responses; records the bodies posted."""

    def __init__(self, paged_bodies):
        self._paged = list(paged_bodies)
        self.posted = []

    def post(self, url, headers=None, data=None, timeout=None):
        self.posted.append(data)
        body = self._paged.pop(0) if self._paged else '{"bidInfoList": []}'
        return FakeResponse(url, 200, body)


class FakePage:
    """Replays canned request/response events through the handlers on goto(),
    the way Playwright fires them during navigation."""

    def __init__(self, events, paged_bodies=()):
        self._events = events
        self._handlers = {}
        self.request = FakeRequestContext(paged_bodies)

    def on(self, event, handler):
        self._handlers[event] = handler

    def goto(self, url, **kw):
        for ev in self._events:
            kind = "request" if isinstance(ev, FakeRequest) else "response"
            if kind in self._handlers:
                self._handlers[kind](ev)

    def wait_for_timeout(self, _ms):
        pass


LIST_URL = "https://api.biddingo.com/restapi/bidding/list/noauthorize/1/41137979"


def _load_events(body):
    return [FakeRequest(LIST_URL), FakeResponse(LIST_URL, 200, body)]


def test_read_bid_list_parses_captured_response():
    body = ('{"bidCount": 2, "bidInfoList": ['
            '{"tenderNumber": "DRPS-2026-002", "tenderId": 1},'
            '{"tenderNumber": "DRPS-2026-001", "tenderId": 2}]}')
    rows, count, sys_id, org_id = read_bid_list(
        FakePage(_load_events(body)), "drps")
    assert (len(rows), count, sys_id, org_id) == (2, 2, "1", "41137979")


def test_read_bid_list_pages_the_replay_until_bidcount():
    # First load returns 1 of 3 (the app's own maxRow=10 shape scaled down);
    # the paged replay serves the full portfolio, deduped on tenderId.
    body = ('{"bidCount": 3, "bidInfoList": ['
            '{"tenderNumber": "DRPS-2026-002", "tenderId": 1}]}')
    paged = [('{"bidCount": 3, "bidInfoList": ['
              '{"tenderNumber": "DRPS-2026-002", "tenderId": 1},'
              '{"tenderNumber": "DRPS-2026-001", "tenderId": 2},'
              '{"tenderNumber": "2023-0002", "tenderId": 3}]}')]
    page = FakePage(_load_events(body), paged_bodies=paged)
    rows, count, _, _ = read_bid_list(page, "drps")
    assert len(rows) == 3 and count == 3
    # The replay mutates ONLY the paging fields of the app's own body.
    import json as _json
    sent = _json.loads(page.request.posted[0])
    assert sent["maxRow"] == 100 and sent["startResult"] == 0


def test_read_bid_list_replay_still_short_raises():
    body = ('{"bidCount": 5, "bidInfoList": ['
            '{"tenderNumber": "DRPS-2026-002", "tenderId": 1}]}')
    paged = ['{"bidCount": 5, "bidInfoList": []}']
    with pytest.raises(RuntimeError, match="silently truncate"):
        read_bid_list(FakePage(_load_events(body), paged_bodies=paged),
                      "drps")


def test_read_bid_list_never_observed_raises():
    with pytest.raises(RuntimeError, match="never observed"):
        read_bid_list(FakePage([FakeResponse(
            "https://api.biddingo.com/restapi/setting/noauthorize/x", 200,
            "{}")]), "drps")


def test_read_bid_list_zero_rows_raises():
    with pytest.raises(RuntimeError, match="0 bids"):
        read_bid_list(FakePage(_load_events(
            '{"bidCount": 0, "bidInfoList": []}')), "drps")


def test_read_bid_list_non_200_raises():
    with pytest.raises(RuntimeError, match="HTTP 403"):
        read_bid_list(FakePage([FakeRequest(LIST_URL),
                                FakeResponse(LIST_URL, 403, "denied")]),
                      "drps")
