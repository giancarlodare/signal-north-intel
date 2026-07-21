"""City of Ottawa tender + award collector on the MERX public buyer page.

Source: merx.com/cityofottawa, the city's public MERX presence (ottawa.ca
links it; verified by the operator in a human browser 2026-07-20 because
ottawa.ca's WAF 403s our UA, so the provenance chain is recorded in
docs/merx-windsor-design.md rather than machine-crawled). merx.com's
robots.txt explicitly welcomes well-behaved crawlers and disallows only
authenticated/transactional paths; can_fetch is True for this collector's UA
with zero blocklist collisions (CI probe, job 88502863474).

Two stages (docs/merx-windsor-design.md, approved 2026-07-20):

  1. ENUMERATE: page through the server-side tabs (open-bids -> tender_notice;
     awarded-bids and bidresults-bids -> award_notice) via pageNumber=N,
     collecting MERX ids from the solicitation links. The identity hash is
     computable from the MERX id alone, so already-collected ids are skipped
     WITHOUT fetching their abstracts: the steady state fetches only new items.
  2. ABSTRACT: for each new id, fetch the solicitation abstract (server-side)
     and parse the Ottawa Solicitation Number (e.g. 19224-68051-T01, the hard
     key Ottawa itself uses, stored in reference_number), Title, and Closing
     Date (published_on, day precision). The MERX id rides in the URL.

Politeness is the board-minutes pattern (shared PoliteFetcher: robots per
host, 2s delay, SignalNorthCollector UA). A per-tab NEW-item cap drains the
awarded backlog over successive days; a hard page bound caps the initial
history at ~1000 ids per tab.

LOUD-FAILURE GUARDS: any tab's page 1 with zero solicitation links raises
(all three tabs carried full pages in the probe); abstract failures count
toward an error budget and then raise. Silence is never recorded as truth.

    python -m src.tenders_merx --dry-run   # fetch + parse, write nothing
    python -m src.tenders_merx             # collect for real
"""
import argparse
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urldefrag, urljoin, urlparse

from . import supabase_client
from .board_minutes import PoliteFetcher, extract_links, html_to_text
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

BASE = "https://www.merx.com"
BUYER_SLUG = "cityofottawa"
SOURCE_URL = "https://www.merx.com/cityofottawa"   # the sources-row key
BUYER_NAME = "City of Ottawa"                      # resolve_orgs canonical name
MAX_STORED_CHARS = 20000

# Tab -> doc_type. bidresults-bids carries the posted bid tabulations for the
# same lifecycle stage as awarded-bids; both map to award_notice, and an id
# appearing in both tabs dedupes to one row (the hash keys on id + doc_type).
TABS = [
    ("open-bids", "tender_notice"),
    ("awarded-bids", "award_notice"),
    ("bidresults-bids", "award_notice"),
]

NEW_PER_TAB = 25        # per-run cap on NEW abstracts (board-minutes style)
PAGE_MAX_PER_TAB = 40   # 40 pages x 25 ids bounds the initial history ~1000
KNOWN_PAGE_STOP = 2     # stop paging a tab after this many all-known pages
ERROR_BUDGET = 25       # abstract failures tolerated before loud abort

# Abstract fields as the page's linearized text prints them (probe verified
# on 0000281771): "Solicitation Number 19224-68051-T01" and
# "Closing Date 2024/12/02 03:00:00 PM EST". The number token must carry a
# digit so a following label word can never read as the value.
SOLNUM_RE = re.compile(
    r"Solicitation\s+Number\s*:?\s*([A-Za-z0-9][A-Za-z0-9./_-]*\d[A-Za-z0-9./_-]*)")
# Fallback (CI diagnostic 2026-07-21, job 88522188983): IWSD-style abstracts
# omit the labeled field, but the page <title> always ends
# "... - 41826-91345-T05 | MERX", and the number keeps Ottawa's
# NNNNN-NNNNN-LNN shape. The "| MERX" anchor keeps body numbers out.
SOLNUM_TITLE_RE = re.compile(r"-\s*(\d{4,6}-\d{4,6}-[A-Z]\d{2})\s*\|\s*MERX")
# Amended solicitations interleave text between the label and the date
# ("Closing Date A - Previous Amendment 2026/06/11 ..."). A short non-digit
# gap is tolerated, but never across "Previous": a previous amendment's
# close is explicitly NOT the current close, and none beats a wrong date.
# STRUCTURAL CEILING (CI diagnostic 2026-07-21, job 88523493062, all 8
# amended pages): the CURRENT close of an amended solicitation appears
# NOWHERE in the server HTML (zero raw-only date tokens; every dated field
# is annotated "A - Previous Amendment", current values client-rendered).
# Those rows carry published_on NULL honestly; ~10% of sampled abstracts.
CLOSING_RE = re.compile(
    r"Closing\s+Date\b(?:(?!Previous)[^0-9]){0,40}(\d{4})/(\d{1,2})/(\d{1,2})")
