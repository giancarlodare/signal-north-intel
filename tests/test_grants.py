"""Tests for the two grants collectors, against fixtures that mirror the
CI-probe-verified structures of the real pages (2026-07-11):

  - Ontario open directory: <h2> program sections with Status badge, bare
    ministry <p>, and h3/h4 Deadline/Description/Eligibility/Program
    guidelines/Contacts subsections.
  - Ontario closed archive: flat <h3> entries with <h4> ministry under
    letter-group <h2> headings.
  - CFR dataset pages: CKAN resource-items with English/French download PDFs.
  - PS Canada index: one table whose Program column is a <th scope="row">.
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import grants_ontario as go
from src import grants_pscanada as gp
from src.filters import Keywords

KEYWORDS = Keywords(general=("body-worn camera",), defence=("armoured",))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _program(name, status="OPEN", ministry="Ministry of the Solicitor General",
             deadline_html="<p>Applications close September 29, 2026.</p>",
             guidelines_html=None, description="Supports police services.",
             eligibility="Municipal applicants."):
    parts = [f"<h2>{name}</h2>",
             '<div><a class="button" href="/page/apply">Apply for funding</a></div>',
             f'<p>Status: <span class="badge badge--default-heavy">{status}</span></p>',
             f"<p>{ministry}</p>",
             f"<h3>Deadline</h3>{deadline_html}",
             f"<h3>Description</h3><p>{description}</p>",
             f"<h3>Eligibility</h3><p>{eligibility}</p>"]
    if guidelines_html is not None:
        parts.append(f"<h3>Program guidelines</h3>{guidelines_html}")
    parts.append("<h3>Contacts</h3><p>someone@ontario.ca</p>")
    return "".join(parts)


def open_page(*programs):
    return ("<html><body><h2>Overview</h2><p>You can apply for funding.</p>"
            + "".join(programs) + "</body></html>")


CLOSED_PAGE = """
<html><body>
<h2>Closed funding opportunities A &ndash; E</h2>
<h3>Bail Compliance Grant</h3><p>Supports police warrant apprehension.</p>
<h4>Ministry of the Solicitor General</h4>
<p>Status: <span class="badge badge--neutral-light">Closed</span></p><hr>
<h3>Cheese Innovation Fund</h3><p>Supports artisanal dairy.</p>
<h4>Ministry of Agriculture</h4>
<p>Status: <span class="badge badge--neutral-light">Closed</span></p><hr>
<h2>Closed funding opportunities F &ndash; J</h2>
<h3>Fire Protection Grant</h3><p>Year one of the fire protection program.</p>
<h4>Ministry of the Solicitor General</h4>
<p>Status: <span class="badge badge--neutral-light">Closed</span></p><hr>
<h3>Fire Protection Grant</h3><p>Year two of the fire protection program.</p>
<h4>Ministry of the Solicitor General</h4>
<p>Status: <span class="badge badge--neutral-light">Closed</span></p><hr>
</body></html>
"""

CFR_PAGE = """
<html><body>
<li class="resource-item" data-id="a1" title="English - on000464e - Guidelines">
  English Guidelines <span class="format-label">PDF</span>
  <a href="https://forms.example.on.ca/dataset/d1/resource/a1/download/guidelines-en.pdf"
     class="btn" download>Download</a></li>
<li class="resource-item" data-id="f1" title="French - on000464f - Guidelines">
  French Guidelines <span class="format-label">PDF</span>
  <a href="https://forms.example.on.ca/dataset/d1/resource/f1/download/lignes-directrices.pdf"
     class="btn" download>Download</a></li>
</body></html>
"""

PSC_INDEX = """
<html><main>
<table>
<tr><th>Program</th><th>Description</th><th>Type</th></tr>
<tr><th scope="row"><a href="/cnt/prgrm-one-en.aspx">First Nations Policing Program</a></th>
    <td>Funds policing agreements.</td><td>Contribution</td></tr>
