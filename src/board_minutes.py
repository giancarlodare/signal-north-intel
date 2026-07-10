"""Police board minutes & agendas collector (PDF/HTML with full-text bodies).

Boards collected (hardcoded — nothing auto-adds a source; new boards are added
here by a reviewed PR, per the propose-then-approve rule):
  - Toronto Police Service Board
  - Peel Police Services Board

Design decisions:
  - Real publisher URLs only: every document row links to the PDF/HTML file on
    the board's own website. No caches, no aggregators.
  - content_hash dedupe identical to the CanadaBuys collector: sha256 of the
    publisher URL + doc_type, checked before insert, so re-runs are idempotent.
  - Stores the extracted text in documents.content (see
    migrations/2026-07-10_documents_content.sql) — the first doc_type with real
    bodies for the extraction pipeline to read.
  - robots.txt respected per host (unreachable robots.txt other than 404 =>
    treat host as disallowed), one shared polite delay between EVERY HTTP
    request, small per-board per-run document cap.
  - Board minutes from a police board are in-scope by construction, so the
    keyword filter is used only to tag defence_relevant — never to drop.

The listing URLs below are the boards' public meetings pages as best known;
they are deliberately configuration, not logic. VERIFY them with a dry run
before the first real run (and after any board website redesign):

    python -m src.board_minutes --dry-run

which fetches, parses, and lists exactly what would be inserted, writing
nothing.
"""
import argparse
import io
import logging
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests

from . import supabase_client
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

USER_AGENT = (
    "SignalNorthCollector/1.0 (+https://github.com/giancarlodare/signal-north-intel; "
    "public-record procurement research)"
)
POLITE_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT = 30
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024   # refuse PDFs larger than this
MAX_STORED_CHARS = 400_000              # cap documents.content
MAX_DOCS_PER_BOARD = 25                 # per run; backlog drains over a few days

# A link is a candidate document if its text or URL mentions minutes/agenda.
DOC_LINK_RE = re.compile(r"minutes|agenda", re.IGNORECASE)

BOARDS = [
    {
        # sources.name is matched case/whitespace-insensitively against these
        # candidates; override with the *_SOURCE_ID env var if the row differs.
        "name": "Toronto Police Service Board",
        "source_name_candidates": [
            "Toronto Police Service Board",
            "Toronto Police Services Board",
            "TPSB",
        ],
        "source_id_env": "TPSB_SOURCE_ID",
        # VERIFY: the board's public meetings page (dry run before first use).
        "listing_urls": ["https://tpsb.ca/meetings"],
    },
    {
        "name": "Peel Police Services Board",
        "source_name_candidates": [
            "Peel Police Services Board",
            "Peel Police Service Board",
            "Peel Regional Police Services Board",
        ],
        "source_id_env": "PEEL_PSB_SOURCE_ID",
        # VERIFY: the board's public meetings page (dry run before first use).
        "listing_urls": ["https://www.peelpoliceboard.ca/en/board-meetings.aspx"],
    },
]


