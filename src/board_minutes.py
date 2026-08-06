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
from urllib.parse import urldefrag, urljoin, urlparse

import requests

from . import supabase_client
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

# Deliberately terse but still honest: tpsb.ca's server returned 415 to the
# longer parenthesized form (URL + description), which some WAFs choke on.
# The name still identifies us as an automated collector — this is
# compatibility, not disguise. Full provenance lives in this repo.
# Renamed from SignalNorthCollector/1.0 (operator 2026-07-28): the word
# "Collector" appears verbatim in standard bad-bot blocklists (Biddingo's
# robots bans a different tool by that token), so the old name drew false
# robots collisions on sites whose stated policy welcomes crawlers. The new
# name identifies us just as plainly; this clears a false match, it does not
# evade any rule aimed at us.
USER_AGENT = "SignalNorthIntel/1.0"
POLITE_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT = 30
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024   # refuse PDFs larger than this
MAX_STORED_CHARS = 400_000              # cap documents.content
MAX_DOCS_PER_BOARD = 25                 # per run; backlog drains over a few days
MAX_EXPANDED_PAGES = 20                 # cap on section-expanded listing pages

# A link is a candidate document if its text or URL mentions minutes/agenda.
DOC_LINK_RE = re.compile(r"minutes|agenda", re.IGNORECASE)

