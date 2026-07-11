"""Tests for the federal awards collector, against canned datastore_search
pages shaped like the probe-verified real records (2026-07-11)."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import grants_federal_awards as fa
from src.board_minutes import PoliteFetcher
from src.filters import Keywords

KEYWORDS = Keywords(general=("body-worn camera",), defence=("armoured",))
DEPT = {"org": "ps-sp", "env": "AWARDS_SOURCE_ID_PS_SP"}


def _rec(ref, start, amd=0, **over):
    rec = {
        "ref_number": ref,
        "amendment_number": amd,
        "amendment_date": None,
        "agreement_type": "C",
        "recipient_legal_name": "Example Safety Society",
        "recipient_operating_name": None,
        "recipient_city": "Ottawa|Ottawa",
        "recipient_province": "ON",
        "recipient_country": "CA",
        "prog_name_en": "Policy Development Contribution Program",
        "prog_name_fr": "Programme de contribution",
        "prog_purpose_en": "Builds emergency management capacity.",
        "agreement_title_en": "Emergency Planning Project",
        "agreement_value": 25000.0,
        "agreement_start_date": start,
        "agreement_end_date": None,
        "description_en": None,
        "expected_results_en": None,
        "additional_information_en": None,
        "naics_identifier": None,
        "owner_org": "ps-sp",
        "owner_org_title": "Public Safety Canada | Sécurité publique Canada",
    }
    rec.update(over)
    return rec


class FakeAPI:
    """post_json stand-in serving canned pages keyed by offset."""

    def __init__(self, pages):
        self.pages = pages          # {offset: [records]}
        self.calls = []

    def post_json(self, url, payload):
        self.calls.append(payload)
        records = self.pages.get(payload["offset"], [])
        return SimpleNamespace(json=lambda: {
            "success": True, "result": {"records": records}})


def _wire(monkeypatch, existing_hashes=frozenset()):
    inserted = []
    monkeypatch.setattr(fa.supabase_client, "get_document_by_hash",
                        lambda h: {"id": "x"} if h in existing_hashes else None)
    monkeypatch.setattr(fa.supabase_client, "insert_document",
                        lambda p: inserted.append(p) or {"id": "new"})
    return inserted


def test_award_document_mapping(monkeypatch):
    inserted = _wire(monkeypatch)
    api = FakeAPI({0: [_rec("GC-2025-Q1-00001", "2025-06-01")]})
    stats = fa.collect_department(DEPT, "src-1", api, KEYWORDS, 25, dry_run=False)
    assert stats["inserted"] == 1
    doc = inserted[0]
    assert doc["doc_type"] == "grant_award"
    assert doc["published_on"] == "2025-06-01"
    assert doc["title"] == "Emergency Planning Project — Example Safety Society"
    assert doc["url"] == fa.record_url("ps-sp", "GC-2025-Q1-00001", 0)
    for field in ("Agreement type: Contribution", "Value: $25,000.00 CAD",
                  "Recipient location: Ottawa, ON, CA",       # pipe field split
                  "Department: Public Safety Canada"):
        assert field in doc["content"]


def test_window_stop_on_older_record(monkeypatch):
    """Newest-first sort: the first pre-window record ends the department."""
    inserted = _wire(monkeypatch)
    api = FakeAPI({0: [_rec("NEW", "2025-06-01"), _rec("OLD", "2023-01-15"),
                       _rec("OLDER", "2019-03-01")],
                   100: [_rec("NEVER", "2018-01-01")]})
    stats = fa.collect_department(DEPT, "src-1", api, KEYWORDS, 25, dry_run=False)
    assert stats["inserted"] == 1
    assert [d["title"] for d in inserted] == [fa.award_title(_rec("NEW", "2025-06-01"))]
    assert len(api.calls) == 1                       # never paged past the stop


def test_undated_records_skipped_not_fatal(monkeypatch):
    """NULLs sort first on DESC; they're counted, skipped, and the scan
    continues to the dated records."""
    inserted = _wire(monkeypatch)
    api = FakeAPI({0: [_rec("NODATE", None), _rec("DATED", "2025-06-01")]})
    stats = fa.collect_department(DEPT, "src-1", api, KEYWORDS, 25, dry_run=False)
    assert stats["skipped_undated"] == 1 and stats["inserted"] == 1
    assert inserted[0]["published_on"] == "2025-06-01"


def test_amendment_is_a_fresh_document(monkeypatch):
    inserted = _wire(monkeypatch)
    api = FakeAPI({0: [_rec("GC-1", "2025-06-01", amd=0),
                       _rec("GC-1", "2025-06-01", amd=1, agreement_value=40000.0)]})
    stats = fa.collect_department(DEPT, "src-1", api, KEYWORDS, 25, dry_run=False)
    assert stats["inserted"] == 2
    assert inserted[0]["content_hash"] != inserted[1]["content_hash"]
    assert "(amendment 1)" in inserted[1]["title"]
    assert "Amendment: 1" in inserted[1]["content"]


def test_all_duplicate_page_stops_paging(monkeypatch):
    """Steady state: a full page of known records ends the scan after one
    API call."""
    recs = [_rec(f"GC-{i}", "2025-06-01") for i in range(3)]
    inserted = _wire(monkeypatch)
    api = FakeAPI({0: recs, 100: [_rec("DEEP", "2025-01-01")]})
    fa.collect_department(DEPT, "src-1", api, KEYWORDS, 25, dry_run=False)
    hashes = {d["content_hash"] for d in inserted}

    api2 = FakeAPI({0: recs, 100: [_rec("DEEP", "2025-01-01")]})
    inserted2 = _wire(monkeypatch, existing_hashes=hashes)
    stats = fa.collect_department(DEPT, "src-1", api2, KEYWORDS, 25, dry_run=False)
    assert stats["skipped_duplicate"] == 3 and not inserted2
    assert len(api2.calls) == 1


def test_cap_counts_new_docs_and_backlog_resumes(monkeypatch):
    recs = [_rec(f"GC-{i}", "2025-06-01") for i in range(5)]
    inserted = _wire(monkeypatch)
    stats = fa.collect_department(DEPT, "src-1", FakeAPI({0: recs}), KEYWORDS,
                                  limit=2, dry_run=False)
    assert stats["inserted"] == 2
    # next run: the 2 known ones don't consume the cap; the rest insert
    hashes = {d["content_hash"] for d in inserted}
    inserted2 = _wire(monkeypatch, existing_hashes=hashes)
    stats = fa.collect_department(DEPT, "src-1", FakeAPI({0: recs}), KEYWORDS,
                                  limit=25, dry_run=False)
    assert stats["skipped_duplicate"] == 2 and stats["inserted"] == 3
    assert len(inserted2) == 3


def test_run_fails_only_when_every_department_fails(monkeypatch):
    monkeypatch.setattr(fa, "load_keywords", lambda: KEYWORDS)
    monkeypatch.setattr(fa, "PoliteFetcher", lambda: FakeAPI({}))
    monkeypatch.setattr(fa.supabase_client, "update_source_last_collected",
                        lambda *a: None)
    _wire(monkeypatch)
    rows = [{"id": f"src-{d['org']}", "name": d["org"],
             "url": fa.dept_search_url(d["org"])} for d in fa.DEPARTMENTS]

    # every dept resolves and returns empty pages -> success
    monkeypatch.setattr(fa.supabase_client, "fetch_rows", lambda *a: rows)
    assert fa.run(dry_run=True) == 0

    # one dept missing its sources row -> logged failure, run still green
    monkeypatch.setattr(fa.supabase_client, "fetch_rows", lambda *a: rows[1:])
    assert fa.run(dry_run=True) == 0

    # no dept resolves -> systemic
    monkeypatch.setattr(fa.supabase_client, "fetch_rows", lambda *a: [])
    assert fa.run(dry_run=True) == 1


def test_source_resolution_is_url_keyed():
    rows = [{"id": "right", "name": "whatever",
             "url": "https://search.open.canada.ca/grants/?owner_org=ps-sp"}]
    assert fa.resolve_source_id(DEPT, rows) == "right"
    assert fa.resolve_source_id({"org": "dnd-mdn", "env": "NO_SUCH"}, rows) is None


def test_politefetcher_honors_longer_crawl_delay(monkeypatch):
    """open.canada.ca declares Crawl-delay: 20 — longer than our 2s floor, so
    it must be honored; shorter declarations must NOT speed us up."""
    fetcher = PoliteFetcher(delay=2.0)

    def fake_get(url, timeout=None, stream=False):
        return SimpleNamespace(
            ok=True, status_code=200,
            text="User-agent: *\nCrawl-delay: 20\nDisallow: /admin/\n")
    monkeypatch.setattr(fetcher.session, "get", fake_get)
    assert fetcher.allowed("https://slow.example.ca/data/api") is True
    assert fetcher._host_delay["slow.example.ca"] == 20.0

    fast = PoliteFetcher(delay=2.0)
    def fake_get_fast(url, timeout=None, stream=False):
        return SimpleNamespace(ok=True, status_code=200,
                               text="User-agent: *\nCrawl-delay: 1\n")
    monkeypatch.setattr(fast.session, "get", fake_get_fast)
    assert fast.allowed("https://quick.example.ca/x") is True
    assert "quick.example.ca" not in fast._host_delay
