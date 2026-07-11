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

# Deliberately terse but still honest: tpsb.ca's server returned 415 to the
# longer parenthesized form (URL + description), which some WAFs choke on.
# The name still identifies us as an automated collector — this is
# compatibility, not disguise. Full provenance lives in this repo.
USER_AGENT = "SignalNorthCollector/1.0"
POLITE_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT = 30
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024   # refuse PDFs larger than this
MAX_STORED_CHARS = 400_000              # cap documents.content
MAX_DOCS_PER_BOARD = 25                 # per run; backlog drains over a few days
MAX_EXPANDED_PAGES = 20                 # cap on section-expanded listing pages

# A link is a candidate document if its text or URL mentions minutes/agenda.
DOC_LINK_RE = re.compile(r"minutes|agenda", re.IGNORECASE)

BOARDS = [
    {
        # sources.name is matched case/whitespace-insensitively against these
        # candidates; override with the *_SOURCE_ID env var if the row differs.
        "name": "Toronto Police Service Board",
        "source_name_candidates": [
            "Toronto Police Service Board — Agendas & Minutes",  # actual sources.name
            "Toronto Police Service Board",
            "Toronto Police Services Board",
            "TPSB",
        ],
        "source_id_env": "TPSB_SOURCE_ID",
        # PARKED 2026-07-11: tpsb.ca's WAF returns 415 to this client
        # SITE-WIDE — robots.txt AND the listing page — regardless of
        # User-Agent, even though robots.txt (verified in-browser) allows all
        # crawling. Per the operator's call: park rather than fight the WAF.
        # Unparking options: contact the board office about collector access,
        # or revisit if the WAF policy changes. Flip enabled to True to retry.
        "enabled": False,
        "parked_reason": "tpsb.ca WAF 415s all collector requests (2026-07-11)",
        # Verified in-browser 2026-07-10 (the earlier /meetings guess 404s).
        # Structure: year headings, then meeting dates, some with links.
        "listing_urls": ["https://tpsb.ca/home/current-and-past-meetings/"],
        # TPSB documents are same-host PDFs under /wp-content/uploads/ with
        # link texts like "Read Agenda", "Read the Minutes" (caught by the
        # generic pattern) but also "Item 19" / "New Business" (not caught) —
        # so any on-host uploads PDF is a candidate. YouTube and other
        # non-PDF links are excluded by the .pdf-only pattern.
        "doc_url_patterns": [r"/wp-content/uploads/.+\.pdf$"],
    },
    {
        "name": "Peel Police Services Board",
        "source_name_candidates": [
            "Peel Police Service Board — Meetings",              # actual sources.name
            "Peel Police Services Board",
            "Peel Police Service Board",
            "Peel Regional Police Services Board",
        ],
        "source_id_env": "PEEL_PSB_SOURCE_ID",
        # Verified in-browser 2026-07-10 (the earlier /en/... guess 404s).
        "listing_urls": [
            "https://www.peelpoliceboard.ca/meetings-updates/presentations/#2026",
            "https://www.peelpoliceboard.ca/reports/",
            # news-and-updates: HTML posts (paginated ×16), not PDFs. Page 1 is
            # scanned for any /media PDFs it links; collecting the posts
            # themselves as documents is a noted follow-up, not built here.
            "https://www.peelpoliceboard.ca/news-and-updates/",
        ],
        # /reports/ links out to sub-pages (Annual Performance, Corporate Risk,
        # Budget, Public Complaints, Missing Persons, …) that carry the PDFs;
        # same-host links under this prefix are fetched as additional listing
        # pages (one level deep, capped).
        "listing_expand_prefixes": ["/reports/"],
        # Peel's documents are same-host PDFs at /media/{hash}/{slug}.pdf with
        # descriptive link text that never says "minutes"/"agenda", so the
        # generic name pattern misses them all. Any on-host /media PDF is a
        # candidate; the title comes from the link text. The listings span
        # 2017–2026 — the per-run cap pages through that backlog over multiple
        # runs because duplicates don't consume the cap.
        "doc_url_patterns": [r"/media/.+\.pdf$"],
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
            if resp.ok:
                parser = robotparser.RobotFileParser()
                parser.parse(resp.text.splitlines())
            elif 400 <= resp.status_code < 500:
                # RFC 9309 §2.3.1.3: robots.txt "unavailable" (4xx) => crawlers
                # MAY access any resources. tpsb.ca's WAF 415s our client's
                # robots.txt request even though the file itself (verified
                # in-browser 2026-07-10: empty Disallow, Yoast block) allows
                # all crawling — so treating 4xx as allow follows both the RFC
                # and the publisher's stated policy.
                log.info("robots.txt for %s returned %s (4xx); allow-all per RFC 9309",
                         host, resp.status_code)
                parser = robotparser.RobotFileParser()
                parser.parse([])
            else:
                # 5xx: robots.txt exists but the server is unwell — stay out.
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
    """Collects (href, text, context): context is the page text immediately
    PRECEDING the link — listing pages put the meeting date in a heading or
    row label next to the link, not inside it (option-3 listing-context
    capture; see derive_event_date)."""

    _CONTEXT_CHARS = 200

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str, str]] = []   # (href, text, context)
        self._href: Optional[str] = None
        self._text_parts: list[str] = []
        self._context = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._href = href
                self._text_parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._text_parts.append(data)
        else:
            self._context = (self._context + " " + data)[-self._CONTEXT_CHARS:]

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            text = " ".join(" ".join(self._text_parts).split())
            context = " ".join(self._context.split())
            self.links.append((self._href, text, context))
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
    return [(u, t) for u, t, _ in extract_links_with_context(html, base_url)]


