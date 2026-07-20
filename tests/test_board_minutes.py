import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import board_minutes as bm
from src.filters import Keywords


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _mini_pdf(text: str) -> bytes:
    """Build a minimal one-page PDF containing `text`, with a valid xref."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(stream)).encode() + b">>stream\n" + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj".encode() + obj + b"endobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\n"
            f"startxref\n{xref_pos}\n%%EOF").encode()
    return bytes(out)


LISTING_HTML = """
<html><body>
  <a href="/docs/minutes-2026-06-25.pdf">Minutes — June 25, 2026</a>
  <a href="agenda-july.html">Agenda for July meeting</a>
  <a href="https://elsewhere.example.com/minutes.pdf">Regional minutes (PDF, offsite)</a>
  <a href="https://elsewhere.example.com/minutes.html">Offsite HTML minutes</a>
  <a href="/about-the-board">About the Board</a>
  <a href="mailto:board@example.com">Email the board minutes clerk</a>
  <a href="/docs/minutes-2026-06-25.pdf">Minutes — June 25, 2026 (duplicate link)</a>
</body></html>
"""


class FakeResponse:
    def __init__(self, text="", status_code=200, headers=None, content=b""):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content or text.encode()
        self.ok = 200 <= status_code < 300
        self.encoding = "utf-8"

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeFetcher:
    """Stands in for PoliteFetcher: serves canned responses, never sleeps."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.requested: list = []

    def get(self, url):
        self.requested.append(url)
        return self.responses.get(url)


NO_KEYWORDS = Keywords(general=("drone",), defence=("armoured",))


# ---------------------------------------------------------------------------
# Link discovery
# ---------------------------------------------------------------------------
def test_find_document_links_keeps_minutes_and_agendas_only():
    links = bm.find_document_links(LISTING_HTML, "https://board.example.ca/meetings")
    urls = [u for u, *_ in links]
    assert "https://board.example.ca/docs/minutes-2026-06-25.pdf" in urls
    assert "https://board.example.ca/agenda-july.html" in urls          # same-host HTML ok
    assert "https://elsewhere.example.com/minutes.pdf" in urls           # offsite PDF ok
    assert "https://elsewhere.example.com/minutes.html" not in urls      # offsite HTML dropped
    assert not any("about-the-board" in u for u in urls)                 # not minutes/agenda
    assert not any(u.startswith("mailto:") for u in urls)
    assert urls.count("https://board.example.ca/docs/minutes-2026-06-25.pdf") == 1  # deduped


def test_find_document_links_skips_office_binaries():
    # A same-host .docx named "minutes" would otherwise qualify and then decode
    # to NUL-laden text that Postgres rejects (the TPSB daily-collect failure).
    html = ('<a href="/uploads/Public_Minutes_Mar_4.docx">Read the Minutes</a>'
            '<a href="/uploads/Public_Minutes_Mar_4.pdf">Read the Minutes (PDF)</a>')
    urls = [u for u, *_ in bm.find_document_links(html, "https://board.example.ca/meetings")]
    assert "https://board.example.ca/uploads/Public_Minutes_Mar_4.docx" not in urls
    assert "https://board.example.ca/uploads/Public_Minutes_Mar_4.pdf" in urls


def test_html_to_text_strips_scripts_and_collapses_whitespace():
    html = "<html><script>var x=1;</script><body><h1>Board</h1>\n<p>met  on   June 25</p></body></html>"
    assert bm.html_to_text(html) == "Board met on June 25"


def test_pdf_to_text_extracts_body():
    text = bm.pdf_to_text(_mini_pdf("Body-worn camera pilot approved"))
    assert "Body-worn camera pilot approved" in text


def test_guess_meeting_date():
    assert bm.guess_meeting_date("Minutes — June 25, 2026") == "2026-06-25"
    assert bm.guess_meeting_date("", "agenda_2026-03-14.pdf") == "2026-03-14"
    assert bm.guess_meeting_date("Agenda for the next meeting") is None


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------
def _fetcher_with_robots(robots_response):
    fetcher = bm.PoliteFetcher(delay=0)

    class Session:
        headers: dict = {}

        def get(self, url, **kwargs):
            if url.endswith("/robots.txt"):
                return robots_response
            return FakeResponse("<html></html>")

    fetcher.session = Session()
    return fetcher


