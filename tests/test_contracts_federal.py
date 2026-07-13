"""Tests for the federal contracts collector, against canned datastore pages
shaped like the probe-verified real records (2026-07-13)."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import contracts_federal as cf
from src.filters import Keywords

KEYWORDS = Keywords(general=("body-worn camera",), defence=("armoured",))
DEPT = {"org": "ps-sp", "env": "CONTRACTS_SOURCE_ID_PS_SP"}


def _rec(ref, date, value, proc_id="D160830442", **over):
    rec = {
        "reference_number": ref,
        "procurement_id": proc_id,
        "vendor_name": "Axon Public Safety Canada Inc.",
        "buyer_name": "Public Safety Canada",
        "contract_date": date,
        "contract_period_start": date,
        "delivery_date": None,
        "contract_value": str(value),
        "original_value": str(value),
        "amendment_value": "0.0",
        "description_en": "Body-worn camera systems",
        "description_fr": "Systemes de camera corporelle",
        "commodity_type": "G",
        "solicitation_procedure": "TC",
        "number_of_bids": "3",
        "owner_org": "ps-sp",
        "owner_org_title": "Public Safety Canada | Securite publique Canada",
    }
    rec.update(over)
    return rec


class FakeAPI:
    def __init__(self, pages):
        self.pages = pages          # {offset: [records]}
        self.calls = []

    def post_json(self, url, payload):
        self.calls.append(payload)
        return SimpleNamespace(json=lambda: {
            "success": True, "result": {"records": self.pages.get(payload["offset"], [])}})


def _wire(monkeypatch, existing_hashes=frozenset()):
    inserted = []
    monkeypatch.setattr(cf.supabase_client, "get_document_by_hash",
                        lambda h: {"id": "x"} if h in existing_hashes else None)
    monkeypatch.setattr(cf.supabase_client, "insert_document",
                        lambda p: inserted.append(p) or {"id": "new"})
    return inserted


def test_contract_award_document_mapping(monkeypatch):
    """doc_type is award_notice (awarded rung), procurement_id goes to the
    first-class reference_number the proposer hard-keys on."""
    inserted = _wire(monkeypatch)
    api = FakeAPI({0: [_rec("C-2025-Q1-001", "2025-06-01", 250000, proc_id="D999")]})
    stats = cf.collect_department(DEPT, "src-1", api, KEYWORDS, 50, dry_run=False)
    assert stats["inserted"] == 1
    doc = inserted[0]
    assert doc["doc_type"] == "award_notice"             # floors at awarded (grade 5)
    assert doc["reference_number"] == "D999"             # procurement_id, the hard key
    assert doc["published_on"] == "2025-06-01"
    assert "Body-worn camera systems" in doc["content"]
    assert "$250,000.00 CAD" in doc["content"]


def test_contract_awards_grade_awarded_grants_grade_commitment():
    """Concern #2, asserted directly: a contract award (award_notice) grades
    awarded (5); a grant award (grant_award) grades commitment (3)."""
    from src import taxonomy
    assert taxonomy.grade("contract_award", "award_notice") == 5
    assert taxonomy.rung(taxonomy.grade("contract_award", "award_notice")) == "awarded"
    assert taxonomy.rung(taxonomy.grade("funding_announcement", "grant_award")) == "commitment"


def test_value_floor_skips_small_contracts(monkeypatch):
    inserted = _wire(monkeypatch)
    api = FakeAPI({0: [
        _rec("BIG", "2025-06-01", 150000),
        _rec("SMALL", "2025-05-01", 40000),      # below $100k floor
        _rec("EXACT", "2025-04-15", 100000),     # exactly at the floor -> kept
    ]})
    stats = cf.collect_department(DEPT, "src-1", api, KEYWORDS, 50, dry_run=False)
    assert stats["skipped_below_floor"] == 1
    assert stats["inserted"] == 2
    assert {d["title"].split(" - ")[0] for d in inserted} == {"Body-worn camera systems"}


def test_window_stop_on_older_contract(monkeypatch):
    inserted = _wire(monkeypatch)
    api = FakeAPI({0: [_rec("NEW", "2025-06-01", 200000),
                       _rec("OLD", "2023-01-01", 500000)],
                   100: [_rec("NEVER", "2022-01-01", 900000)]})
    stats = cf.collect_department(DEPT, "src-1", api, KEYWORDS, 50, dry_run=False)
    assert stats["inserted"] == 1
    assert len(api.calls) == 1                            # stopped, never paged on


def test_amendment_reinserts_on_value_change(monkeypatch):
    inserted = _wire(monkeypatch)
    api = FakeAPI({0: [
        _rec("C-1", "2025-06-01", 200000),
        _rec("C-1", "2025-06-01", 350000, amendment_value="150000"),  # amended value
    ]})
    stats = cf.collect_department(DEPT, "src-1", api, KEYWORDS, 50, dry_run=False)
    assert stats["inserted"] == 2
    assert inserted[0]["content_hash"] != inserted[1]["content_hash"]


def test_all_duplicate_page_stops_paging(monkeypatch):
    recs = [_rec(f"C-{i}", "2025-06-01", 200000) for i in range(3)]
    inserted = _wire(monkeypatch)
    cf.collect_department(DEPT, "src-1", FakeAPI({0: recs}), KEYWORDS, 50, dry_run=False)
    hashes = {d["content_hash"] for d in inserted}
    api2 = FakeAPI({0: recs, 100: [_rec("DEEP", "2025-01-01", 200000)]})
    inserted2 = _wire(monkeypatch, existing_hashes=hashes)
    stats = cf.collect_department(DEPT, "src-1", api2, KEYWORDS, 50, dry_run=False)
    assert stats["skipped_duplicate"] == 3 and not inserted2
    assert len(api2.calls) == 1


def test_cap_counts_new_docs(monkeypatch):
    recs = [_rec(f"C-{i}", "2025-06-01", 200000) for i in range(5)]
    inserted = _wire(monkeypatch)
    stats = cf.collect_department(DEPT, "src-1", FakeAPI({0: recs}), KEYWORDS,
                                  limit=2, dry_run=False)
    assert stats["inserted"] == 2


def test_source_resolution_is_url_keyed():
    rows = [{"id": "right", "name": "x",
             "url": "https://search.open.canada.ca/contracts/?owner_org=ps-sp"}]
    assert cf.resolve_source_id(DEPT, rows) == "right"
    assert cf.resolve_source_id({"org": "jus", "env": "NO_SUCH"}, rows) is None


def test_six_departments_configured():
    assert [d["org"] for d in cf.DEPARTMENTS] == [
        "ps-sp", "rcmp-grc", "dnd-mdn", "cbsa-asfc", "csc-scc", "jus"]