# ---------------------------------------------------------------------------
# Politeness: robots.txt + shared delay
# ---------------------------------------------------------------------------
class PoliteFetcher:
    """All HTTP goes through here: robots.txt per host, one delay between
    every request (listings and documents alike), one User-Agent."""

    def __init__(self, delay: float = POLITE_DELAY_SECONDS):
        self.delay = delay
        self._robots: dict[str, Optional[robotparser.RobotFileParser]] = {}
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.monotonic()

    def _robots_for(self, url: str) -> Optional[robotparser.RobotFileParser]:
        host = urlparse(url).netloc
        if host in self._robots:
            return self._robots[host]
        robots_url = f"{urlparse(url).scheme}://{host}/robots.txt"
        parser: Optional[robotparser.RobotFileParser]
        try:
            self._wait()
            resp = self.session.get(robots_url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 404:
                parser = robotparser.RobotFileParser()
                parser.parse([])           # no robots.txt => everything allowed
            elif resp.ok:
                parser = robotparser.RobotFileParser()
                parser.parse(resp.text.splitlines())
            else:
                # robots.txt exists but can't be read: be conservative.
                log.warning("robots.txt for %s returned %s; skipping host", host, resp.status_code)
                parser = None
        except requests.RequestException as e:
            log.warning("robots.txt fetch failed for %s (%s); skipping host", host, e)
            parser = None
        self._robots[host] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        if parser is None:
            return False
        return parser.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> Optional[requests.Response]:
        if not self.allowed(url):
            log.info("robots.txt disallows %s; skipping", url)
            return None
        self._wait()
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()
        return resp


# ---------------------------------------------------------------------------
# HTML parsing (stdlib only — no new heavyweight dependency for link lists)
# ---------------------------------------------------------------------------
class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []   # (href, text)
        self._href: Optional[str] = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._href = href
                self._text_parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            text = " ".join(" ".join(self._text_parts).split())
            self.links.append((self._href, text))
            self._href = None
            self._text_parts = []


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self._parts).split())


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """All (absolute_url, link_text) pairs on a page."""
    collector = _LinkCollector()
    collector.feed(html)
    return [(urljoin(base_url, href), text) for href, text in collector.links]


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.text()


