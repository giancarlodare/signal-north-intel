"""Ontario grants collector — the province's public funding directory.

Grant money is a leading indicator of downstream procurement 6-18 months out,
often sub-threshold and invisible to tender monitoring (docs/ROADMAP.md), so
grant programs are collected as first-class documents.

Two listing pages, both server-rendered HTML (CI-probe-verified 2026-07-11):

  OPEN   /page/available-funding-opportunities-ontario-government  (daily)
         Each program is an <h2> section carrying: Status badge
         (OPEN/RESTRICTED), a bare Ministry paragraph, then h3/h4 subsections
         Deadline / Description / Eligibility / Program guidelines / Contacts.
         All of it is captured into the document text. The DEADLINE is the
         event date (published_on) where a full date parses; "ongoing" or
         unparseable deadlines are honestly null.
  CLOSED /page/closed-funding-opportunities-ontario-government     (one-time)
         Flat archive: <h3> name, description paragraph, <h4> ministry,
         Status: Closed. A baseline corpus, not news — entries carry no
         dates, so published_on is null, never fabricated. Crawled once via
         --baseline.

Design decisions:
  - Keyword scope filter ON (operator-specified): the directory spans every
    ministry; only public-safety programs are kept (SCOPE_TERMS below).
    keywords.txt still runs, but only to tag defence_relevant — the scope
    terms are the drop decision.
  - Program identity for dedupe = listing URL + program name + parsed
    deadline + status. A NEW program inserts; a DEADLINE or STATUS change
    re-inserts as a fresh document (per the operator: new programs and
    deadline changes ARE the signal). Description edits alone do not.
  - Document URLs use a text fragment (#:~:text=<program name>) on the
    listing page: still the publisher's own page (provenance rule), resolves
    to the exact program section in modern browsers, and keeps each program's
    URL distinct.
  - Program guidelines: most programs link public guideline documents in the
    Central Forms Repository (forms.mgcs.gov.on.ca). Those are the published
    evaluation rubrics — followed and captured into the program record (a
    rubric-library asset). Where guidelines sit behind a Transfer Payment
    Ontario login or are by-request-only, the program is still collected
    with guidelines_gated=true rather than skipped (operator rule).
  - Everything else standard: PoliteFetcher (robots + 2s delay), content_hash
    check-then-insert, per-run cap counts NEW docs only, --dry-run/--limit,
    log-and-continue per program with a systemic exit only when the listing
    itself cannot be collected.

    python -m src.grants_ontario --dry-run             # open page, preview
    python -m src.grants_ontario --baseline --dry-run  # closed archive, preview
"""
import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote, urlparse

from . import supabase_client
from .board_minutes import (MAX_DOCUMENT_BYTES, MAX_STORED_CHARS, PoliteFetcher,
                            extract_links, guess_meeting_date, html_to_text,
                            pdf_to_text)
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

OPEN_LISTING_URL = (
    "https://www.ontario.ca/page/available-funding-opportunities-ontario-government")
CLOSED_LISTING_URL = (
    "https://www.ontario.ca/page/closed-funding-opportunities-ontario-government")

MAX_DOCS_PER_RUN = 25
BASELINE_LIMIT = 200                 # closed archive is ~160 entries pre-filter
MAX_GUIDELINE_FETCHES_PER_PROGRAM = 3

# Public-safety scope (operator-specified 2026-07-11): the funding directory
# spans every ministry; keep only programs in our lane. Substring match, same
# convention as rss_collector.matches_scope. "solicitor general" and "public
# safety" follow the Ontario Newsroom scope precedent — SolGen is the
# province's public-safety ministry, so its programs are in-lane by
# construction.
SCOPE_TERMS = [
    "police", "policing", "fire", "emergency", "correction", "border",
    "security", "anti-hate", "anti hate", "trafficking",
    "first nations policing", "solicitor general", "public safety",
]

# Hosts whose guideline links are public documents we can follow. Anything
# else in a guidelines section (tpon.gov.on.ca login, mailto:) is a gate.
PUBLIC_GUIDELINE_HOSTS = {
    "forms.mgcs.gov.on.ca",                    # Central Forms Repository
    "www.grants.gov.on.ca", "grants.gov.on.ca",  # legacy Grants Portal
    "files.ontario.ca",
    "www.ontario.ca", "ontario.ca",
}

