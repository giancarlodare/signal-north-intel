"""City of Windsor open-data tender + award collector.

Source: opendata.citywindsor.ca/Tools/BidsAndTenders, the city's own
open-data mirror of its bid activity (docs/merx-windsor-design.md, approved
2026-07-20). One server-side HTML page, no pagination, no JS: the probe saw
121 items spanning a year-plus, each carrying a reference (NN-YY), Open/Close
datetimes, a tender-letter PDF at /Tools/DownloadTender/{GUID}, a free-text
description, and (for 59 items) a "View Unofficial Results" PDF, which is the
award record. Provenance is publisher-published by definition: this is the
city's own catalogue. robots.txt 404s (allow-all per RFC 9309); the
PoliteFetcher still checks it every run in case one appears.

Spine mapping (no schema change): each item emits a `tender_notice`
(in_market) whose published_on is the CLOSE date at day precision. The close
date is the current truth: 40 of the probe's items carried "(Extended)", and
an extended close REFRESHES IN PLACE on the existing row, CanadaBuys-amendment
style, because the identity hash deliberately excludes the date. Items with an
Unofficial Results link additionally emit an `award_notice` on the same
reference; the results PDF publishes no award date, so published_on stays the
close date (same convention as the bids&tenders awarded rung; never
fabricate). reference_number carries the NN-YY hard key the procurement
proposer clusters on.

LOUD-FAILURE GUARD: zero parsed items raises. The page always carries a
year-plus of activity, so an empty parse means the endpoint or markup
changed, and silence must never be recorded as truth.

    python -m src.tenders_windsor --dry-run   # fetch + parse, write nothing
    python -m src.tenders_windsor             # collect for real
"""
import argparse
import logging
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin

from . import supabase_client
from .board_minutes import PoliteFetcher
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

LISTING_URL = "https://opendata.citywindsor.ca/Tools/BidsAndTenders"
SOURCE_URL = LISTING_URL          # the sources-row key (URL-guarded migration)
BUYER_NAME = "City of Windsor"    # must match a resolve_orgs ORG_SEED canonical
MAX_STORED_CHARS = 20000
ERROR_BUDGET = 25                 # per-item failures tolerated before loud abort

# Item header as the page prints it: "RFP 86-26, Retaining Wall ..." (probe
# 2026-07-20: prefixes RFT/RFP/EOI/RFPQ live, RFQ reserved; refs \d{1,3}-\d{2}).
# RFPQ before RFP so alternation matches the longer prefix first.
ITEM_HEAD = re.compile(r"\b(RFPQ|RFP|RFT|RFQ|EOI)\s+(\d{1,3}-\d{2})\s*,?\s")
# A real header is followed by its own "Open:" marker within this window
# (title lengths run well under it). A reference mentioned mid-description
# is not, so it never starts a phantom item (see parse_items).
HEAD_WINDOW = 500

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
# "Open: Jul 08, 2026 12:00 AM EST" / "Close: Aug 05, 2026 11:30 AM EST".
OPEN_RE = re.compile(r"Open:\s*([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})")
CLOSE_RE = re.compile(r"Close:\s*([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})")


def _date_iso(mon_abbr: str, day: str, year: str) -> Optional[str]:
    mon = MONTHS.get(mon_abbr)
    if not mon:
        return None
    return f"{int(year):04d}-{mon:02d}-{int(day):02d}"


class _Stream(HTMLParser):
    """Linearizes the page into document-order text plus links positioned by
    their offset in that text, so per-item links (tender letter, unofficial
    results) can be assigned to the item segment they appear inside without
    depending on the page's exact block markup."""

    _SKIP = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self._parts: list[str] = []
        self._len = 0
        self._a: Optional[list] = None          # [href, offset, text_parts]
        self.links: list[tuple[int, str, str]] = []   # (offset, href, text)

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif tag == "a" and not self._skip:
            href = dict(attrs).get("href")
            if href:
                self._a = [href, self._len, []]

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        elif tag == "a" and self._a is not None:
            href, off, parts = self._a
            self.links.append((off, href, " ".join(" ".join(parts).split())))
            self._a = None

    def handle_data(self, data):
        if self._skip:
            return
        chunk = " ".join(data.split())
        if not chunk:
            return
        self._parts.append(chunk)
        self._len += len(chunk) + 1     # +1 for the join separator
        if self._a is not None:
            self._a[2].append(data)

    def text(self) -> str:
        return " ".join(self._parts)


