"""Public Safety Canada funding-programs collector.

The department's funding-programs index (CI-probe-verified 2026-07-11) is a
single HTML table of ~30 contribution/grant programs — columns Program (with
a link to each program's terms-and-conditions page), Description, Type. Each
program becomes one grant_program document whose body is the detail page's
<main> content (the program's full terms, objectives, eligible recipients —
exactly what the extractor needs to spot procurement-leading money).

Design decisions:
  - No scope filter: every program here is public-safety by construction
    (it's PS Canada's own program list). keywords.txt runs tag-only, marking
    defence_relevant — same rule as the board-minutes collector.
  - published_on is NULL: these are standing program pages, not dated events.
    Their terms cite statute years and past budgets — parsing dates out of
    that text would fabricate event dates, and None beats a wrong date. When
    a program announces a call-for-proposals with a real deadline, that
    arrives through the PS Canada newsroom feed instead.
  - Identity = detail-page URL (the publisher's own page, one per program):
    re-runs are no-ops until the department adds a program. Weekly cadence.
  - Detail-page fetch failure = skip WITHOUT inserting (log-and-continue),
    so the next weekly run retries with a body instead of leaving a
    permanently body-less record behind the dedupe hash.

    python -m src.grants_pscanada --dry-run
"""
import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote, urljoin, urlparse

from . import supabase_client
from .board_minutes import (MAX_STORED_CHARS, PoliteFetcher, html_to_text)
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

INDEX_URL = "https://www.publicsafety.gc.ca/cnt/rsrcs/fndng-prgrms/index-en.aspx"
MAX_DOCS_PER_RUN = 40    # the table is ~30 rows; the first run captures all

_MAIN_RE = re.compile(r"<main[^>]*>(.*?)</main>", re.S | re.I)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
# The Program column is a <th scope="row"> (WET accessible-table markup), so
# cells are matched as th-or-td in document order; the header row is detected
# by having no <td> at all.
_CELL_RE = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.S | re.I)
_TD_RE = re.compile(r"<td[^>]*>", re.I)
_LINK_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)


def main_content(html: str) -> str:
    """The page's <main> region (canada.ca WET template), else the whole page."""
    m = _MAIN_RE.search(html)
    return m.group(1) if m else html


def parse_programs(index_html: str, base_url: str) -> list:
    """[{name, url, description, type}] from the index table. Rows are
    (Program-with-link, Description, Type); the header row has no <td>."""
    programs = []
    for row_html in _ROW_RE.findall(main_content(index_html)):
        if not _TD_RE.search(row_html):
            continue        # header row (all <th>)
        cells = _CELL_RE.findall(row_html)
        if len(cells) < 2:
            continue
        link = _LINK_RE.search(cells[0])
        if link:
            url = urljoin(base_url, link.group(1))
            name = html_to_text(link.group(2))
        else:
            name = html_to_text(cells[0])
            # No detail page: the index row itself is the public source.
            url = f"{base_url}#:~:text={quote(name, safe='')}"
        if not name:
            continue
        programs.append({
            "name": name,
            "url": url,
            "description": html_to_text(cells[1]),
            "type": html_to_text(cells[2]) if len(cells) > 2 else "",
            "has_detail": bool(link),
        })
    return programs


def resolve_source_id(sources: list) -> Optional[str]:
    """URL-keyed (ASCII, stable) — name matching has been silently defeated
    by em-dash variants twice before."""
    override = os.environ.get("PSC_GRANTS_SOURCE_ID", "").strip()
    if override:
        return override
    target = INDEX_URL.rstrip("/")
    for row in sources:
        if (row.get("url") or "").strip().rstrip("/") == target:
            return row["id"]
    return None


def collect(source_id: str, fetcher: PoliteFetcher, keywords: Keywords,
            limit: int, dry_run: bool) -> dict:
    stats = {"programs": 0, "inserted": 0, "skipped_duplicate": 0,
             "bodies_fetched": 0, "errors": 0}

    resp = fetcher.get(INDEX_URL)
    if resp is None:
        raise RuntimeError(f"index disallowed or unreachable: {INDEX_URL}")
    programs = parse_programs(resp.text, INDEX_URL)
    log.info("Index lists %d programs", len(programs))

    for prog in programs:
        stats["programs"] += 1
        if stats["inserted"] >= limit:
            log.info("Per-run cap (%d) reached", limit)
            break
        chash = content_hash(prog["url"], "grant_program")
        if supabase_client.get_document_by_hash(chash):
            stats["skipped_duplicate"] += 1
            continue
        try:
            body = (f"Program: {prog['name']}\n"
                    f"Type: {prog['type']}\n"
                    f"Description: {prog['description']}")
            if prog["has_detail"]:
                detail = fetcher.get(prog["url"])
                if detail is None:
                    # robots said no — don't insert a body-less record
                    stats["errors"] += 1
                    continue
                body += "\n\n" + html_to_text(main_content(detail.text))
                stats["bodies_fetched"] += 1

            # Tag-only: PS Canada's own program list is in-scope by
            # construction; keywords.txt just marks defence relevance.
            result = evaluate(prog["name"], body[:20000], "", keywords)
            payload = {
                "source_id": source_id,
                "url": prog["url"],
                "title": prog["name"][:500],
                "doc_type": "grant_program",
                "status": "captured",
                "published_on": None,   # standing program page, not a dated event
                "content_hash": chash,
                "content": body[:MAX_STORED_CHARS] or None,
                "defence_relevant": result.defence_relevant,
            }
            if dry_run:
                log.info("[dry-run] would insert: %r (%s, %d chars body)",
                         prog["name"][:80], prog["url"], len(body))
            else:
                supabase_client.insert_document(payload)
            stats["inserted"] += 1
        except Exception:   # noqa: BLE001 - one bad program must not kill the run
            log.exception("Error collecting %s", prog["url"])
            stats["errors"] += 1

    return stats


def run(limit: int = MAX_DOCS_PER_RUN, dry_run: bool = False) -> int:
    keywords = load_keywords()
    fetcher = PoliteFetcher()
    sources = supabase_client.fetch_rows("sources", "id,name,url")
    source_id = resolve_source_id(sources)
    if not source_id:
        log.error("No sources row found with url=%s (run the grants sources "
                  "seed migration, or set PSC_GRANTS_SOURCE_ID)", INDEX_URL)
        return 1

    try:
        stats = collect(source_id, fetcher, keywords, limit, dry_run)
    except Exception:
        # One index page: if IT cannot be collected, nothing was — systemic.
        log.exception("PS Canada funding-programs collection failed")
        return 1

    log.info("PS Canada funding programs: %s%s", stats, " (DRY RUN)" if dry_run else "")
    if not dry_run and not stats["errors"]:
        supabase_client.update_source_last_collected(
            source_id, datetime.now(timezone.utc))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PS Canada funding-programs collector")
    parser.add_argument("--limit", type=int, default=MAX_DOCS_PER_RUN,
                        help=f"max NEW documents per run (default {MAX_DOCS_PER_RUN})")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and parse but write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(limit=args.limit, dry_run=args.dry_run))
