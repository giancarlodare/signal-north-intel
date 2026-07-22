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


# --- doubled-cell dedupe -----------------------------------------------------
def test_dedupe_phrase_collapses_fuelux_doubled_header():
    # The repeater nests a heading div, so each header cell's innerText doubles.
    assert bt.dedupe_phrase("Bid Name Bid Name") == "Bid Name"
    assert bt.dedupe_phrase("Bid Closing Date Bid Closing Date") == "Bid Closing Date"


def test_dedupe_phrase_leaves_non_doubled_untouched():
    assert bt.dedupe_phrase("2026-104P - Flow Meters") == "2026-104P - Flow Meters"
    assert bt.dedupe_phrase("Open") == "Open"
    assert bt.dedupe_phrase("") == ""


# --- header-driven column mapping --------------------------------------------
def test_map_columns_and_col_lookup():
    idx = bt.map_columns(["Bid Name", "Bid Status", "Bid Closing Date", "Days Left"])
    row = ["2026-104P - Flow Meters", "Open", "Wed Jul 15, 2026 12:00:00 PM (EDT)", "0"]
    assert bt._col(idx, row, "bid status") == "Open"
    assert bt._col(idx, row, "bid closing date") == "Wed Jul 15, 2026 12:00:00 PM (EDT)"
    # falls through name alternatives (awarded view uses a different header)
    assert bt._col(idx, row, "award date", "bid closing date") == "Wed Jul 15, 2026 12:00:00 PM (EDT)"


def test_map_columns_handles_doubled_headers():
    # The exact failure that produced 0 rows: doubled header text broke lookup.
    idx = bt.map_columns(["Bid Name Bid Name", "Bid Status Bid Status",
                          "Bid Closing Date Bid Closing Date", "Days Left Days Left"])
    row = ["2026-104P - Flow Meters", "Open", "Wed Jul 15, 2026 12:00:00 PM (EDT)", "0"]
    assert bt._col(idx, row, "bid name") == "2026-104P - Flow Meters"
    assert bt._col(idx, row, "bid status") == "Open"
    assert bt._col(idx, row, "bid closing date") == "Wed Jul 15, 2026 12:00:00 PM (EDT)"


def test_col_substring_fallback_tolerates_header_drift():
    idx = bt.map_columns(["Bid Name", "Status", "Awarded Date"])
    row = ["2026-104P - Flow Meters", "Awarded", "Mon Jun 30, 2026"]
    # 'award date' is not an exact header, but 'award date' is a substring miss;
    # 'awarded date' resolves, and the fallback finds 'status' inside itself.
    assert bt._col(idx, row, "awarded date") == "Mon Jun 30, 2026"
    assert bt._col(idx, row, "bid status", "status") == "Awarded"


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
    # published_on carries the null-date signal; date_precision stays a valid
    # non-null value ('day') for the NOT NULL documents column.
    assert p["published_on"] is None and p["date_precision"] == "day"


# --- Method-B awarded ---------------------------------------------------------
def _awarded_json(ref="2017-695N", title=None, status="Awarded",
                  closed="Mon Nov 27, 2017 12:00:00 PM"):
    return {
        "Id": "865bca1b-a51f-4f85-9721-71c22bb0079b",
        "Title": title if title is not None else f"{ref} - Provision of a Public Safety LTE System",
        "Scope": "Prequalification", "Status": status,
        "Description": "Provision of a Public Safety LTE System",
        "DateClosingDisplay": closed,
        "VendorIsRegistered": "False",  # about the viewer, NOT the winning vendor
    }


def test_awarded_row_from_json_pulls_reference_from_title():
    row = bt.awarded_row_from_json(_awarded_json())
    assert row["ref"] == "2017-695N"                       # hard key from Title
    assert row["title"].startswith("Provision of a Public Safety")
    assert row["status"] == "Awarded"
    assert row["guid"] == "865bca1b-a51f-4f85-9721-71c22bb0079b"