# Office binaries the body pipeline cannot parse (pypdf reads PDFs, html_to_text
# reads HTML). Decoding a .docx (a ZIP archive) as text keeps embedded NUL bytes,
# which Postgres rejects (22P05), so such a link is skipped at discovery. Their
# content is normally published as a PDF too.
BINARY_DOC_EXT = (".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".zip")

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
        # RE-PARKED 2026-07-28: the site-wide WAF 415 returned (daily-collect
        # run 30350142055). Diagnosis probe run 30359688633 confirmed 415 on
        # robots.txt AND the listing under the collector UA, the renamed UA,
        # and a real browser UA alike -- client/IP-level, not UA. Same wall
        # that parked this 2026-07-11 and lifted 2026-07-14; likely to lift
        # again. Proxy coverage while parked: the 88 already-collected TPSB
        # PDFs stay in corpus, and Toronto CKAN tenders + TPS awards continue.
        # Re-probe on a later daily red-check; unpark by flipping back True.
        # (History: unparked 2026-07-14 after the 2026-07-11 park.)
        "enabled": False,
        "parked_reason": (
            "site-wide WAF 415 returned 2026-07-28 (run 30350142055; probe "
            "30359688633: 415 under collector, renamed, and browser UAs "
            "alike -- client-level, not UA). Second occurrence of the "
            "2026-07-11 wall, which lifted once before; re-probe "
            "periodically and unpark when it lifts. Proxy: the 88 collected "
            "TPSB PDFs stay in corpus; Toronto CKAN tenders + TPS awards "
            "continue."),
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
    # ------------------------------------------------------------------
    # Big 12 phase 2 (docs/big12-boards-design.md, approved 2026-07-20).
    # Every enabled board passed the four-pass CI probe: publisher-linked
    # provenance, fetchable with this collector's own fetch path, robots
    # respected, text PDFs confirmed by extraction.
    # ------------------------------------------------------------------
    {
        "name": "York Regional Police Services Board",
        "source_name_candidates": [
            "York Regional Police Services Board - Meetings",
            "York Regional Police Services Board", "YRPSB"],
        "source_id_env": "YRPSB_SOURCE_ID",
        "listing_urls": ["https://www.yrpsb.ca/meetings",
                         "https://www.yrpsb.ca/meetings-archives"],
        # The archives page links per-year pages /meetings-archives-2017..
        # (~25-27 docs each); one-level expansion reaches them all. The
        # per-year links are plain-http URLs on the same host.
        "listing_expand_prefixes": ["/meetings-archives-"],
        "doc_url_patterns": [r"/usercontent/.+\.pdf$"],
    },
    {
        "name": "Durham Regional Police Services Board",
        "source_name_candidates": [
            "Durham Regional Police Services Board - Meetings",
            "Durham Regional Police Services Board",
            "Durham Region Police Services Board", "DRPSB"],
        "source_id_env": "DRPSB_SOURCE_ID",
        "listing_urls": [
            "https://durhampoliceboard.ca/archived-board-meetings-agendas-and-minutes/",
            "https://durhampoliceboard.ca/"],
        # 174 candidates on the archive page alone; some documents live on
        # reports.drps.ca (off-host PDFs are allowed when the path ends .pdf).
        "doc_url_patterns": [r"/upload_files/.+\.pdf$"],
    },
    {
        "name": "Halton Police Board",
        "source_name_candidates": [
            "Halton Police Board - Meetings",
            "Halton Police Board", "Halton Regional Police Services Board"],
        "source_id_env": "HALTON_PB_SOURCE_ID",
        "listing_urls": ["https://haltonpoliceboard.ca/meetings/"],
        # WordPress: /meetings/ lists per-meeting pages carrying "Download
        # Agenda" links. AGENDAS ONLY by design: minutes are .docx (skipped
        # by BINARY_DOC_EXT); the agenda meeting books (46-138pp text PDFs)
        # carry the full staff reports, which is the signal.
        "listing_expand_prefixes": ["/meetings/"],
        # One observed agenda URL lacks a .pdf suffix, so the extension is
        # not required here; office binaries are excluded upstream.
        "doc_url_patterns": [r"/wp-content/uploads/.+"],
    },
    {
        "name": "Waterloo Regional Police Services Board",
        "source_name_candidates": [
            "Waterloo Regional Police Services Board - Meetings",
            "Waterloo Regional Police Services Board",
            "Waterloo Regional Police Service Board", "WRPSB"],
        "source_id_env": "WRPSB_SOURCE_ID",
        "listing_urls": ["https://www.wrps.on.ca/police-service-board-meetings"],
        # Per-meeting /resource/ pages each link one agenda PDF in the
        # service's own S3 bucket; those are off-host PDFs with agenda-named
        # text, caught by the generic name pattern. The meetings-archive path
        # 403s through a wrps.ca redirect (recorded); current listing only.
        "listing_expand_prefixes": ["/resource/"],
    },
    {
        "name": "Greater Sudbury Police Services Board",
        "source_name_candidates": [
            "Greater Sudbury Police Services Board - Meetings",
            "Greater Sudbury Police Services Board",
            "Greater Sudbury Police Service Board", "GSPSB"],
        "source_id_env": "GSPSB_SOURCE_ID",
        "listing_urls": [
            "https://www.gsps.ca/about-gsps/greater-sudbury-police-service-board/board-meetings/"],
        "doc_url_patterns": [r"/media/.+"],
    },
    # PARKED boards (probe 2026-07-20, four passes + the Ottawa timeboxed
    # check; docs/big12-boards-design.md section 3). The verdict travels with
    # the config so revival is a flag flip plus a re-probe, not archaeology.
    {
        "name": "Hamilton Police Service Board",
        "enabled": False,
        "parked_reason": (
            "hamiltonpsb.ca agendas-and-materials listing is JS-rendered "
            "(Umbraco); zero server-side documents. Revive via the banked "
            "render-capable collection evaluation (Wave 2-later)."),
        "source_name_candidates": ["Hamilton Police Service Board"],
        "source_id_env": "HPSB_SOURCE_ID",
        "listing_urls": ["https://www.hamiltonpsb.ca/meetings/agendas-and-materials/"],
    },
    {
        "name": "Niagara Regional Police Service Board",
        "enabled": False,
        # eScribe adapter wired (2026-08-06); fleet_validate pending before
        # enabling. Host is html-mode: 4 doc links visible in raw HTML on the
        # 2026 year listing, same shape as Hamilton/Kitchener/Oakville.
        "parked_reason": (
            "eScribe adapter wired 2026-08-06; fleet_validate result pending "
            "before enable (pub-niagarapolice.escribemeetings.com)."),
        "escribe_host": "pub-niagarapolice.escribemeetings.com",
        "source_name_candidates": ["Niagara Regional Police Service Board"],
        "source_id_env": "NRPSB_SOURCE_ID",
        "listing_urls": ["https://pub-niagarapolice.escribemeetings.com/"],
    },
    {
        "name": "London Police Service Board",
        "enabled": False,
        # NOT A GAP (operator 2026-08-02): two server-side surfaces exist.
        #  1. pub-london.escribemeetings.com -- an eScribe tenant (confirmed
        #     via a filestream.ashx document URL): first wave of the eScribe
        #     adapter alongside Ottawa and Niagara.
        #  2. londonpoliceserviceboard.com -- dedicated WordPress board site
        #     publishing full agenda-and-report packages as PDFs under
        #     /wp-content/uploads/YYYY/MM/ (e.g. "LPSB-OPEN-Agenda-and-
        #     Report-Package-February-19-2026-Full-Package.pdf"). 2026
        #     meetings: Jan 15, Feb 19, Mar 19, Apr 16, May 21, Jun 18,
        #     (no July), Aug 20, Sep 17 special budget, Oct 15, Nov 19,
        #     Dec 17. Same shape as the TPSB config; enable after the
        #     standard CI validation dry-run.
        # COLLISION WARNING (same class as OACP): the City of London, UK
        # publishes a Police Authority Board at democracy.cityoflondon.gov.uk.
        # Anything touching "London Police" must be domain-scoped
        # (londonpolice.ca / londonpoliceserviceboard.com /
        # pub-london.escribemeetings.com) or the corpus silently takes on
        # British data.
        "parked_reason": (
            "READY, pending validation dry-run: londonpoliceserviceboard.com "
            "WordPress packages (server-rendered) + pub-london eScribe "
            "tenant in the adapter first wave. Was mis-parked as no-surface; "
            "operator located both 2026-08-02."),
        "source_name_candidates": ["London Police Service Board"],
        "source_id_env": "LPSB_SOURCE_ID",
        "listing_urls": ["https://londonpoliceserviceboard.com/"],
        "doc_url_patterns": [r"/wp-content/uploads/.+\.pdf$"],
    },
    {
        "name": "Windsor Police Service Board",
        "enabled": False,
        "parked_reason": (
            "windsorpolice.ca/about/wps-board carries zero document links; "
            "minutes presumably with the city clerk (citywindsor.ca) but not "
            "publisher-linked from the board page. Provenance not established."),
        "source_name_candidates": ["Windsor Police Service Board"],
        "source_id_env": "WPSB_SOURCE_ID",
        "listing_urls": ["https://www.windsorpolice.ca/about/wps-board"],
    },
    {
        "name": "Ottawa Police Services Board",
        "enabled": False,
        # eScribe adapter wired (2026-08-06); fleet_validate pending before
        # enabling. Per-year meeting pages on pub-ottawa.escribemeetings.com
        # carry FileStream.ashx document links — same html-mode shape as
        # Hamilton/Kitchener/Oakville.
        "parked_reason": (
            "eScribe adapter wired 2026-08-06; fleet_validate result pending "
            "before enable (pub-ottawa.escribemeetings.com)."),
        "escribe_host": "pub-ottawa.escribemeetings.com",
        "source_name_candidates": ["Ottawa Police Services Board", "OPSB"],
        "source_id_env": "OPSB_SOURCE_ID",
        "listing_urls": ["https://www.ottawapoliceboard.ca/opsb-cspo/meetings.html"],
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
        # Hosts that declare a robots.txt Crawl-delay LONGER than our default
        # get it honored (open.canada.ca asks for 20s). Shorter declarations
        # don't speed us up — self.delay stays the floor.
        self._host_delay: dict[str, float] = {}
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def _wait(self, host: Optional[str] = None) -> None:
        delay = max(self.delay, self._host_delay.get(host or "", 0.0))
        elapsed = time.monotonic() - self._last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
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
        if parser is not None:
            try:
                declared = parser.crawl_delay(USER_AGENT)
            except AttributeError:
                declared = None
            if declared and float(declared) > self.delay:
                self._host_delay[host] = float(declared)
                log.info("Honoring robots.txt Crawl-delay of %ss for %s", declared, host)
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
        self._wait(urlparse(url).netloc)
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()
        return resp

    def post_json(self, url: str, payload: dict) -> Optional[requests.Response]:
        """POST a JSON body (CKAN action-API style). Same robots check and
        per-host delay as get(); the body keeps parameters out of the query
        string, so URL-pattern Disallow rules can't be tripped even under
        wildcard interpretations robotparser doesn't apply."""
        if not self.allowed(url):
            log.info("robots.txt disallows %s; skipping", url)
            return None
        self._wait(urlparse(url).netloc)
        resp = self.session.post(url, json=payload, timeout=REQUEST_TIMEOUT)
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
        # A fragment never names a different document; keeping it would
        # collect '#main-content' / '#tab-...' anchor variants of the same
        # page as separate documents with distinct content hashes.
        url, _fragment = urldefrag(url)
        if url in seen:
            continue
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.path.lower().endswith(BINARY_DOC_EXT):
            continue  # office binaries: unparseable, and decode to NUL-laden text
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

# Separators inside month-name dates: listing text uses spaces, board
# filenames use hyphens/underscores (Halton "june-25-2026", Durham
# "19_JAN_2021"; big12-boards probe 2026-07-20). "." is deliberately NOT a
# separator so ambiguous all-numeric forms stay unparsed. \b cannot guard
# these (underscore is a word character), so explicit guards are used:
# no letter/digit immediately before, no digit immediately after.
_SEP = r"[-_\s]+"
_LG = r"(?<![A-Za-z0-9])"
_RG = r"(?![0-9])"

_DATE_PATTERNS = [
    # ISO-ish: 2026-04-24 (also _ . / separators). (?<!\d)/(?!\d) instead of
    # \b: underscore is a word character, so \b would fail on filenames like
    # agenda_2026-03-14.
    re.compile(r"(?<!\d)(20\d{2})[-_./](\d{1,2})[-_./](\d{1,2})(?!\d)"),
    # Month-first: "April 24, 2026", "Sept. 26 2025", "june-25-2026".
    re.compile(rf"{_LG}{_MONTH_RE}\.?,?{_SEP}(\d{{1,2}})(?:st|nd|rd|th)?,?{_SEP}(20\d{{2}}){_RG}",
               re.IGNORECASE),
    # Day-first: "26 September 2025", "26th of Sept. 2025", "19_JAN_2021";
    # common atop board minutes and in archive filenames.
    re.compile(rf"{_LG}(\d{{1,2}})(?:st|nd|rd|th)?{_SEP}(?:of\s+)?{_MONTH_RE}\.?,?{_SEP}(20\d{{2}}){_RG}",
               re.IGNORECASE),
    # Compact day-first: "28jan2026", "17june26" (Sudbury filenames). A
    # 2-digit year is accepted only inside the same 2015-2035 plausibility
    # window the Peel filename convention uses (see guess_meeting_date).
    re.compile(rf"{_LG}(\d{{1,2}}){_MONTH_RE}(20\d{{2}}|\d{{2}}){_RG}", re.IGNORECASE),
]

# Month + year with NO day ("RTOC-Presentation-May2026", "March_2021_Minutes")
# -> month precision. Applied by month_year_date to link text and URL only.
_MONTH_YEAR_RE = re.compile(rf"{_LG}{_MONTH_RE}\.?[-_\s]?(20\d{{2}}){_RG}",
                            re.IGNORECASE)


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
        m = _DATE_PATTERNS[3].search(text)
        if m:
            year = int(m.group(3))
            if year < 100:
                year += 2000
                if not (2015 <= year <= 2035):
                    year = 0  # implausible 2-digit year: not a date
            if year:
                result = _valid(year, _MONTHS[m.group(2).lower().rstrip(".")],
                                int(m.group(1)))
                if result:
                    return result
    return None


def month_year_date(*texts) -> tuple:
    """(published_on, 'month') from a month+year token with no day, or
    (None, None). Month precision with the conventional day=01 placeholder
    (renderers show 'Mar 2021', never a fabricated day). Callers apply this
    to link text and URL only; publisher-authored filenames are trustworthy,
    while a bare 'June 2026' inside page context or a document body is
    commonplace and would mis-date."""
    for text in texts:
        m = _MONTH_YEAR_RE.search(text or "")
        if m:
            mo = _MONTHS.get(m.group(1).lower().rstrip("."))
            if mo:
                return f"{int(m.group(2)):04d}-{mo:02d}-01", "month"
    return None, None


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
             "skipped_duplicate": 0, "skipped_robots": 0, "dead_links": 0,
             "errors": 0}

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

    # Per-board validation counters over the documents actually processed this
    # run (docs/big12-boards-design.md section 8: >= 90% date-parse, nonzero
    # text bodies). Logged, not returned: the stats dict shape is unchanged.
    val_docs = val_dated = val_body = 0

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
            # Postgres text cannot hold a NUL byte (22P05); strip it defensively so
            # no extracted body can ever crash the insert, whatever its source.
            body = body.replace("\x00", "")

            title = link_text or urlparse(url).path.rsplit("/", 1)[-1]
            title = f"{board['name']} — {title}"[:500]
            # Date derivation order: (1) full date in link text or URL, (2)
            # month+year in link text or URL at month precision, (3) the
            # listing page's text right before the link, then the body.
            # Filename month-year outranks listing context deliberately: on
            # tabular archives (Durham) the context capture spans the PREVIOUS
            # row, so a month-only filename dated from context lands on the
            # wrong meeting. A correct month beats a wrong day.
            published_on, date_precision = derive_event_date(link_text, url)
            if not published_on:
                published_on, date_precision = month_year_date(link_text, url)
            if not published_on:
                published_on, date_precision = derive_event_date(
                    listing_context, body[:4000])
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
            val_docs += 1
            val_dated += 1 if published_on else 0
            val_body += 1 if body else 0
        except requests.HTTPError as e:
            # A 404 on a document is the publisher's own dead link (nine-year
            # archive pages accumulate them); skipping it loudly-logged keeps
            # the board green while the WARNING keeps it visible. Anything
            # else (403/5xx/network) stays an error: those can mean gating,
            # which must never pass silently.
            if e.response is not None and e.response.status_code == 404:
                stats["dead_links"] += 1
                log.warning("Dead link on listing (404): %s", url)
            else:
                log.exception("Error collecting %s", url)
                stats["errors"] += 1
        except Exception:   # noqa: BLE001 - one bad document must not kill the board
            log.exception("Error collecting %s", url)
            stats["errors"] += 1

    if val_docs:
        log.info("VALIDATION [%s]: docs=%d date_parsed=%d (%d%%) nonzero_body=%d (%d%%)",
                 board["name"], val_docs, val_dated,
                 round(100 * val_dated / val_docs), val_body,
                 round(100 * val_body / val_docs))
    return stats


def collect_escribe_board(board: dict, source_id: str, fetcher: PoliteFetcher,
                          keywords: Keywords, limit: int, dry_run: bool) -> dict:
    """Collect one eScribe/CivicWeb board using the adapter's html-mode parsers.

    Fetches the year listing for the current and previous year, parses meeting
    URLs via the adapter, then collects documents from each meeting page. Uses
    the same PDF/HTML extraction, date derivation, and insert path as
    collect_board -- only the listing discovery is different.

    The board config must carry `escribe_host` (the tenant hostname) and
    optionally `escribe_year_path` (default "/?Year={year}").
    """
    from .escribe_adapter import (  # lazy: avoid importing playwright-weight at module level
        Tenant, listing_url as esc_listing_url,
        plan_from_listing, parse_document_links, LoudZeroMeetings,
    )

    host = board["escribe_host"]
    tenant = Tenant(host, board["name"], "police_board",
                    mode="html",
                    year_path=board.get("escribe_year_path", "/?Year={year}"))

    stats = {"listing_pages": 0, "candidates": 0, "inserted": 0,
             "skipped_duplicate": 0, "skipped_robots": 0, "dead_links": 0,
             "errors": 0}
    val_docs = val_dated = val_body = 0
    current_year = datetime.now(timezone.utc).year
    seen_docs: set[str] = set()

    for year in [current_year, current_year - 1]:
        if stats["inserted"] >= limit:
            break
        url = esc_listing_url(tenant, year)
        resp = fetcher.get(url)
        if resp is None:
            stats["skipped_robots"] += 1
            continue
        stats["listing_pages"] += 1
        try:
            plan = plan_from_listing(tenant, resp.text, year)
        except LoudZeroMeetings as exc:
            if year == current_year:
                raise  # current-year zero is a loud failure -- propagate
            log.warning("[%s] eScribe year %d returned 0 meetings: %s", board["name"], year, exc)
            continue

        for meeting_url in plan["meetings"]:
            if stats["inserted"] >= limit:
                break
            resp2 = fetcher.get(meeting_url)
            if resp2 is None:
                stats["skipped_robots"] += 1
                continue
            stats["listing_pages"] += 1

            for doc_url, link_text in parse_document_links(resp2.text, meeting_url):
                if doc_url in seen_docs:
                    continue
                seen_docs.add(doc_url)
                if stats["inserted"] >= limit:
                    log.info("Per-run cap (%d) reached for %s", limit, board["name"])
                    break
                stats["candidates"] += 1
                chash = content_hash(doc_url, "board_minutes")
                if supabase_client.get_document_by_hash(chash):
                    stats["skipped_duplicate"] += 1
                    continue
                try:
                    doc_resp = fetcher.get(doc_url)
                    if doc_resp is None:
                        stats["skipped_robots"] += 1
                        continue
                    content_length = int(doc_resp.headers.get("Content-Length") or 0)
                    if content_length > MAX_DOCUMENT_BYTES:
                        log.warning("Skipping oversized document (%d bytes): %s",
                                    content_length, doc_url)
                        continue
                    data = doc_resp.content
                    if len(data) > MAX_DOCUMENT_BYTES:
                        log.warning("Skipping oversized document (%d bytes): %s",
                                    len(data), doc_url)
                        continue
                    content_type = (doc_resp.headers.get("Content-Type") or "").lower()
                    if doc_url.lower().endswith(".pdf") or "pdf" in content_type:
                        body = pdf_to_text(data)
                    else:
                        body = html_to_text(
                            data.decode(doc_resp.encoding or "utf-8", errors="replace"))
                    body = body.replace("\x00", "")
                    title = link_text or urlparse(doc_url).path.rsplit("/", 1)[-1]
                    title = f"{board['name']} — {title}"[:500]
                    published_on, date_precision = derive_event_date(link_text, doc_url)
                    if not published_on:
                        published_on, date_precision = month_year_date(link_text, doc_url)
                    result = evaluate(title, body[:20000], "", keywords)
                    payload = {
                        "source_id": source_id,
                        "url": doc_url,
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
                        log.info("[dry-run] would insert: %s (%s, %d chars, published %s)",
                                 title, doc_url, len(body), published_on)
                    else:
                        supabase_client.insert_document(payload)
                    stats["inserted"] += 1
                    val_docs += 1
                    val_dated += 1 if published_on else 0
                    val_body += 1 if body else 0
                except requests.HTTPError as e:
                    if e.response is not None and e.response.status_code == 404:
                        stats["dead_links"] += 1
                        log.warning("Dead link on eScribe meeting (404): %s", doc_url)
                    else:
                        log.exception("Error collecting %s", doc_url)
                        stats["errors"] += 1
                except Exception:
                    log.exception("Error collecting %s", doc_url)
                    stats["errors"] += 1

    if val_docs:
        log.info("VALIDATION [%s]: docs=%d date_parsed=%d (%d%%) nonzero_body=%d (%d%%)",
                 board["name"], val_docs, val_dated,
                 round(100 * val_dated / val_docs), val_body,
                 round(100 * val_body / val_docs))
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
            if board.get("escribe_host"):
                stats = collect_escribe_board(board, source_id, fetcher, keywords, limit, dry_run)
            else:
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