def extract_links_with_context(html: str, base_url: str) -> list[tuple[str, str, str]]:
    """(absolute_url, link_text, preceding_page_text) triples."""
    collector = _LinkCollector()
    collector.feed(html)
    return [(urljoin(base_url, href), text, ctx)
            for href, text, ctx in collector.links]


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.text()


def find_document_links(html: str, base_url: str,
                        extra_url_patterns: Optional[list] = None) -> list[tuple[str, str]]:
    """Candidate minutes/agenda documents on a listing page.

    A link qualifies if its text or URL mentions minutes/agenda, OR its
    same-host URL path matches one of the board's extra_url_patterns (compiled
    regexes) — for boards like Peel whose documents live at /media/*.pdf with
    descriptive link text that never says minutes/agenda. Either way it must
    point at a PDF or a same-host page (off-host links are someone else's
    document — the provenance rule wants the publisher's copy).
    """
    base_host = urlparse(base_url).netloc
    seen: set[str] = set()
    results: list[tuple[str, str, str]] = []
    for url, text, context in extract_links_with_context(html, base_url):
        if url in seen:
            continue
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            continue
        named = bool(DOC_LINK_RE.search(text) or DOC_LINK_RE.search(url))
        extra = parsed.netloc == base_host and any(
            p.search(parsed.path) for p in (extra_url_patterns or []))
        if not named and not extra:
            continue
        is_pdf = parsed.path.lower().endswith(".pdf")
        if not is_pdf and parsed.netloc != base_host:
            continue
        seen.add(url)
        results.append((url, text, context))
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


# Month name (full or abbreviated, optional trailing period) → 1..12.
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}
for _full, _n in list(_MONTHS.items()):
    _MONTHS[_full[:3]] = _n
_MONTHS["sept"] = 9
_MONTH_RE = (r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
             r"Jul(?:y)?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|"
             r"Nov(?:ember)?|Dec(?:ember)?)")

_DATE_PATTERNS = [
    # ISO-ish: 2026-04-24 (also _ . / separators). (?<!\d)/(?!\d) instead of
    # \b: underscore is a word character, so \b would fail on filenames like
    # agenda_2026-03-14.
    re.compile(r"(?<!\d)(20\d{2})[-_./](\d{1,2})[-_./](\d{1,2})(?!\d)"),
    # Month-first: "April 24, 2026", "Sept. 26 2025".
    re.compile(rf"\b{_MONTH_RE}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(20\d{{2}})\b",
               re.IGNORECASE),
    # Day-first: "26 September 2025", "26th of Sept. 2025" — common atop
    # board minutes and presentations.
    re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH_RE}\.?,?\s+(20\d{{2}})\b",
               re.IGNORECASE),
]