# CFR dataset pages are CKAN-themed: each file is a <li class="resource-item"
# title="English - … / French - …"> with a download link ending .pdf. The
# French copies are skipped so they don't crowd the extraction window.
_CFR_RESOURCE_RE = re.compile(
    r'<li class="resource-item"[^>]*title="([^"]*)"(.*?)</li>', re.S | re.I)

_STATUS_RE = re.compile(r"Status:\s*<span[^>]*>([^<]+)</span>", re.I)
_MINISTRY_RE = re.compile(
    r"((?:Ministry (?:of|for)|Treasury Board|Cabinet Office)[^<]{0,150}?)\s*<", re.I)
_SUBHEAD_RE = re.compile(r"<h([34])[^>]*>(.*?)</h\1>", re.S | re.I)


# ---------------------------------------------------------------------------
# HTML sectioning (the pages are machine-generated Drupal output with clean,
# regular tags — regex sectioning over the raw HTML is stable here)
# ---------------------------------------------------------------------------
def split_sections(html: str, level: int) -> list:
    """(heading_text, body_html) for each <h{level}>; a section's body runs to
    the next heading of the same or higher level (so closed-archive h3
    sections stop at the next letter-group h2)."""
    heading_re = re.compile(rf"<h{level}[^>]*>(.*?)</h{level}>", re.S | re.I)
    boundary_re = re.compile(rf"<h[1-{level}]\b", re.I)
    sections = []
    for m in heading_re.finditer(html):
        nxt = boundary_re.search(html, m.end())
        end = nxt.start() if nxt else len(html)
        sections.append((html_to_text(m.group(1)), html[m.end():end]))
    return sections


def subsections(section_html: str) -> list:
    """(label, body_html) chunks of a program section split on its h3/h4
    subheadings; the text before the first subheading arrives with label ''."""
    parts = []
    prev_label, prev_end = "", 0
    for m in _SUBHEAD_RE.finditer(section_html):
        parts.append((prev_label, section_html[prev_end:m.start()]))
        prev_label = html_to_text(m.group(2))
        prev_end = m.end()
    parts.append((prev_label, section_html[prev_end:]))
    return parts


def parse_status(section_html: str) -> Optional[str]:
    m = _STATUS_RE.search(section_html)
    return m.group(1).strip().upper() if m else None


def parse_ministry(section_html: str) -> Optional[str]:
    m = _MINISTRY_RE.search(section_html)
    return " ".join(m.group(1).split()) if m else None


def matches_scope(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in SCOPE_TERMS)


def program_url(listing_url: str, name: str) -> str:
    """The listing page with a text fragment locating the program's section —
    the publisher's own page, one distinct URL per program."""
    return f"{listing_url}#:~:text={quote(name, safe='')}"


# ---------------------------------------------------------------------------
# Guidelines follow-through (Central Forms Repository etc.)
# ---------------------------------------------------------------------------
def guideline_links(section_html: str, base_url: str) -> tuple:
    """(public_urls, gated) from a program's guidelines subsection(s).

    gated=True when the program HAS a guidelines section but it offers no
    public-host link — the TPON-login and contact-your-adviser cases. A
    program with no guidelines section at all is simply (nothing, False):
    absence is not a gate.
    """
    urls, saw_section = [], False
    for label, body_html in subsections(section_html):
        if "guideline" not in label.lower():
            continue
        saw_section = True
        for url, _text in extract_links(body_html, base_url):
            if urlparse(url).scheme in ("http", "https") and \
                    urlparse(url).netloc.lower() in PUBLIC_GUIDELINE_HOSTS:
                urls.append(url)
    return urls, (saw_section and not urls)


def _french_pdf_urls(page_html: str) -> set:
    """PDF hrefs inside CFR resource items titled 'French - …'."""
    skip: set = set()
    for m in _CFR_RESOURCE_RE.finditer(page_html):
        if m.group(1).lower().startswith("french"):
            skip.update(re.findall(r'href="([^"]+\.pdf)"', m.group(2)))
    return skip