def test_awarded_row_builds_award_notice_payload_on_hard_key():
    row = bt.awarded_row_from_json(_awarded_json(ref="2017-711T"))
    p = bt.build_payload(MUNI, "s", "award_notice", row, KW)
    assert p["doc_type"] == "award_notice"
    assert p["reference_number"] == "2017-711T"            # links to the tender
    assert p["published_on"] == "2017-11-27"               # closing date (best available)
    assert p["url"].endswith("/Tender/Preview/865bca1b-a51f-4f85-9721-71c22bb0079b")


def test_awarded_row_untitled_ref_is_none():
    # A row whose Title carries no reference is not a keyable awarded bid.
    row = bt.awarded_row_from_json(_awarded_json(title="Notice to vendors"))
    assert row["ref"] is None


def test_status_query_url_swaps_status_and_paging_keeps_sort():
    base = ("https://peelregion.bidsandtenders.ca/Module/Tenders/en/Tender/Search/"
            "246c4240-574b-42fa-a0dd-0ab49d3f4f5a?status=Open&limit=25&start=0"
            "&dir=ASC&from=&to=&sort=DateClosing+ASC,Id")
    u = bt.status_query_url(base, "Awarded", 100, 200)
    assert "status=Awarded" in u
    assert "limit=100" in u and "start=200" in u
    assert "sort=DateClosing" in u and "dir=ASC" in u     # other params preserved


# --- awarded backfill resilience ---------------------------------------------
import pytest  # noqa: E402


def _awarded_rows(n):
    return [{"Id": f"guid{i}", "Title": f"2020-{i:03d}T - Thing {i}", "Status": "Awarded",
             "Description": "x", "DateClosingDisplay": "Mon Nov 27, 2017 12:00:00 PM"}
            for i in range(n)]


class _Resp:
    def __init__(self, data, total):
        self._data, self._total, self.status = data, total, 200

    def json(self):
        return {"data": self._data, "total": self._total}


class _Page:
    """Minimal Playwright-page stand-in: one awarded page, then empty."""
    def __init__(self, rows):
        self._rows, self.calls = rows, 0

        class _Req:
            def post(inner, url, headers=None, data=None, timeout=None):
                self.calls += 1
                return _Resp(self._rows, len(self._rows)) if self.calls == 1 \
                    else _Resp([], len(self._rows))
        self.request = _Req()


_CAP = {"url": "https://x/Module/Tenders/en/Tender/Search/" + ("a" * 36)
        + "?status=Open&limit=25&start=0", "headers": {}, "post_data": ""}


def test_fetch_awarded_tolerates_transient_row_failures(monkeypatch):
    monkeypatch.setattr(bt.supabase_client, "get_document_by_hash", lambda h: None)
    n = {"i": 0}

    def flaky_insert(payload):
        n["i"] += 1
        if n["i"] <= 5:
            raise RuntimeError("transient blip")
        return {}
    monkeypatch.setattr(bt.supabase_client, "insert_document", flaky_insert)
    stats = {"read": 0, "inserted": 0, "skipped_duplicate": 0, "errors": 0}
    read = bt.fetch_awarded(_Page(_awarded_rows(30)), _CAP, MUNI, "s", KW, stats, dry_run=False)
    assert read == 30              # every row attempted, none lost to an early abort
    assert stats["errors"] == 5    # 5 transient failures tolerated
    assert stats["inserted"] == 25 # the rest inserted


def test_fetch_awarded_fails_loud_over_error_budget(monkeypatch):
    monkeypatch.setattr(bt.supabase_client, "get_document_by_hash", lambda h: None)

    def always_fail(payload):
        raise RuntimeError("systemic")
    monkeypatch.setattr(bt.supabase_client, "insert_document", always_fail)
    stats = {"read": 0, "inserted": 0, "skipped_duplicate": 0, "errors": 0}
    with pytest.raises(RuntimeError, match="error budget"):
        bt.fetch_awarded(_Page(_awarded_rows(40)), _CAP, MUNI, "s", KW, stats, dry_run=False)
    assert stats["errors"] > bt.AWARDED_ERROR_BUDGET