def test_robots_disallow_blocks_fetch():
    robots = FakeResponse("User-agent: *\nDisallow: /", status_code=200)
    fetcher = _fetcher_with_robots(robots)
    assert fetcher.allowed("https://board.example.ca/meetings") is False
    assert fetcher.get("https://board.example.ca/meetings") is None


def test_robots_missing_allows_fetch():
    fetcher = _fetcher_with_robots(FakeResponse("not found", status_code=404))
    assert fetcher.allowed("https://board.example.ca/meetings") is True


def test_robots_unreachable_is_conservative():
    fetcher = _fetcher_with_robots(FakeResponse("err", status_code=500))
    assert fetcher.allowed("https://board.example.ca/meetings") is False


# ---------------------------------------------------------------------------
# Collection behaviour
# ---------------------------------------------------------------------------
BOARD = {
    "name": "Testville Police Board",
    "source_name_candidates": ["Testville Police Board"],
    "source_id_env": "TESTVILLE_SOURCE_ID",
    "listing_urls": ["https://board.example.ca/meetings"],
}


def _wire(monkeypatch, existing_hashes=frozenset()):
    inserted = []
    monkeypatch.setattr(bm.supabase_client, "get_document_by_hash",
                        lambda h: {"id": "x"} if h in existing_hashes else None)
    monkeypatch.setattr(bm.supabase_client, "insert_document",
                        lambda payload: inserted.append(payload) or {"id": "new"})
    return inserted


def _canned_fetcher():
    pdf = _mini_pdf("Award of armoured vehicle contract")
    return FakeFetcher({
        "https://board.example.ca/meetings": FakeResponse(LISTING_HTML),
        "https://board.example.ca/docs/minutes-2026-06-25.pdf": FakeResponse(
            headers={"Content-Type": "application/pdf"}, content=pdf),
        "https://board.example.ca/agenda-july.html": FakeResponse(
            "<html><body>Agenda: drone program update</body></html>",
            headers={"Content-Type": "text/html"}),
        "https://elsewhere.example.com/minutes.pdf": FakeResponse(
            headers={"Content-Type": "application/pdf"}, content=pdf),
    })


def test_collect_inserts_with_body_hash_and_publisher_url(monkeypatch):
    inserted = _wire(monkeypatch)
    stats = bm.collect_board(BOARD, "src-1", _canned_fetcher(), NO_KEYWORDS,
                             limit=10, dry_run=False)
    assert stats["inserted"] == 3 and stats["errors"] == 0
    pdf_doc = next(d for d in inserted if d["url"].endswith("minutes-2026-06-25.pdf"))
    assert pdf_doc["doc_type"] == "board_minutes"
    assert pdf_doc["published_on"] == "2026-06-25"
    assert "armoured vehicle" in pdf_doc["content"]          # real body stored
    assert pdf_doc["defence_relevant"] is True               # tagged, not dropped
    assert pdf_doc["url"].startswith("https://board.example.ca/")  # publisher URL
    html_doc = next(d for d in inserted if d["url"].endswith("agenda-july.html"))
    assert "drone program update" in html_doc["content"]


def test_collect_skips_existing_hashes(monkeypatch):
    from src.hashing import content_hash
    dup = content_hash("https://board.example.ca/docs/minutes-2026-06-25.pdf",
                       "board_minutes")
    inserted = _wire(monkeypatch, existing_hashes={dup})
    stats = bm.collect_board(BOARD, "src-1", _canned_fetcher(), NO_KEYWORDS,
                             limit=10, dry_run=False)
    assert stats["skipped_duplicate"] == 1
    assert not any(d["url"].endswith("minutes-2026-06-25.pdf") for d in inserted)


def test_dry_run_writes_nothing(monkeypatch):
    inserted = _wire(monkeypatch)
    stats = bm.collect_board(BOARD, "src-1", _canned_fetcher(), NO_KEYWORDS,
                             limit=10, dry_run=True)
    assert stats["inserted"] == 3      # counted…
    assert inserted == []              # …but nothing written


def test_resolve_source_id_by_name_and_env(monkeypatch):
    sources = [{"id": "abc", "name": "  Testville  POLICE board "}]
    assert bm.resolve_source_id(BOARD, sources) == "abc"
    monkeypatch.setenv("TESTVILLE_SOURCE_ID", "override-id")
    assert bm.resolve_source_id(BOARD, sources) == "override-id"
    monkeypatch.delenv("TESTVILLE_SOURCE_ID")
    assert bm.resolve_source_id(BOARD, [{"id": "z", "name": "Other Board"}]) is None