def fetch_guideline_texts(fetcher: PoliteFetcher, urls: list, stats: dict) -> list:
    """Fetch public guideline documents and return labelled text blocks.

    A CFR link lands on a dataset page listing the actual files — its
    same-host PDF links are followed too (they are the published rubric
    documents). Capped per program; failures log and continue (a missing
    guideline never drops the program)."""
    blocks: list = []
    fetched = 0
    queue = list(urls)
    while queue and fetched < MAX_GUIDELINE_FETCHES_PER_PROGRAM:
        url = queue.pop(0)
        fetched += 1
        try:
            resp = fetcher.get(url)
            if resp is None:
                continue
            data = resp.content
            if len(data) > MAX_DOCUMENT_BYTES:
                log.warning("Skipping oversized guideline (%d bytes): %s", len(data), url)
                continue
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if url.lower().endswith(".pdf") or "pdf" in content_type:
                blocks.append(f"--- Program guidelines ({url}) ---\n{pdf_to_text(data)}")
                stats["guideline_fetches"] += 1
            else:
                page_html = data.decode(resp.encoding or "utf-8", errors="replace")
                blocks.append(f"--- Program guidelines page ({url}) ---\n{html_to_text(page_html)}")
                stats["guideline_fetches"] += 1
                skip = _french_pdf_urls(page_html)
                host = urlparse(url).netloc
                for child, _text in extract_links(page_html, url):
                    if (urlparse(child).netloc == host
                            and urlparse(child).path.lower().endswith(".pdf")
                            and child not in skip
                            and child not in queue):
                        queue.append(child)
        except Exception:   # noqa: BLE001 - guidelines are additive, never fatal
            log.warning("Guideline fetch failed for %s", url, exc_info=True)
    return blocks


# ---------------------------------------------------------------------------
# Program assembly
# ---------------------------------------------------------------------------
def assemble_text(name: str, status: Optional[str], ministry: Optional[str],
                  section_html: str) -> str:
    lines = [f"Program: {name}"]
    if status:
        lines.append(f"Status: {status}")
    if ministry:
        lines.append(f"Ministry: {ministry}")
    for label, body_html in subsections(section_html):
        text = html_to_text(body_html)
        if not text:
            continue
        lines.append(f"{label}: {text}" if label else text)
    return "\n".join(lines)


def parse_deadline(section_html: str) -> Optional[str]:
    """Full date from the program's Deadline subsection(s), or None —
    'ongoing'/'continuous intake' deadlines have no date and get none."""
    for label, body_html in subsections(section_html):
        if not label.lower().startswith("deadline"):
            continue
        date = guess_meeting_date(html_to_text(body_html))
        if date:
            return date
    return None