def find_document_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Candidate minutes/agenda documents on a listing page.

    A link qualifies if its text or URL mentions minutes/agenda, and it points
    at a PDF or a same-host page (off-host links are someone else's document —
    the provenance rule wants the publisher's copy, which for these boards is
    on their own domain).
    """
    base_host = urlparse(base_url).netloc
    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    for url, text in extract_links(html, base_url):
        if url in seen:
            continue
        if not DOC_LINK_RE.search(text) and not DOC_LINK_RE.search(url):
            continue
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            continue
        is_pdf = parsed.path.lower().endswith(".pdf")
        if not is_pdf and parsed.netloc != base_host:
            continue
        seen.add(url)
        results.append((url, text))
    return results


# ---------------------------------------------------------------------------
# Document bodies
# ---------------------------------------------------------------------------
def pdf_to_text(data: bytes) -> str:
    from pypdf import PdfReader  # lazy so the module imports without pypdf

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:   # noqa: BLE001 - a bad page shouldn't kill the doc
            continue
    return " ".join(" ".join(pages).split())


_DATE_PATTERNS = [
    # (?<!\d)/(?!\d) instead of \b: underscore is a word character, so \b
    # would fail to match dates embedded in filenames like agenda_2026-03-14.
    re.compile(r"(?<!\d)(20\d{2})[-_./](\d{1,2})[-_./](\d{1,2})(?!\d)"),
    re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2}),?\s+(20\d{2})\b",
        re.IGNORECASE,
    ),
]
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}


def guess_meeting_date(*texts: str) -> Optional[str]:
    """Best-effort meeting date from link text / URL / body. None if unsure —
    a null published_on is better than a fuzzy-parsed wrong one."""
    for text in texts:
        if not text:
            continue
        m = _DATE_PATTERNS[0].search(text)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        m = _DATE_PATTERNS[1].search(text)
        if m:
            mo = _MONTHS[m.group(1).lower()]
            return f"{int(m.group(3)):04d}-{mo:02d}-{int(m.group(2)):02d}"
    return None


# ---------------------------------------------------------------------------
# Source resolution
# ---------------------------------------------------------------------------
def _norm(name: str) -> str:
    return " ".join((name or "").split()).lower()


def resolve_source_id(board: dict, sources: list) -> Optional[str]:
    import os
    override = os.environ.get(board["source_id_env"], "").strip()
    if override:
        return override
    candidates = {_norm(c) for c in board["source_name_candidates"]}
    for row in sources:
        if _norm(row.get("name", "")) in candidates:
            return row["id"]
    return None


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
def collect_board(board: dict, source_id: str, fetcher: PoliteFetcher,
                  keywords: Keywords, limit: int, dry_run: bool) -> dict:
    stats = {"listing_pages": 0, "candidates": 0, "inserted": 0,
             "skipped_duplicate": 0, "skipped_robots": 0, "errors": 0}

    candidates: list[tuple[str, str]] = []
    for listing_url in board["listing_urls"]:
        resp = fetcher.get(listing_url)
        if resp is None:
            stats["skipped_robots"] += 1
            continue
        stats["listing_pages"] += 1
        candidates.extend(find_document_links(resp.text, listing_url))

    for url, link_text in candidates[: limit]:
        stats["candidates"] += 1
        chash = content_hash(url, "board_minutes")
        if supabase_client.get_document_by_hash(chash):
            stats["skipped_duplicate"] += 1
            continue
        try:
            resp = fetcher.get(url)
            if resp is None:
                stats["skipped_robots"] += 1
                continue
            content_length = int(resp.headers.get("Content-Length") or 0)
            if content_length > MAX_DOCUMENT_BYTES:
                log.warning("Skipping oversized document (%d bytes): %s", content_length, url)
                continue
            data = resp.content
            if len(data) > MAX_DOCUMENT_BYTES:
                log.warning("Skipping oversized document (%d bytes): %s", len(data), url)
                continue

            content_type = (resp.headers.get("Content-Type") or "").lower()
            if url.lower().endswith(".pdf") or "pdf" in content_type:
                body = pdf_to_text(data)
            else:
                body = html_to_text(data.decode(resp.encoding or "utf-8", errors="replace"))

            title = link_text or urlparse(url).path.rsplit("/", 1)[-1]
            title = f"{board['name']} — {title}"[:500]
            published_on = guess_meeting_date(link_text, url, body[:2000])
            # Tag-only: board business is in-scope by construction.
            result = evaluate(title, body[:20000], "", keywords)

            payload = {
                "source_id": source_id,
                "url": url,                      # the publisher's own copy
                "title": title,
                "doc_type": "board_minutes",
                "status": "captured",
                "published_on": published_on,
                "content_hash": chash,
                "content": body[:MAX_STORED_CHARS] or None,
                "defence_relevant": result.defence_relevant,
            }
            if dry_run:
                log.info("[dry-run] would insert: %s (%s, %d chars body, published %s)",
                         title, url, len(body), published_on)
            else:
                supabase_client.insert_document(payload)
            stats["inserted"] += 1
        except Exception:   # noqa: BLE001 - one bad document must not kill the board
            log.exception("Error collecting %s", url)
            stats["errors"] += 1

    return stats


def run(limit: int = MAX_DOCS_PER_BOARD, dry_run: bool = False) -> int:
    keywords = load_keywords()
    fetcher = PoliteFetcher()
    now = datetime.now(timezone.utc)
    sources = supabase_client.fetch_rows("sources", "id,name")
    failures = []

    for board in BOARDS:
        source_id = resolve_source_id(board, sources)
        if not source_id:
            log.error(
                "No sources row found for %s (tried names: %s). Add the row or set %s.",
                board["name"], board["source_name_candidates"], board["source_id_env"],
            )
            failures.append(board["name"])
            continue
        try:
            stats = collect_board(board, source_id, fetcher, keywords, limit, dry_run)
            log.info("Board %s: %s%s", board["name"], stats, " (DRY RUN)" if dry_run else "")
            if stats["errors"]:
                failures.append(board["name"])
            elif not dry_run:
                supabase_client.update_source_last_collected(source_id, now)
        except Exception:
            log.exception("Collection failed for %s", board["name"])
            failures.append(board["name"])

    if failures:
        log.error("Board minutes run finished with failures in: %s", ", ".join(failures))
        return 1
    log.info("Board minutes run finished successfully")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Police board minutes collector")
    parser.add_argument("--limit", type=int, default=MAX_DOCS_PER_BOARD,
                        help=f"max documents per board per run (default {MAX_DOCS_PER_BOARD})")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and parse but write nothing (verify listing configs)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(limit=args.limit, dry_run=args.dry_run))
