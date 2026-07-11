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
    urls = [u for u, _ in links]
    assert "https://board.example.ca/docs/minutes-2026-06-25.pdf" in urls
    assert "https://board.example.ca/agenda-july.html" in urls          # same-host HTML ok
    assert "https://elsewhere.example.com/minutes.pdf" in urls           # offsite PDF ok
    assert "https://elsewhere.example.com/minutes.html" not in urls      # offsite HTML dropped
    assert not any("about-the-board" in u for u in urls)                 # not minutes/agenda
    assert not any(u.startswith("mailto:") for u in urls)
    assert urls.count("https://board.example.ca/docs/minutes-2026-06-25.pdf") == 1  # deduped


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
    urls = [u for u, _ in links]
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