# --- Big 12 tier 1 (docs/big12-tier1-design.md) -------------------------------
def test_tier1_config_rows_are_enabled_and_drps_is_not():
    keys = [m["org_key"] for m in bt.MUNICIPALITIES]
    assert keys == ["peel", "york", "london", "durham", "yrp"]
    assert "drps" not in keys                      # HELD on provenance
    subs = [m["subdomain"] for m in bt.MUNICIPALITIES]
    assert len(set(subs)) == len(subs)             # unique tenants
    assert all(m.get("name") for m in bt.MUNICIPALITIES)


def test_build_payload_writes_buyer_name_from_config():
    muni = {"org_key": "york", "subdomain": "york", "name": "York Region"}
    row = {"ref": "2026-104P", "title": "Body armour supply", "guid": "g1",
           "date": "Wed Jul 29, 2026 12:00:00 PM (EDT)", "status": "Open",
           "raw": "2026-104P - Body armour supply"}
    payload = bt.build_payload(muni, "src1", "tender_notice", row, bt.load_keywords())
    assert payload["buyer_name"] == "York Region"
    assert payload["reference_number"] == "2026-104P"


def test_tier1_buyer_names_resolve_via_org_seed():
    from src.resolve_orgs import ORG_SEED
    seeded = {canonical for canonical, *_ in ORG_SEED}
    for muni in bt.MUNICIPALITIES:
        assert muni["name"] in seeded, f"{muni['name']} missing from ORG_SEED"


# --- letter-prefixed references (tier-1 markup probe, 2026-07-20) -------------
def test_parse_bid_name_letter_prefixed_references():
    # Real bid names observed on the York/Durham/London/YRP tenants.
    for text, want_ref in [
        ("RFPQ-3823-26 - Construction Manager at Risk (CMAR) Services", "RFPQ-3823-26"),
        ("RFT-3138-25 - Equipment and Supplies Required", "RFT-3138-25"),
        ("T-1083-2026 - Harmony Creek WPCP motorized slide gate pre-purchase", "T-1083-2026"),
        ("RFT-2026-143 - Construct New Intersection Pedestrian Signal", "RFT-2026-143"),
        ("RFP17-50 - Early Years Programming – French Parent and Family Literacy Centre",
         "RFP17-50"),
        ("T-10-108 - TRAFFIC DATA COLLECTION & DATA SUBMISSION", "T-10-108"),
        ("RFP-303-2017-C - Electrical Services Registry", "RFP-303-2017-C"),
    ]:
        ref, _title = bt.parse_bid_name(text)
        assert ref == want_ref, f"{text!r} -> {ref!r}, wanted {want_ref!r}"


def test_parse_bid_name_rejects_reference_lookalikes():
    # Title words that look reference-ish must never become a reference:
    # COVID-19 has a 5-letter prefix, E-BIDDING carries no digits.
    for text in ["COVID-19 - Vaccination Clinic Staffing",
                 "E-BIDDING - Vendor Information Session",
                 "Pre-Qualification - General Contractors"]:
        ref, title = bt.parse_bid_name(text)
        assert ref is None, f"{text!r} wrongly parsed ref {ref!r}"


def test_bid_ref_word_extracts_full_ref_from_register_link_text():
    # The guid map keys on the same reference form the row parser produces;
    # the word regex must take the full letter-prefixed token, not a digit tail.
    m = bt.BID_REF_WORD.search(
        "Register for this Bid - RFPQ-3823-26 - Construction Manager at Risk")
    assert m and m.group(0) == "RFPQ-3823-26"
    m = bt.BID_REF_WORD.search("Register for this Bid - 2026-104P - Flow Meters")
    assert m and m.group(0) == "2026-104P"


def test_status_query_url_sort_override_for_awarded_paging():
    base = ("https://york.bidsandtenders.ca/Module/Tenders/en/Tender/Search/"
            "eb167b72-95d5-4bbc-a85c-0846df5be368?status=Open&limit=25&start=0"
            "&dir=ASC&from=&to=&sort=DateClosing+ASC,Id")
    u = bt.status_query_url(base, "Awarded", 100, 0, sort="DateClosing DESC,Id")
    assert "sort=DateClosing+DESC%2CId" in u
    # without the override the captured sort is preserved untouched
    u2 = bt.status_query_url(base, "Awarded", 100, 0)
    assert "sort=DateClosing+ASC%2CId" in u2