<tr><th scope="row">Legacy Program Without Page</th>
    <td>An old program with no detail page.</td><td>Grant</td></tr>
</table>
</main></html>
"""

PSC_DETAIL = ("<html><main><h1>Terms and Conditions</h1>"
              "<p>The program funds tripartite policing agreements.</p></main>"
              "<footer>site footer noise</footer></html>")


class FakeFetcher:
    def __init__(self, pages=None):
        self.pages = pages or {}
        self.requested = []

    def get(self, url):
        self.requested.append(url)
        page = self.pages.get(url)
        if page is None:
            return None
        return SimpleNamespace(text=page, content=page.encode(),
                               headers={"Content-Type": "text/html"},
                               encoding="utf-8")


def _wire(module, monkeypatch, existing_hashes=frozenset()):
    inserted = []
    monkeypatch.setattr(module.supabase_client, "get_document_by_hash",
                        lambda h: {"id": "x"} if h in existing_hashes else None)
    monkeypatch.setattr(module.supabase_client, "insert_document",
                        lambda p: inserted.append(p) or {"id": "new"})
    return inserted


# ---------------------------------------------------------------------------
# Ontario: open directory
# ---------------------------------------------------------------------------
def test_open_page_program_capture(monkeypatch):
    inserted = _wire(go, monkeypatch)
    html = open_page(_program("Preventing Auto Thefts Grant"))
    fetcher = FakeFetcher({go.OPEN_LISTING_URL: html})
    stats = go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                            limit=10, dry_run=False, baseline=False)
    assert stats["inserted"] == 1
    doc = inserted[0]
    assert doc["doc_type"] == "grant_program"
    assert doc["title"] == "Preventing Auto Thefts Grant"
    assert doc["published_on"] == "2026-09-29"      # the DEADLINE is the event
    assert doc["guidelines_gated"] is False
    assert doc["url"].startswith(go.OPEN_LISTING_URL + "#:~:text=")
    for field in ("Status: OPEN", "Ministry of the Solicitor General",
                  "Deadline:", "Description:", "Eligibility:", "Contacts:"):
        assert field in doc["content"]


def test_overview_section_is_not_a_program(monkeypatch):
    """Only sections with a Status badge are programs — Overview and nav
    headings never produce documents."""
    inserted = _wire(go, monkeypatch)
    fetcher = FakeFetcher({go.OPEN_LISTING_URL: open_page(_program("Police Grant"))})
    stats = go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                            limit=10, dry_run=False, baseline=False)
    assert stats["sections"] == 2 and stats["programs"] == 1
    assert len(inserted) == 1


def test_scope_filter_drops_out_of_lane_programs(monkeypatch):
    inserted = _wire(go, monkeypatch)
    html = open_page(
        _program("Cheese Innovation Fund", ministry="Ministry of Agriculture",
                 description="Supports artisanal dairy production."),
        _program("Preventing Auto Thefts Grant"))
    fetcher = FakeFetcher({go.OPEN_LISTING_URL: html})
    stats = go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                            limit=10, dry_run=False, baseline=False)
    assert stats["skipped_scope"] == 1 and stats["inserted"] == 1
    assert inserted[0]["title"] == "Preventing Auto Thefts Grant"


def test_ongoing_deadline_is_honestly_null(monkeypatch):
    inserted = _wire(go, monkeypatch)
    html = open_page(_program(
        "Fire Grant", deadline_html="<p>Applications are accepted on an ongoing basis.</p>"))
    fetcher = FakeFetcher({go.OPEN_LISTING_URL: html})
    go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                    limit=10, dry_run=False, baseline=False)
    assert inserted[0]["published_on"] is None


def test_deadline_change_reinserts_description_edit_does_not(monkeypatch):
    """Operator rule: new programs and deadline changes ARE the signal;
    description edits are not."""
    v1 = open_page(_program("Police Grant"))
    fetcher = FakeFetcher({go.OPEN_LISTING_URL: v1})
    inserted = _wire(go, monkeypatch)
    go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                    limit=10, dry_run=False, baseline=False)
    first_hash = inserted[0]["content_hash"]

    # Description edit → same hash → duplicate-skip.
    edited = open_page(_program("Police Grant", description="Reworded police support."))
    fetcher = FakeFetcher({go.OPEN_LISTING_URL: edited})
    stats = go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                            limit=10, dry_run=False, baseline=False)
    # note: dedupe is against the store, simulated by first_hash
    inserted2 = _wire(go, monkeypatch, existing_hashes={first_hash})
    stats = go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                            limit=10, dry_run=False, baseline=False)
    assert stats["skipped_duplicate"] == 1 and not inserted2

    # Deadline change → new hash → fresh document.
    moved = open_page(_program(
        "Police Grant", deadline_html="<p>Applications close October 30, 2026.</p>"))
    fetcher = FakeFetcher({go.OPEN_LISTING_URL: moved})
    inserted3 = _wire(go, monkeypatch, existing_hashes={first_hash})
    go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                    limit=10, dry_run=False, baseline=False)
    assert len(inserted3) == 1
    assert inserted3[0]["published_on"] == "2026-10-30"


def test_gated_guidelines_recorded_not_skipped(monkeypatch):
    """Operator rule: TPON-login / by-request guidelines set
    guidelines_gated=true; the program is still collected."""
    inserted = _wire(go, monkeypatch)
    html = open_page(_program(
        "Fire Protection Reimbursement",
        guidelines_html="<p>The program guidelines are available by logging in "
                        'to the <a href="https://www.tpon.gov.on.ca/tpon/psLogin">'
                        "Transfer Payment Ontario system</a>.</p>"))
    fetcher = FakeFetcher({go.OPEN_LISTING_URL: html})
    stats = go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                            limit=10, dry_run=False, baseline=False)
    assert stats["gated"] == 1 and stats["inserted"] == 1
    assert inserted[0]["guidelines_gated"] is True
    assert "GATED" in inserted[0]["content"]


def test_cfr_guidelines_followed_english_only(monkeypatch):
    """A public CFR link is followed; its English download PDF is fetched and
    captured; the French copy is skipped."""
    monkeypatch.setattr(go, "PUBLIC_GUIDELINE_HOSTS",
                        {"forms.example.on.ca"})
    cfr_url = "https://forms.example.on.ca/en/dataset/on000464"
    pdf_url = "https://forms.example.on.ca/dataset/d1/resource/a1/download/guidelines-en.pdf"
    html = open_page(_program(
        "Police Grant",
        guidelines_html=f'<p><a href="{cfr_url}">Program Guidelines</a></p>'))
    fetcher = FakeFetcher({go.OPEN_LISTING_URL: html, cfr_url: CFR_PAGE,
                           pdf_url: "not actually fetched as html"})
    # make the PDF fetch return PDF-ish response and stub pdf_to_text
    real_get = fetcher.get
    def get(url):
        resp = real_get(url)
        if resp is not None and url.endswith(".pdf"):
            resp.headers = {"Content-Type": "application/pdf"}
        return resp
    fetcher.get = get
    monkeypatch.setattr(go, "pdf_to_text", lambda data: "Scoring rubric: 40 points capacity.")
    inserted = _wire(go, monkeypatch)
    stats = go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                            limit=10, dry_run=False, baseline=False)
    assert stats["guideline_fetches"] == 2          # CFR page + English PDF
    assert pdf_url in fetcher.requested
    assert not any("lignes-directrices" in u for u in fetcher.requested)
    doc = inserted[0]
    assert doc["guidelines_gated"] is False
    assert "Scoring rubric: 40 points capacity." in doc["content"]


def test_guideline_fetch_failure_never_drops_the_program(monkeypatch):
    monkeypatch.setattr(go, "PUBLIC_GUIDELINE_HOSTS", {"forms.example.on.ca"})
    cfr_url = "https://forms.example.on.ca/en/dataset/broken"
    html = open_page(_program(
        "Police Grant",
        guidelines_html=f'<p><a href="{cfr_url}">Program Guidelines</a></p>'))
    fetcher = FakeFetcher({go.OPEN_LISTING_URL: html})    # CFR fetch -> None
    inserted = _wire(go, monkeypatch)
    stats = go.collect_page(go.OPEN_LISTING_URL, 2, "src-1", fetcher, KEYWORDS,
                            limit=10, dry_run=False, baseline=False)
    assert stats["inserted"] == 1 and stats["errors"] == 0
    assert inserted[0]["guidelines_gated"] is False


# ---------------------------------------------------------------------------
# Ontario: closed archive baseline
# ---------------------------------------------------------------------------
def test_closed_archive_baseline(monkeypatch):
    inserted = _wire(go, monkeypatch)
    fetcher = FakeFetcher({go.CLOSED_LISTING_URL: CLOSED_PAGE})
    stats = go.collect_page(go.CLOSED_LISTING_URL, 3, "src-2", fetcher, KEYWORDS,
                            limit=200, dry_run=False, baseline=True)
    # Cheese fund out of scope; Bail + two Fire Protection years in.
    assert stats["programs"] == 4 and stats["skipped_scope"] == 1
    assert stats["inserted"] == 3
    for doc in inserted:
        assert doc["published_on"] is None          # no date beats a wrong date
        assert doc["doc_type"] == "grant_program"
    # Same-name year-cycles stay distinct (description snippet in the hash)…
    fire = [d for d in inserted if d["title"] == "Fire Protection Grant"]
    assert len(fire) == 2 and fire[0]["content_hash"] != fire[1]["content_hash"]
    # …and the guidelines follow-through never runs on the archive.
    assert fetcher.requested == [go.CLOSED_LISTING_URL]


def test_closed_archive_rerun_is_idempotent(monkeypatch):
    fetcher = FakeFetcher({go.CLOSED_LISTING_URL: CLOSED_PAGE})
    inserted = _wire(go, monkeypatch)
    go.collect_page(go.CLOSED_LISTING_URL, 3, "src-2", fetcher, KEYWORDS,
                    limit=200, dry_run=False, baseline=True)
    hashes = {d["content_hash"] for d in inserted}
    inserted2 = _wire(go, monkeypatch, existing_hashes=hashes)
    stats = go.collect_page(go.CLOSED_LISTING_URL, 3, "src-2", fetcher, KEYWORDS,
                            limit=200, dry_run=False, baseline=True)
    assert stats["skipped_duplicate"] == 3 and not inserted2


def test_cap_counts_new_documents_only(monkeypatch):
    """Duplicates must not consume the per-run cap (the board-collector
    backlog-stall lesson)."""
    fetcher = FakeFetcher({go.CLOSED_LISTING_URL: CLOSED_PAGE})
    inserted = _wire(go, monkeypatch)
    go.collect_page(go.CLOSED_LISTING_URL, 3, "src-2", fetcher, KEYWORDS,
                    limit=200, dry_run=False, baseline=True)
    first_hash = inserted[0]["content_hash"]
    inserted2 = _wire(go, monkeypatch, existing_hashes={first_hash})
    stats = go.collect_page(go.CLOSED_LISTING_URL, 3, "src-2", fetcher, KEYWORDS,
                            limit=2, dry_run=False, baseline=True)
    assert stats["skipped_duplicate"] == 1 and stats["inserted"] == 2


# ---------------------------------------------------------------------------
# Ontario: run-level policy
# ---------------------------------------------------------------------------
def test_unreachable_listing_is_systemic_failure(monkeypatch):
    monkeypatch.setattr(go, "PoliteFetcher", lambda: FakeFetcher())  # all None
    monkeypatch.setattr(go.supabase_client, "fetch_rows",
                        lambda *a: [{"id": "s1", "name": "x",
                                     "url": go.OPEN_LISTING_URL}])
    monkeypatch.setattr(go, "load_keywords", lambda: KEYWORDS)
    assert go.run(dry_run=True) == 1


def test_source_resolution_is_url_keyed(monkeypatch):
    rows = [{"id": "right", "name": "Ontario — Available Funding Opportunities",
             "url": go.OPEN_LISTING_URL},
            {"id": "wrong", "name": "Ontario - Available Funding Opportunities",
             "url": "https://example.com/other"}]
    assert go.resolve_source_id(go.OPEN_LISTING_URL, rows,
                                "NO_SUCH_ENV") == "right"
    assert go.resolve_source_id("https://nowhere.example", rows,
                                "NO_SUCH_ENV") is None


# ---------------------------------------------------------------------------
# PS Canada
# ---------------------------------------------------------------------------
def test_psc_index_parses_th_scope_rows():
    programs = gp.parse_programs(PSC_INDEX, gp.INDEX_URL)
    assert len(programs) == 2                       # header row skipped
    assert programs[0]["name"] == "First Nations Policing Program"
    assert programs[0]["url"] == "https://www.publicsafety.gc.ca/cnt/prgrm-one-en.aspx"
    assert programs[0]["type"] == "Contribution"
    assert programs[1]["has_detail"] is False
    assert programs[1]["url"].startswith(gp.INDEX_URL + "#:~:text=")


def test_psc_collects_detail_bodies(monkeypatch):
    inserted = _wire(gp, monkeypatch)
    detail_url = "https://www.publicsafety.gc.ca/cnt/prgrm-one-en.aspx"
    fetcher = FakeFetcher({gp.INDEX_URL: PSC_INDEX, detail_url: PSC_DETAIL})
    stats = gp.collect("src-3", fetcher, KEYWORDS, limit=40, dry_run=False)
    assert stats["inserted"] == 2 and stats["bodies_fetched"] == 1
    doc = inserted[0]
    assert doc["doc_type"] == "grant_program"
    assert doc["published_on"] is None              # standing page, not an event
    assert "tripartite policing agreements" in doc["content"]
    assert "site footer noise" not in doc["content"]   # <main> only


def test_psc_detail_failure_skips_without_inserting(monkeypatch):
    """A failed detail fetch must NOT insert a body-less record behind the
    dedupe hash — the next weekly run retries instead."""
    inserted = _wire(gp, monkeypatch)
    fetcher = FakeFetcher({gp.INDEX_URL: PSC_INDEX})     # detail page -> None
    stats = gp.collect("src-3", fetcher, KEYWORDS, limit=40, dry_run=False)
    assert stats["errors"] == 1
    assert [d["title"] for d in inserted] == ["Legacy Program Without Page"]


def test_psc_rerun_is_idempotent(monkeypatch):
    detail_url = "https://www.publicsafety.gc.ca/cnt/prgrm-one-en.aspx"
    fetcher = FakeFetcher({gp.INDEX_URL: PSC_INDEX, detail_url: PSC_DETAIL})
    inserted = _wire(gp, monkeypatch)
    gp.collect("src-3", fetcher, KEYWORDS, limit=40, dry_run=False)
    hashes = {d["content_hash"] for d in inserted}
    inserted2 = _wire(gp, monkeypatch, existing_hashes=hashes)
    stats = gp.collect("src-3", fetcher, KEYWORDS, limit=40, dry_run=False)
    assert stats["skipped_duplicate"] == 2 and not inserted2
    # duplicates are skipped before any detail fetch — no wasted requests
    assert fetcher.requested.count(detail_url) == 1


def test_psc_dry_run_writes_nothing(monkeypatch):
    inserted = _wire(gp, monkeypatch)
    detail_url = "https://www.publicsafety.gc.ca/cnt/prgrm-one-en.aspx"
    fetcher = FakeFetcher({gp.INDEX_URL: PSC_INDEX, detail_url: PSC_DETAIL})
    stats = gp.collect("src-3", fetcher, KEYWORDS, limit=40, dry_run=True)
    assert stats["inserted"] == 2 and not inserted