def collect_page(listing_url: str, level: int, source_id: str,
                 fetcher: PoliteFetcher, keywords: Keywords,
                 limit: int, dry_run: bool, baseline: bool) -> dict:
    follow_guidelines = not baseline   # archive entries carry no guideline links
    stats = {"sections": 0, "programs": 0, "in_scope": 0, "inserted": 0,
             "skipped_duplicate": 0, "skipped_scope": 0, "gated": 0,
             "guideline_fetches": 0, "errors": 0}

    resp = fetcher.get(listing_url)
    if resp is None:
        raise RuntimeError(f"listing disallowed or unreachable: {listing_url}")
    html = resp.text

    for name, section_html in split_sections(html, level):
        stats["sections"] += 1
        status = parse_status(section_html)
        if not status:
            continue        # Overview / nav / letter-group headings, not a program
        stats["programs"] += 1
        if stats["inserted"] >= limit:
            log.info("Per-run cap (%d) reached; remaining programs left for future runs",
                     limit)
            break
        try:
            ministry = parse_ministry(section_html)
            body_text = assemble_text(name, status, ministry, section_html)
            if not matches_scope(f"{name}\n{ministry or ''}\n{body_text}"):
                stats["skipped_scope"] += 1
                continue
            stats["in_scope"] += 1

            deadline = parse_deadline(section_html)
            # Open page: identity = name + deadline + status, so deadline and
            # status changes re-insert (the signal) but description edits
            # don't. Closed archive: several year-cycles share one name
            # ("RIDE" ×3, "FireSmart" ×2), so a description snippet keeps
            # distinct entries distinct — still idempotent across re-runs.
            hash_parts = [listing_url, "grant_program", name,
                          deadline or "", (status or "").lower()]
            if baseline:
                hash_parts.append(body_text[:300])
            chash = content_hash(*hash_parts)
            if supabase_client.get_document_by_hash(chash):
                stats["skipped_duplicate"] += 1
                continue

            gated = False
            if follow_guidelines:
                links, gated = guideline_links(section_html, listing_url)
                if gated:
                    stats["gated"] += 1
                    body_text += ("\n\nProgram guidelines: GATED — published only "
                                  "behind a TPON login or by request; see the "
                                  "Contacts section.")
                for block in fetch_guideline_texts(fetcher, links, stats):
                    body_text += f"\n\n{block}"

            # Tag-only: the scope filter above is the drop decision;
            # keywords.txt just marks defence relevance.
            result = evaluate(name, body_text[:20000], "", keywords)
            payload = {
                "source_id": source_id,
                "url": program_url(listing_url, name),
                "title": name[:500],
                "doc_type": "grant_program",
                "status": "captured",
                "published_on": deadline,          # the DEADLINE is the event
                "date_precision": "day",
                "content_hash": chash,
                "content": body_text[:MAX_STORED_CHARS] or None,
                "defence_relevant": result.defence_relevant,
                "guidelines_gated": gated,
            }
            if dry_run:
                log.info("[dry-run] would insert: %r (%s | %s | deadline %s%s, %d chars)",
                         name, status, ministry or "ministry unknown", deadline,
                         " | GATED guidelines" if gated else "", len(body_text))
            else:
                supabase_client.insert_document(payload)
            stats["inserted"] += 1
        except Exception:   # noqa: BLE001 - one bad program must not kill the run
            log.exception("Error collecting program %r", name)
            stats["errors"] += 1

    return stats


def resolve_source_id(listing_url: str, sources: list, env_var: str) -> Optional[str]:
    """URL-keyed (ASCII, stable) — name-keyed matching has been silently
    defeated by em-dash variants twice before."""
    override = os.environ.get(env_var, "").strip()
    if override:
        return override
    target = listing_url.rstrip("/")
    for row in sources:
        if (row.get("url") or "").strip().rstrip("/") == target:
            return row["id"]
    return None


def run(limit: Optional[int] = None, dry_run: bool = False,
        baseline: bool = False) -> int:
    if baseline:
        listing_url, level, env_var = CLOSED_LISTING_URL, 3, "ONTARIO_GRANTS_CLOSED_SOURCE_ID"
        limit = BASELINE_LIMIT if limit is None else limit
    else:
        listing_url, level, env_var = OPEN_LISTING_URL, 2, "ONTARIO_GRANTS_SOURCE_ID"
        limit = MAX_DOCS_PER_RUN if limit is None else limit

    keywords = load_keywords()
    fetcher = PoliteFetcher()
    sources = supabase_client.fetch_rows("sources", "id,name,url")
    source_id = resolve_source_id(listing_url, sources, env_var)
    if not source_id:
        log.error("No sources row found with url=%s (run the grants sources "
                  "seed migration, or set %s)", listing_url, env_var)
        return 1

    try:
        stats = collect_page(listing_url, level, source_id, fetcher, keywords,
                             limit, dry_run, baseline=baseline)
    except Exception:
        # Single listing page per mode: if IT cannot be collected the run has
        # collected nothing — that is systemic, exit nonzero.
        log.exception("Ontario grants collection failed for %s", listing_url)
        return 1

    log.info("Ontario grants (%s): %s%s", "closed baseline" if baseline else "open",
             stats, " (DRY RUN)" if dry_run else "")
    if not dry_run and not stats["errors"]:
        supabase_client.update_source_last_collected(
            source_id, datetime.now(timezone.utc))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ontario grants collector")
    parser.add_argument("--limit", type=int, default=None,
                        help=f"max NEW documents per run (default {MAX_DOCS_PER_RUN}; "
                             f"{BASELINE_LIMIT} with --baseline)")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and parse but write nothing")
    parser.add_argument("--baseline", action="store_true",
                        help="one-time crawl of the closed-funding archive instead "
                             "of the open directory")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(limit=args.limit, dry_run=args.dry_run, baseline=args.baseline))