STATUS_RE = re.compile(r"This solicitation is\s+([A-Z]+)")


def listing_url(tab: str, page: int) -> str:
    return f"{BASE}/{BUYER_SLUG}/solicitations/{tab}?pageNumber={page}&selectedContent=BUYER"


def merx_hash(merx_id: str, doc_type: str) -> str:
    """Identity from the MERX id alone, so stage 1 can skip known ids without
    fetching abstracts. doc_type keeps the open -> awarded lifecycle as fresh
    inserts; the 'merx' namespace keeps ids away from other collectors'."""
    return content_hash(f"merx:{merx_id}", doc_type)


def solicitation_links(html: str, base_url: str) -> list[tuple[str, str, str]]:
    """Unique (merx_id, absolute_url, link_text) triples in page order. A
    solicitation link's path ends in the numeric MERX id (probe: both
    /cityofottawa/solicitations/<tab>/<slug>/0000327960 and the
    /cityofottawa/buyer-6700/solicitations/<slug>/0000316390 shape)."""
    seen: set[str] = set()
    out: list[tuple[str, str, str]] = []
    for url, text in extract_links(html, base_url):
        url, _ = urldefrag(url)
        parsed = urlparse(url)
        segs = [s for s in parsed.path.split("/") if s]
        if "solicitations" not in segs or not segs:
            continue
        last = segs[-1]
        if not (last.isdigit() and 8 <= len(last) <= 12):
            continue
        if last in seen:
            continue
        seen.add(last)
        out.append((last, url, " ".join((text or "").split())))
    return out


def has_next_page(html: str, base_url: str, tab: str, page: int) -> bool:
    """True when the page links pageNumber=page+1 for the same tab (the
    listing's own Next link; text is unreliable, the query is not)."""
    for url, _text in extract_links(html, base_url):
        parsed = urlparse(url)
        if f"/solicitations/{tab}" not in parsed.path:
            continue
        q = dict(parse_qsl(parsed.query))
        if q.get("pageNumber") == str(page + 1):
            return True
    return False


