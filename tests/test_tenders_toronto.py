"""Tests for the Toronto CKAN collector's pure logic: the live-column
resolver (the whole point of the build, per docs/toronto-ckan-design.md
section 2), date normalization across Toronto's date shapes, and payload
construction (hard key on Toronto's reference, non-competitive marking,
null-date discipline, defence tagging, keep-all body assembly). The network
path (package_show + datastore_search) is exercised by a CI dry-run, not
unit-tested here."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import tenders_toronto as tt
from src.filters import Keywords

KW = Keywords(general=("bridge",), defence=("police",))

OPEN_DS = {"slug": "tobids-all-open-solicitations", "doc_type": "tender_notice",
           "date_role": "close", "non_competitive": False}
AWARD_DS = {"slug": "tobids-awarded-contracts", "doc_type": "award_notice",
            "date_role": "award", "non_competitive": False}
NC_DS = {"slug": "tobids-non-competitive-contracts", "doc_type": "award_notice",
         "date_role": "award", "non_competitive": True}


# --- column resolver ---------------------------------------------------------
def test_resolve_columns_prefers_specific_over_generic():
    fields = ["_id", "Solicitation Document Number", "Solicitation Document Description",
              "High Level Category", "Client Division", "Issue Date",
              "Submission Deadline", "_full_text"]
    cols = tt._resolve_columns(fields)
    # "solicitation document number" beats a bare "number"; "submission
    # deadline" is the close date; internals are excluded.
    assert cols["reference"] == "Solicitation Document Number"
    assert cols["description"] == "Solicitation Document Description"
    assert cols["close"] == "Submission Deadline"
    assert cols["issue"] == "Issue Date"
    assert cols["division"] == "Client Division"
    assert cols["category"] == "High Level Category"


def test_resolve_columns_award_and_vendor_shapes():
    fields = ["Solicitation Number", "Awarded Supplier", "Award Date",
              "Total Awarded Amount", "Division", "Description"]
    cols = tt._resolve_columns(fields)
    assert cols["reference"] == "Solicitation Number"
    assert cols["award"] == "Award Date"
    assert cols["vendor"] == "Awarded Supplier"
    assert cols["value"] == "Total Awarded Amount"


def test_resolve_columns_no_double_assignment():
    # A single column must not be claimed by two roles; each pick is consumed.
    fields = ["Number", "Description", "Date"]
    cols = tt._resolve_columns(fields)
    picked = [v for v in cols.values() if v]
    assert len(picked) == len(set(picked))


# --- date normalization ------------------------------------------------------
def test_normalize_date_iso_and_slash():
    assert tt.normalize_date("2026-04-15") == "2026-04-15"
    assert tt.normalize_date("2026/04/15") == "2026-04-15"
    assert tt.normalize_date("2026-04-15T00:00:00") == "2026-04-15"


def test_normalize_date_textual_month():
    assert tt.normalize_date("April 15, 2026") == "2026-04-15"
    assert tt.normalize_date("Apr 5 2026") == "2026-04-05"


def test_normalize_date_numeric_month_first():
    assert tt.normalize_date("04/15/2026") == "2026-04-15"


def test_normalize_date_rejects_garbage_never_fabricates():
    assert tt.normalize_date("") is None
    assert tt.normalize_date(None) is None
    assert tt.normalize_date("not a date") is None
    assert tt.normalize_date("2026-13-40") is None   # impossible month/day


# --- payload construction ----------------------------------------------------
COLS = {"reference": "Solicitation Number", "close": "Submission Deadline",
        "award": "Award Date", "issue": "Issue Date", "vendor": "Awarded Supplier",
        "description": "Description", "division": "Division", "value": "Amount",
        "category": None, "url": None}


def test_open_solicitation_payload_hard_key_and_close_date():
    rec = {"Solicitation Number": "Doc 123-2026", "Description": "Bridge rehab",
           "Submission Deadline": "2026-08-05", "Division": "Engineering",
           "_id": 7}
    p = tt.build_payload(rec, COLS, OPEN_DS, "src-1", KW)
    assert p["doc_type"] == "tender_notice"
    assert p["reference_number"] == "Doc 123-2026"
    assert p["published_on"] == "2026-08-05"    # the close date
    assert p["date_precision"] == "day"
    assert p["status"] == "captured"
    assert p["buyer_name"] == "City of Toronto"
    # identity keys on the Toronto reference, not the CKAN _id
    assert p["content_hash"] == tt.content_hash("toronto:Doc 123-2026", "tender_notice")


def test_award_payload_uses_award_date_and_tags_defence():
    rec = {"Solicitation Number": "RFQ 9-2026", "Description": "Police fleet repair",
           "Award Date": "2026/03/01", "Awarded Supplier": "Acme Ltd",
           "Amount": "50000"}
    p = tt.build_payload(rec, COLS, AWARD_DS, "src-1", KW)
    assert p["doc_type"] == "award_notice"
    assert p["published_on"] == "2026-03-01"
    assert p["defence_relevant"] is True      # "police" defence keyword hit
    assert "Acme Ltd" in p["content"]


def test_non_competitive_marked_and_reference_fallback():
    # A non-competitive row with no solicitation reference: status marks it,
    # the title flags it, and identity falls back to a stable composite
    # (never colliding with a referenced row's namespace).
    rec = {"Description": "Proprietary software renewal", "Award Date": "2026-01-10",
           "Awarded Supplier": "Vendor X", "Division": "IT"}
    cols = dict(COLS, reference=None)
    p = tt.build_payload(rec, cols, NC_DS, "src-1", KW)
    assert p["status"] == "non_competitive"
    assert p["title"].startswith("Non-competitive:")
    assert p["reference_number"] is None
    assert p["content_hash"] == tt.content_hash(
        "toronto-nc:Vendor X|Proprietary software renewal|IT|2026-01-10",
        "award_notice")
    assert "NON-COMPETITIVE" in p["content"]


def test_missing_date_yields_null_published_on_valid_precision():
    rec = {"Solicitation Number": "Doc 5", "Description": "x",
           "Submission Deadline": "unknown"}
    p = tt.build_payload(rec, COLS, OPEN_DS, "src-1", KW)
    assert p["published_on"] is None          # none beats a wrong date
    assert p["date_precision"] == "day"       # still NOT NULL-valid


def test_body_keeps_unmapped_columns():
    rec = {"Solicitation Number": "Doc 5", "Description": "x",
           "Submission Deadline": "2026-08-05", "Weird Extra Field": "keep me"}
    p = tt.build_payload(rec, COLS, OPEN_DS, "src-1", KW)
    assert "Weird Extra Field: keep me" in p["content"]