def parse_items(html: str, base_url: str = LISTING_URL) -> tuple[list[dict], int]:
    """(items, open_marker_count). Each item: {prefix, ref, title, open_on,
    close_on, letter_url, results_url, text}. open_marker_count is the page's
    own count of "Open: <date>" markers, the independent expected-item tally
    the validation line compares against."""
    stream = _Stream()
    stream.feed(html)
    text = stream.text()
    open_markers = len(OPEN_RE.findall(text))

    matches = list(ITEM_HEAD.finditer(text))
    heads = []
    for i, m in enumerate(matches):
        # Only accept a header whose own "Open:" follows before the next
        # header candidate; a self-reference inside a description fails this
        # and stays part of its item instead of splitting a phantom one.
        window_end = m.start() + HEAD_WINDOW
        if i + 1 < len(matches):
            window_end = min(window_end, matches[i + 1].start())
        if text.find("Open:", m.end(), window_end) != -1:
            heads.append(m)

    items = []
    for i, m in enumerate(heads):
        seg_start = m.start()
        seg_end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        seg = text[seg_start:seg_end]

        pos_open = seg.find("Open:")
        title = seg[m.end() - seg_start:pos_open].strip(" ,;") if pos_open > 0 else ""
        om = OPEN_RE.search(seg)
        cm = CLOSE_RE.search(seg)

        letter_url = results_url = None
        for off, href, link_text in stream.links:
            if not (seg_start <= off < seg_end):
                continue
            absolute = urljoin(base_url, href)
            if letter_url is None and "/tools/downloadtender/" in absolute.lower():
                letter_url = absolute
            if results_url is None and (
                    "unofficial results" in link_text.lower()
                    or "unofficialresult" in href.lower()):
                results_url = absolute

        items.append({
            "prefix": m.group(1),
            "ref": m.group(2),
            "title": title,
            "open_on": _date_iso(*om.groups()) if om else None,
            "close_on": _date_iso(*cm.groups()) if cm else None,
            "letter_url": letter_url,
            "results_url": results_url,
            "text": seg[:MAX_STORED_CHARS],
        })
    return items, open_markers


def build_payload(item: dict, source_id: Optional[str], doc_type: str,
                  keywords: Keywords) -> dict:
    """One parsed item -> a documents payload. The identity hash is
    (reference, doc_type, 'windsor'): no date and no status, so an extended
    close date finds the SAME row and refreshes it in place, while the
    open -> awarded lifecycle (doc_type changes) inserts fresh. 'windsor'
    namespaces the short NN-YY references away from other collectors'."""
    title = f"{item['prefix']} {item['ref']}, {item['title']}" if item["title"] \
        else f"{item['prefix']} {item['ref']}"
    if doc_type == "award_notice":
        url = item["results_url"]
    else:
        url = item["letter_url"] or LISTING_URL
    body = item["text"] or title
    result = evaluate(title, body, "", keywords)
    return {
        "source_id": source_id,
        "url": url,
        "title": title[:500],
        "doc_type": doc_type,
        "status": "captured",
        # The close date is the event the spine cares about (the results PDF
        # publishes no award date, and none beats a wrong date).
        "published_on": item["close_on"],
        "date_precision": "day" if item["close_on"] else None,
        "reference_number": item["ref"],
        "content_hash": content_hash(item["ref"], doc_type, "windsor"),
        "content": body or None,
        "defence_relevant": result.defence_relevant,
        "buyer_name": BUYER_NAME,
    }


def _existing_doc(chash: str) -> Optional[dict]:
    """Existing row as {id, published_on} or None. Fetched with the date so
    the close-date refresh can compare before writing."""
    rows = supabase_client.fetch_rows_where(
        "documents", "id,published_on", {"content_hash": f"eq.{chash}"}, limit=1)
    return rows[0] if rows else None