# ---------------------------------------------------------------------------
# RFC 9309: 4xx robots => allow; extra URL patterns; cap semantics
# ---------------------------------------------------------------------------
def test_robots_4xx_treated_as_allow_per_rfc9309():
    # tpsb.ca's WAF 415s robots.txt even though the file allows all crawling.
    fetcher = _fetcher_with_robots(FakeResponse("blocked", status_code=415))
    assert fetcher.allowed("https://board.example.ca/meetings") is True


def test_media_pdf_pattern_matches_without_minutes_wording():
    import re
    html = '''
      <a href="/media/ab12cd/board-report-june-27.pdf">Public Board Meeting Report</a>
      <a href="/media/ef34gh/photo.jpg">Photo gallery</a>
      <a href="https://elsewhere.example.com/media/x.pdf">Offsite media PDF</a>
      <a href="/newsletter">Newsletter</a>
    '''
    patterns = [re.compile(r"/media/.+\.pdf$", re.IGNORECASE)]
    links = bm.find_document_links(html, "https://board.example.ca/meetings", patterns)
    urls = [u for u, *_ in links]
    assert "https://board.example.ca/media/ab12cd/board-report-june-27.pdf" in urls
    assert not any("photo.jpg" in u for u in urls)          # pattern is .pdf only
    assert not any("elsewhere" in u for u in urls)          # extra rule is same-host only
    assert not any(u.endswith("/newsletter") for u in urls)
    # Title comes from the link text downstream:
    assert links[0][1] == "Public Board Meeting Report"


def test_cap_counts_new_docs_not_candidates(monkeypatch):
    """Backlog paging: duplicates must not consume the per-run cap, or a
    multi-year listing stalls on its first N docs forever."""
    from src.hashing import content_hash
    html = "".join(
        f'<a href="/docs/minutes-{i}.pdf">Minutes part {i}</a>' for i in range(6))
    pdf = _mini_pdf("body text")
    pages = {"https://board.example.ca/meetings": FakeResponse(html)}
    for i in range(6):
        pages[f"https://board.example.ca/docs/minutes-{i}.pdf"] = FakeResponse(
            headers={"Content-Type": "application/pdf"}, content=pdf)
    # First 4 documents are already collected:
    existing = {content_hash(f"https://board.example.ca/docs/minutes-{i}.pdf",
                             "board_minutes") for i in range(4)}
    inserted = _wire(monkeypatch, existing_hashes=existing)
    stats = bm.collect_board(BOARD, "src-1", FakeFetcher(pages), NO_KEYWORDS,
                             limit=2, dry_run=False)
    assert stats["skipped_duplicate"] == 4      # skipped without consuming cap
    assert stats["inserted"] == 2               # both NEW docs collected
    assert len(inserted) == 2


def test_section_expansion_one_level_only(monkeypatch):
    """/reports/ sub-pages are scanned as listings; their own sub-links are not."""
    pdf = _mini_pdf("annual performance details")
    root = "https://board.example.ca/reports/"
    sub = "https://board.example.ca/reports/annual-performance/"
    deeper = "https://board.example.ca/reports/annual-performance/archive/"
    fetcher = FakeFetcher({
        "https://board.example.ca/meetings": FakeResponse(
            f'<a href="{root}">Reports</a>'),          # not under prefix match? root IS
        root: FakeResponse(
            f'<a href="{sub}">Annual Performance</a>'
            f'<a href="/media/aa11/summary.pdf">Budget Summary</a>'),
        sub: FakeResponse(
            f'<a href="/media/bb22/annual-perf.pdf">2025 Annual Performance Report</a>'
            f'<a href="{deeper}">Archive</a>'),
        "https://board.example.ca/media/aa11/summary.pdf": FakeResponse(
            headers={"Content-Type": "application/pdf"}, content=pdf),
        "https://board.example.ca/media/bb22/annual-perf.pdf": FakeResponse(
            headers={"Content-Type": "application/pdf"}, content=pdf),
    })
    board = dict(BOARD,
                 listing_urls=[root],
                 listing_expand_prefixes=["/reports/"],
                 doc_url_patterns=[r"/media/.+\.pdf$"])
    inserted = _wire(monkeypatch)
    stats = bm.collect_board(board, "src-1", fetcher, NO_KEYWORDS,
                             limit=10, dry_run=False)
    urls = [d["url"] for d in inserted]
    assert any(u.endswith("summary.pdf") for u in urls)        # from configured page
    assert any(u.endswith("annual-perf.pdf") for u in urls)    # from expanded sub-page
    assert deeper not in fetcher.requested                     # one level only
    assert stats["listing_pages"] == 2