def parse_abstract(text: str) -> dict:
    """{sol_num, closing_on, status} from the abstract page's linearized
    text. Missing fields stay None: never fabricate a reference or a date."""
    sm = SOLNUM_RE.search(text) or SOLNUM_TITLE_RE.search(text)
    cm = CLOSING_RE.search(text)
    closing = None
    if cm:
        y, mo, d = int(cm.group(1)), int(cm.group(2)), int(cm.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            closing = f"{y:04d}-{mo:02d}-{d:02d}"
    st = STATUS_RE.search(text)
    return {"sol_num": sm.group(1) if sm else None,
            "closing_on": closing,
            "status": st.group(1) if st else None}


def build_payload(merx_id: str, url: str, title: str, doc_type: str,
                  abstract: dict, body: str, source_id: Optional[str],
                  keywords: Keywords) -> dict:
    result = evaluate(title, body[:MAX_STORED_CHARS], "", keywords)
    return {
        "source_id": source_id,
        "url": url,
        "title": (title or "(untitled solicitation)")[:500],
        "doc_type": doc_type,
        "status": "captured",
        "published_on": abstract["closing_on"],
        "date_precision": "day" if abstract["closing_on"] else None,
        "reference_number": abstract["sol_num"],   # Ottawa's own hard key
        "content_hash": merx_hash(merx_id, doc_type),
        "content": body[:MAX_STORED_CHARS] or None,
        "defence_relevant": result.defence_relevant,
        "buyer_name": BUYER_NAME,
    }


def collect(dry_run: bool = True) -> dict:
    keywords = load_keywords()
    fetcher = PoliteFetcher()
    sources = supabase_client.fetch_rows("sources", "id,url")
    source_id = next((s["id"] for s in sources
                      if (s.get("url") or "").rstrip("/") == SOURCE_URL.rstrip("/")), None)
    if not source_id and not dry_run:
        raise RuntimeError(
            f"no sources row for {SOURCE_URL}; apply the MERX/Windsor sources seed first")

    stats = {"inserted": 0, "skipped_duplicate": 0, "errors": 0, "per_tab": {}}
    val = {"abstracts": 0, "solnum": 0, "closing": 0}
    run_hashes: set[str] = set()   # in-run dedupe (awarded/bidresults overlap)

    for tab, doc_type in TABS:
        tval = {"ids_seen": 0, "new": 0, "pages": 0}
        stats["per_tab"][tab] = tval
        queue: list[tuple[str, str, str]] = []   # (merx_id, url, title)
        known_pages = 0
        page = 1
        while page <= PAGE_MAX_PER_TAB:
            resp = fetcher.get(listing_url(tab, page))
            if resp is None:
                raise RuntimeError(
                    f"[merx {tab}] robots.txt would not allow the listing; "
                    f"refusing to record silence")
            tval["pages"] += 1
            links = solicitation_links(resp.text, listing_url(tab, page))
            # LOUD-FAILURE GUARD: every tab carried a full page in the probe,
            # so an empty first page means gating or markup change, not truth.
            if page == 1 and not links:
                raise RuntimeError(
                    f"[merx {tab}] page 1 returned 0 solicitation links: "
                    f"gated or markup changed. Refusing to record silence.")
            page_new = 0
            for merx_id, url, text in links:
                tval["ids_seen"] += 1
                chash = merx_hash(merx_id, doc_type)
                if chash in run_hashes or supabase_client.get_document_by_hash(chash):
                    continue
                page_new += 1
                if len(queue) < NEW_PER_TAB:
                    run_hashes.add(chash)
                    queue.append((merx_id, url, text))
            known_pages = known_pages + 1 if page_new == 0 else 0
            # The tabs list newest activity first, so consecutive all-known
            # pages mean the rest of the history is already collected; the
            # steady state reads one page per tab.
            if (known_pages >= KNOWN_PAGE_STOP or len(queue) >= NEW_PER_TAB
                    or not has_next_page(resp.text, listing_url(tab, page), tab, page)):
                break
            page += 1

        tval["new"] = len(queue)
        log.info("[merx %s] %d ids across %d page(s), %d new queued",
                 tab, tval["ids_seen"], tval["pages"], len(queue))

        for merx_id, url, title in queue:
            try:
                resp = fetcher.get(url)
                if resp is None:
                    stats["errors"] += 1
                    continue
                body = html_to_text(resp.text)
                abstract = parse_abstract(body)
                val["abstracts"] += 1
                val["solnum"] += 1 if abstract["sol_num"] else 0
                val["closing"] += 1 if abstract["closing_on"] else 0
                payload = build_payload(merx_id, url, title, doc_type,
                                        abstract, body, source_id, keywords)
                if dry_run:
                    log.info("[dry-run] %-13s merx=%s ref=%-16s close=%s :: %s",
                             doc_type, merx_id, abstract["sol_num"],
                             abstract["closing_on"], payload["title"][:60])
                else:
                    supabase_client.insert_document(payload)
                stats["inserted"] += 1
            except Exception:
                stats["errors"] += 1
                log.exception("[merx %s] abstract failed (id=%s); continuing",
                              tab, merx_id)
                if stats["errors"] > ERROR_BUDGET:
                    raise RuntimeError(
                        f"[merx] exceeded the error budget ({stats['errors']} "
                        f"failures): systemic, not transient. Aborting.")

    # The enablement bar reads this line (docs/merx-windsor-design.md section
    # 5: >= 90% of sampled abstracts parse Solicitation Number AND Closing
    # Date; open and awarded tabs nonzero).
    a = val["abstracts"] or 1
    log.info("VALIDATION [merx-ottawa]: open_tab=%d awarded_tab=%d "
             "bidresults_tab=%d abstracts=%d solnum_parsed=%d (%d%%) "
             "closing_parsed=%d (%d%%)",
             stats["per_tab"]["open-bids"]["ids_seen"],
             stats["per_tab"]["awarded-bids"]["ids_seen"],
             stats["per_tab"]["bidresults-bids"]["ids_seen"],
             val["abstracts"], val["solnum"], round(100 * val["solnum"] / a),
             val["closing"], round(100 * val["closing"] / a))
    log.info("merx-ottawa: %s%s", stats, " (DRY RUN)" if dry_run else "")
    if not dry_run and source_id:
        supabase_client.update_source_last_collected(
            source_id, datetime.now(timezone.utc))
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="City of Ottawa MERX tender/award collector")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and parse but write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    collect(dry_run=args.dry_run)
    sys.exit(0)