def collect(dry_run: bool = True) -> dict:
    keywords = load_keywords()
    fetcher = PoliteFetcher()
    sources = supabase_client.fetch_rows("sources", "id,url")
    source_id = next((s["id"] for s in sources
                      if (s.get("url") or "").rstrip("/") == SOURCE_URL.rstrip("/")), None)
    if not source_id and not dry_run:
        raise RuntimeError(
            f"no sources row for {SOURCE_URL}; apply the MERX/Windsor sources seed first")

    resp = fetcher.get(LISTING_URL)
    if resp is None:
        raise RuntimeError(
            f"robots.txt would not allow {LISTING_URL}; refusing to record silence")
    items, open_markers = parse_items(resp.text)
    if not items:
        raise RuntimeError(
            "Windsor open-data page parsed to 0 items: endpoint or markup "
            "changed. Refusing to record silence.")
    if open_markers > len(items):
        log.warning("parsed %d items but the page carries %d 'Open:' markers; "
                    "segmentation may be missing items", len(items), open_markers)

    stats = {"items": len(items), "open_markers": open_markers, "inserted": 0,
             "refreshed": 0, "skipped_duplicate": 0, "awards": 0, "errors": 0}
    val_close = sum(1 for it in items if it["close_on"])

    for item in items:
        try:
            tender = build_payload(item, source_id, "tender_notice", keywords)
            existing = _existing_doc(tender["content_hash"])
            if existing:
                # Close-date refresh in place: an "(Extended)" close is the
                # current truth. Never overwrite a known date with None.
                if item["close_on"] and existing.get("published_on") != item["close_on"]:
                    if dry_run:
                        log.info("[dry-run] would refresh close date %s -> %s for %s",
                                 existing.get("published_on"), item["close_on"], item["ref"])
                    else:
                        supabase_client.update_row("documents", existing["id"], {
                            "published_on": item["close_on"], "date_precision": "day"})
                    stats["refreshed"] += 1
                else:
                    stats["skipped_duplicate"] += 1
            else:
                if dry_run:
                    log.info("[dry-run] %-13s ref=%-7s close=%s :: %s",
                             "tender_notice", item["ref"], tender["published_on"],
                             tender["title"][:70])
                else:
                    supabase_client.insert_document(tender)
                stats["inserted"] += 1

            if item["results_url"]:
                stats["awards"] += 1
                award = build_payload(item, source_id, "award_notice", keywords)
                if supabase_client.get_document_by_hash(award["content_hash"]):
                    stats["skipped_duplicate"] += 1
                elif dry_run:
                    log.info("[dry-run] %-13s ref=%-7s close=%s :: unofficial results",
                             "award_notice", item["ref"], award["published_on"])
                    stats["inserted"] += 1
                else:
                    supabase_client.insert_document(award)
                    stats["inserted"] += 1
        except Exception:
            stats["errors"] += 1
            log.exception("[windsor] item failed (ref=%s); continuing", item.get("ref"))
            if stats["errors"] > ERROR_BUDGET:
                raise RuntimeError(
                    f"[windsor] exceeded the error budget ({stats['errors']} item "
                    f"failures): systemic, not transient. Aborting.")

    # The enablement bar reads this line (docs/merx-windsor-design.md section
    # 5: >= 90% ref+close parse, >= 40 items, unofficial results nonzero).
    # Every parsed item carries a reference by construction of ITEM_HEAD, so
    # ref coverage is items/open_markers.
    n = len(items) or 1
    log.info("VALIDATION [windsor]: items=%d open_markers=%d ref_parsed=%d (%d%%) "
             "close_parsed=%d (%d%%) unofficial_results=%d",
             len(items), open_markers, len(items), 100,
             val_close, round(100 * val_close / n), stats["awards"])
    log.info("windsor: %s%s", stats, " (DRY RUN)" if dry_run else "")
    if not dry_run and source_id:
        supabase_client.update_source_last_collected(
            source_id, datetime.now(timezone.utc))
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="City of Windsor open-data tender/award collector")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and parse but write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    collect(dry_run=args.dry_run)
    sys.exit(0)