def test_parked_board_is_skipped_not_failed(monkeypatch):
    monkeypatch.setattr(bm.supabase_client, "fetch_rows",
                        lambda table, select, limit=10000: [])
    monkeypatch.setattr(bm, "BOARDS", [dict(BOARD, enabled=False,
                                            parked_reason="WAF blocks client")])
    monkeypatch.setattr(bm, "load_keywords", lambda: NO_KEYWORDS)
    assert bm.run(limit=5, dry_run=True) == 0     # parked != failure


def test_guess_meeting_date_richer_formats():
    g = bm.guess_meeting_date
    assert g("Board meeting of 26 September 2025") == "2025-09-26"
    assert g("Sept. 26, 2025 Regular Meeting") == "2025-09-26"
    assert g("Friday, the 30th of October 2025") == "2025-10-30"
    assert g("Oct 30 2025") == "2025-10-30"
    assert g("meeting 24/04/26") is None            # ambiguous numeric unparsed
    assert g("Item 32-05-26 discussion") is None    # item numbers don't match


def test_backfill_derives_dates_and_never_overwrites(monkeypatch):
    from src import backfill_event_dates as bf
    updates = []
    monkeypatch.setattr(bf.supabase_client, "fetch_all_rows_where",
                        lambda t, s, f, page_size=1000: [
                            {"id": "d1", "title": "Update on plan", "url": "u1",
                             "content": "Regular Meeting — Sept. 26, 2025. Agenda..."},
                            {"id": "d2", "title": "No date anywhere", "url": "u2",
                             "content": "lorem ipsum"},
                        ])
    monkeypatch.setattr(bf.supabase_client, "update_row",
                        lambda t, i, p: updates.append((i, p)))
    stats = bf.run(dry_run=False)
    assert stats == {"examined": 2, "dated": 1, "still_unknown": 1, "errors": 0}
    assert updates == [("d1", {"published_on": "2025-09-26", "date_precision": "day"})]

    updates.clear()
    stats = bf.run(dry_run=True)                     # dry run writes nothing
    assert stats["dated"] == 1 and updates == []


def test_derive_event_date_precisions():
    d = bm.derive_event_date
    # Full date anywhere wins, precision 'day'
    assert d("Minutes June 25, 2026", "/media/ab/33-04-26-x.pdf") == ("2026-06-25", "day")
    # Peel item-month-year convention -> month precision, day=01 placeholder
    assert d("FIFA World Cup", "https://x.ca/media/4ytdw3za/32-04-26-fifa.pdf") == ("2026-04-01", "month")
    # Invalid month in convention -> nothing
    assert d("", "/media/ab/03-13-26-bad.pdf") == (None, None)
    assert d("no date", "/media/ab/plain-slug.pdf") == (None, None)


def test_listing_context_feeds_date_derivation(monkeypatch):
    """Option 3: the meeting date next to the link on the listing page dates
    documents whose own text carries no date."""
    pdf = _mini_pdf("no date in this deck at all")
    listing = ('<h3>Meeting of June 27, 2025</h3>'
               '<a href="/media/qq11/some-presentation.pdf">Watch the deck</a>')
    fetcher = FakeFetcher({
        "https://board.example.ca/meetings": FakeResponse(listing),
        "https://board.example.ca/media/qq11/some-presentation.pdf": FakeResponse(
            headers={"Content-Type": "application/pdf"}, content=pdf),
    })
    board = dict(BOARD, doc_url_patterns=[r"/media/.+\.pdf$"])
    inserted = _wire(monkeypatch)
    bm.collect_board(board, "src-1", fetcher, NO_KEYWORDS, limit=5, dry_run=False)
    assert inserted[0]["published_on"] == "2025-06-27"
    assert inserted[0]["date_precision"] == "day"