def _valid(y: int, mo: int, d: int) -> Optional[str]:
    if 1 <= mo <= 12 and 1 <= d <= 31:
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def guess_meeting_date(*texts: str) -> Optional[str]:
    """Best-effort meeting date from link text / URL / body. None if unsure —
    a null published_on is better than a fuzzy-parsed wrong one. (Ambiguous
    all-numeric forms like 24/04/26 are deliberately not parsed.)"""
    for text in texts:
        if not text:
            continue
        m = _DATE_PATTERNS[0].search(text)
        if m:
            result = _valid(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if result:
                return result
        m = _DATE_PATTERNS[1].search(text)
        if m:
            result = _valid(int(m.group(3)), _MONTHS[m.group(1).lower().rstrip(".")],
                            int(m.group(2)))
            if result:
                return result
        m = _DATE_PATTERNS[2].search(text)
        if m:
            result = _valid(int(m.group(3)), _MONTHS[m.group(2).lower().rstrip(".")],
                            int(m.group(1)))
            if result:
                return result
    return None


# Peel's document slugs open with {agenda-item}-{MM}-{YY} (e.g. 33-04-26- =
# item 33, April 2026 meeting). Verified against every document where a full
# date was independently derivable. Decodes the meeting MONTH only — the day
# is not present — so dates derived this way carry date_precision='month'
# with the conventional day=01 placeholder. Renderers must show "Apr 2026",
# never a fabricated full date (docs/ROADMAP.md).
_ITEM_MONTH_YEAR_RE = re.compile(r"/media/[^/]+/\d{1,2}-(\d{2})-(\d{2})-")


def derive_event_date(*texts: str) -> tuple:
    """(published_on, date_precision) from link text / url / listing context /
    body — or (None, None). Full parseable dates win ('day'); the Peel
    item-month-year filename convention is the month-precision fallback."""
    full = guess_meeting_date(*texts)
    if full:
        return full, "day"
    for text in texts:
        m = _ITEM_MONTH_YEAR_RE.search(text or "")
        if m:
            mo, yy = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 15 <= yy <= 35:
                return f"20{yy:02d}-{mo:02d}-01", "month"
    return None, None


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

    extra_patterns = [re.compile(p, re.IGNORECASE)
                      for p in board.get("doc_url_patterns", [])]
    expand_prefixes = board.get("listing_expand_prefixes", [])
    configured = list(board["listing_urls"])
    queue = list(configured)
    visited: set[str] = set()
    expanded = 0
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    while queue:
        listing_url = queue.pop(0)
        if listing_url in visited:
            continue
        visited.add(listing_url)
        resp = fetcher.get(listing_url)
        if resp is None:
            stats["skipped_robots"] += 1
            continue
        stats["listing_pages"] += 1
        html = resp.text
        for url, text, context in find_document_links(html, listing_url, extra_patterns):
            if url not in seen_urls:      # dedup across listing pages
                seen_urls.add(url)
                candidates.append((url, text, context))
        # Section expansion, ONE level deep: same-host non-PDF links under a
        # configured prefix (e.g. Peel's /reports/ sub-pages) are fetched as
        # additional listing pages. Only links found on the CONFIGURED pages
        # expand — pages discovered by expansion never expand further, so this
        # cannot crawl beyond the section.
        if expand_prefixes and listing_url in configured:
            host = urlparse(listing_url).netloc
            for url, _text in extract_links(html, listing_url):
                parsed = urlparse(url)
                if (expanded < MAX_EXPANDED_PAGES
                        and parsed.netloc == host
                        and not parsed.path.lower().endswith(".pdf")
                        and any(parsed.path.startswith(p) for p in expand_prefixes)
                        and url not in visited and url not in configured):
                    queue.append(url)
                    expanded += 1

    # The cap counts NEW documents, not candidates: already-collected docs are
    # skipped without consuming it. That's what lets a multi-year backlog page
    # through over successive runs instead of stalling on the first 25 forever.
    for url, link_text, listing_context in candidates:
        if stats["inserted"] >= limit:
            log.info("Per-run cap (%d) reached; %d candidates left for future runs",
                     limit, len(candidates) - stats["candidates"])
            break
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
            # Date derivation order: link text, URL, the listing page's text
            # right before the link (meeting dates live in headings/rows next
            # to links), then the document body. Full dates -> 'day'; the Peel
            # item-month-year filename convention -> 'month'.
            published_on, date_precision = derive_event_date(
                link_text, url, listing_context, body[:4000])
            # Tag-only: board business is in-scope by construction.
            result = evaluate(title, body[:20000], "", keywords)

            payload = {
                "source_id": source_id,
                "url": url,                      # the publisher's own copy
                "title": title,
                "doc_type": "board_minutes",
                "status": "captured",
                "published_on": published_on,
                "date_precision": date_precision or "day",
                "content_hash": chash,
                "content": body[:MAX_STORED_CHARS] or None,
                "defence_relevant": result.defence_relevant,
            }
            if dry_run:
                log.info("[dry-run] would insert: %s (%s, %d chars body, published %s [%s])",
                         title, url, len(body), published_on, date_precision or "day")
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
        if not board.get("enabled", True):
            log.info("Board %s is PARKED (%s); skipping",
                     board["name"], board.get("parked_reason", "no reason recorded"))
            continue
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