def test_month_precision_lands_in_payload(monkeypatch):
    pdf = _mini_pdf("deck without any written date")
    listing = '<a href="/media/zz9/33-04-26-quarterly-update.pdf">Quarterly Update</a>'
    fetcher = FakeFetcher({
        "https://board.example.ca/meetings": FakeResponse(listing),
        "https://board.example.ca/media/zz9/33-04-26-quarterly-update.pdf": FakeResponse(
            headers={"Content-Type": "application/pdf"}, content=pdf),
    })
    board = dict(BOARD, doc_url_patterns=[r"/media/.+\.pdf$"])
    inserted = _wire(monkeypatch)
    bm.collect_board(board, "src-1", fetcher, NO_KEYWORDS, limit=5, dry_run=False)
    assert inserted[0]["published_on"] == "2026-04-01"
    assert inserted[0]["date_precision"] == "month"


# --- Big 12 phase 2 (docs/big12-boards-design.md) -----------------------------
def test_guess_meeting_date_big12_filename_formats():
    """The three filename date shapes the phase-2 probe surfaced, one per
    board. None beats a wrong date stays in force for the ambiguous forms."""
    g = bm.guess_meeting_date
    # Durham: underscore-separated day-first
    assert g("19_JAN_2021_AGENDA_Public_external_2021118134648.pdf") == "2021-01-19"
    assert g("Jan_2021_Minutes_Public_2021217145748.pdf") is None  # month+year only
    # Halton: hyphen-separated month-first
    assert g("meeting-book-halton-police-board-meeting-june-25-2026-2.pdf") == "2026-06-25"
    assert g("Halton-Police-Board-Meeting-MAY-28-2026-2.pdf") == "2026-05-28"
    # Sudbury: compact day-first
    assert g("gspsb-agenda-public_28jan2026.pdf") == "2026-01-28"
    assert g("media-release_gspsb-meeting_28jan2026.pdf") == "2026-01-28"
    # Guards: digits/letters butted against the date are not a date
    assert g("hash_x28jan2026y.pdf") is None
    assert g("ref-2026-08 grant window") is None


def test_guess_meeting_date_existing_formats_still_parse():
    """Regression guard: the separator generalization must not break the
    TPSB/Peel-era vectors."""
    g = bm.guess_meeting_date
    assert g("Minutes - June 25, 2026") == "2026-06-25"
    assert g("agenda_2026-03-14.pdf") == "2026-03-14"
    assert g("Board meeting of 26 September 2025") == "2025-09-26"
    assert g("Sept. 26, 2025 Regular Meeting") == "2025-09-26"
    assert g("meeting 24/04/26") is None
    assert g("Item 32-05-26 discussion") is None


def test_big12_boards_config_rows():
    enabled = [b["name"] for b in bm.BOARDS if b.get("enabled", True)]
    assert enabled == [
        "Toronto Police Service Board",
        "Peel Police Services Board",
        "York Regional Police Services Board",
        "Durham Regional Police Services Board",
        "Halton Police Board",
        "Waterloo Regional Police Services Board",
        "Greater Sudbury Police Services Board",
    ]
    parked = {b["name"]: b for b in bm.BOARDS if not b.get("enabled", True)}
    assert set(parked) == {
        "Hamilton Police Service Board", "Niagara Regional Police Service Board",
        "London Police Service Board", "Windsor Police Service Board",
        "Ottawa Police Services Board"}
    for b in parked.values():
        assert b.get("parked_reason"), f"{b['name']} parked without a verdict"
    # Every board has the fields resolve_source_id needs
    for b in bm.BOARDS:
        assert b["source_name_candidates"] and b["source_id_env"]


def test_big12_enabled_boards_resolve_via_org_seed():
    from src.resolve_orgs import ORG_SEED
    seeded = {canonical for canonical, *_ in ORG_SEED}
    for b in bm.BOARDS:
        if b.get("enabled", True) and b["name"] not in (
                "Toronto Police Service Board", "Peel Police Services Board"):
            assert b["name"] in seeded, f"{b['name']} missing from ORG_SEED"
    # The services behind the enabled boards resolve too
    for svc in ("Durham Regional Police Service", "Halton Regional Police Service",
                "Waterloo Regional Police Service", "Greater Sudbury Police Service",
                "York Regional Police"):
        assert svc in seeded, f"{svc} missing from ORG_SEED"
