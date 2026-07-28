"""Biddingo buyer-page collector (first buyer: Durham Regional Police Service).

Access method, decided on probe evidence (runs 30356741517 + 30356971071,
2026-07-28, both under the honest SignalNorthIntel/1.0 UA):

  * robots: biddingo.com is wildcard-allow; the old SignalNorthCollector name
    falsely matched a banned-tool group ("Collector" token, a different
    product), the renamed UA evaluates clean and the wildcard default applies.
    can_fetch(/m/drps): UA=True, wildcard=True.
  * the /m/<slug> page is an Angular shell that populates UNDER THE HONEST UA
    (no browser-UA requirement, unlike bids&tenders) and feeds itself from one
    public REST call: POST api.biddingo.com/restapi/bidding/list/noauthorize/
    <sysId>/<orgId> -- "noauthorize" is Biddingo's own name for the endpoint.
    The call is SERVER-PAGED ({"startResult": 0, "maxRow": 10} body; the
    response reports the portfolio size as bidCount), and replaying the
    page's own call with a larger maxRow through the page's request context
    returns the full portfolio (DRPS: all 38 bids, refs back to 2013) --
    run 30357811409.
  * each row has a dedicated tenderNumber field (the DRPS bid reference,
    printed verbatim: "DRPS-2026-002", "DRPS 2025-003", "2023-0002",
    "RFP-0100-2023" -- heterogeneous, so NO title parsing is ever attempted),
    tenderName, bidStatus (Open/Closed/Awarded), tenderClosingDate (+ "ET"),
    publishedDate, and tenderId for the public detail URL
    /<slug>/bid/<sysId>/<orgId>/<tenderId>/verification.

So the collector renders the page once with the house Playwright stack,
reads the CAPTURED list response, and when the first page undercounts
bidCount it replays the page's OWN call with only the two paging fields
changed (Method B, as in tenders_bidsandtenders) -- no DOM scraping, no
guessed request shapes, one page load plus at most a few paged data calls
per buyer per run.

Mapping to the spine (same rules as tenders_bidsandtenders): bidStatus
Awarded -> award_notice (grade 5); everything else (Open, Closed, Cancelled,
unknown) -> tender_notice. documents.reference_number carries tenderNumber
verbatim -- the hard key the proposer clusters on and the demand-arc walk
uses, so an awarded row reconciles against the tender it settles.
published_on stores the CLOSING date (bids&tenders semantics: the closing is
the event the brief acts on; for awarded rows it is the only honest
timestamp, an award date is not exposed and is never invented). Identity is
content_hash(ref, doc_type, status): a bid moving Open -> Awarded inserts a
fresh document (the lifecycle is the signal); an unchanged row dedupes.

LOUD-FAILURE GUARDS (silent-empty is the failure a hit-rate product cannot
afford): the list call not observed on render, zero rows, or a response
shorter than its own bidCount (server-side paging appearing) all raise.

Politeness: one rendered page per buyer, 2s settle, nothing else fetched.
Coverage multiplier: BUYERS is config -- any other Biddingo buyer page is a
row here (after its own robots + provenance gate), no new code.

    python -m src.tenders_biddingo --dry-run   # render + validate, write nothing
    python -m src.tenders_biddingo             # collect for real
"""
import argparse
import json
import logging
import re
import sys

from . import supabase_client
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

BASE = "https://www.biddingo.com"

# The honest collector UA (renamed 2026-07-28; see src/board_minutes.py).
# Probe-proven: the Biddingo grid populates under this UA.
USER_AGENT = "SignalNorthIntel/1.0"

# One row per Biddingo buyer page. `slug` is the /m/<slug> landing slug;
# `name` is documents.buyer_name (structural on a buyer page) and must match
# a resolve_orgs canonical name. Add a buyer = add a row, after its own
# robots + provenance gate (design doc note + operator go).
BUYERS = [
    # Provenance: drps.ca/about-us/procurement-services/ names Biddingo as
    # DRPS's posting channel (operator browse 2026-07-20); probe runs above.
    {"slug": "drps", "name": "Durham Regional Police Service"},
]

# The page's own data call, observed on render: POST
# api.biddingo.com/restapi/bidding/list/noauthorize/<sysId>/<orgId>.
LIST_CALL_RE = re.compile(
    r"https://api\.biddingo\.com/restapi/bidding/list/noauthorize/(\d+)/(\d+)")

# An unknown bidStatus maps to tender_notice (never dropped, never guessed
# into the awarded rung) and is surfaced in the VALIDATION line.
AWARDED_STATUSES = {"awarded"}

MAX_STORED_CHARS = 20000
DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def buyer_page_url(slug: str) -> str:
    return f"{BASE}/m/{slug}"


def bid_detail_url(slug: str, sys_id: str, org_id: str, tender_id) -> str:
    """The public per-bid page ('Access Bid Document(s)' target)."""
    return f"{BASE}/{slug}/bid/{sys_id}/{org_id}/{tender_id}/verification"


def parse_us_date(text: str):
    """'04/24/2026 02:00:00 PM' -> '2026-04-24' (Biddingo prints MM/DD/YYYY,
    timezone ET). Returns None when no date parses (None beats a wrong date)."""
    m = DATE_RE.search(text or "")
    if not m:
        return None
    mon, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mon <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{mon:02d}-{day:02d}"


def map_row(jr: dict, slug: str, sys_id: str, org_id: str) -> dict:
    """One bidInfoList row -> the neutral row shape build_payload reads.
    The reference is tenderNumber VERBATIM (whitespace-normalized only):
    the printed forms vary and are the publisher's own key; we never
    reformat or fabricate one."""
    ref = " ".join((jr.get("tenderNumber") or "").split()) or None
    status = (jr.get("bidStatus") or "").strip()
    return {
        "ref": ref,
        "title": " ".join((jr.get("tenderName") or "").split()),
        "status": status,
        "doc_type": ("award_notice" if status.lower() in AWARDED_STATUSES
                     else "tender_notice"),
        "closing": jr.get("tenderClosingDate") or "",
        "posted": jr.get("publishedDate") or "",
        "tender_id": jr.get("tenderId"),
        "url": (bid_detail_url(slug, sys_id, org_id, jr["tenderId"])
                if jr.get("tenderId") else buyer_page_url(slug)),
    }


def build_payload(buyer: dict, source_id, row: dict,
                  keywords: Keywords) -> dict:
    closing_iso = parse_us_date(row.get("closing"))
    posted_iso = parse_us_date(row.get("posted"))
    title = row.get("title") or "(untitled bid)"
    # The compact raw line is the stored body (this endpoint has no scope
    # text); both dates ride along so extraction sees them even though
    # published_on stores only the closing date.
    raw = " | ".join(x for x in (
        row.get("ref"), title, row.get("status"),
        f"posted {row['posted']}" if row.get("posted") else "",
        f"closes {row['closing']} ET" if row.get("closing") else "",
        buyer["name"]) if x)
    result = evaluate(title, raw[:MAX_STORED_CHARS], "", keywords)
    return {
        "source_id": source_id,
        "url": row["url"],
        "title": title[:500],
        "doc_type": row["doc_type"],
        "status": "captured",
        # Closing date, bids&tenders semantics (module docstring). Falls back
        # to the posted date rather than NULL when closing did not parse.
        "published_on": closing_iso or posted_iso,
        "date_precision": "day",
        "reference_number": row.get("ref"),
        "content_hash": content_hash(row.get("ref") or row["url"],
                                     row["doc_type"], row.get("status") or ""),
        "content": raw[:MAX_STORED_CHARS] or None,
        "defence_relevant": result.defence_relevant,
        "buyer_name": buyer["name"],
    }


# The list endpoint is server-paged: the app's own first POST asks for
# {"startResult": 0, "maxRow": 10} and the response reports the full
# portfolio size as bidCount (probe run 30357811409: maxRow=100 replayed
# through the page's request context returns all 38 DRPS rows, HTTP 200).
# The collector replays the captured call page by page -- same Method-B
# pattern as tenders_bidsandtenders -- never guessing a request shape, only
# mutating the two paging fields of the body the app itself sent.
PAGE_ROWS = 100          # rows per replayed page
PORTFOLIO_MAX = 3000     # safety cap on a buyer's paged portfolio


def read_bid_list(page, slug: str) -> tuple:
    """Render the buyer page, then page the captured noauthorize list call
    until the full bidCount is in hand. Returns (rows, bid_count, sys_id,
    org_id). Raises when the call is never observed, a page fails, or the
    paged total still undercounts bidCount."""
    captured: dict = {}

    def on_request(req):
        m = LIST_CALL_RE.match(req.url)
        if m and req.method == "POST" and "url" not in captured:
            captured["url"] = req.url
            captured["sys_id"], captured["org_id"] = m.group(1), m.group(2)
            captured["post_data"] = req.post_data or ""
            try:
                captured["headers"] = req.all_headers()
            except Exception:
                captured["headers"] = dict(req.headers)

    def on_response(resp):
        if LIST_CALL_RE.match(resp.url) and "body" not in captured:
            captured["status"] = resp.status
            try:
                captured["body"] = resp.text()
            except Exception as e:      # keep the URL evidence for the raise
                captured["body"] = ""
                captured["error"] = repr(e)

    page.on("request", on_request)
    page.on("response", on_response)
    page.goto(buyer_page_url(slug), wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)

    if "body" not in captured or "url" not in captured:
        raise RuntimeError(
            f"[{slug}] the bidding/list/noauthorize call was never observed "
            f"on render: endpoint or app changed. Refusing to record silence.")
    if captured["status"] != 200 or not captured["body"]:
        raise RuntimeError(
            f"[{slug}] list call HTTP {captured['status']} "
            f"({captured.get('error', 'empty body')}): gated or changed.")
    data = json.loads(captured["body"])
    rows = list(data.get("bidInfoList") or [])
    bid_count = data.get("bidCount")
    if not rows:
        raise RuntimeError(
            f"[{slug}] list returned 0 bids (bidCount={bid_count}); a live "
            f"buyer page has a portfolio. Refusing to record silence.")

    if isinstance(bid_count, int) and len(rows) < bid_count:
        try:
            base_body = json.loads(captured["post_data"] or "{}")
        except ValueError:
            raise RuntimeError(
                f"[{slug}] list request body is no longer JSON; cannot page "
                f"the portfolio honestly. Refusing to truncate.")
        headers = {k: v for k, v in captured["headers"].items()
                   if not k.startswith(":")}
        seen = {r.get("tenderId") for r in rows}
        start = 0
        while len(rows) < min(bid_count, PORTFOLIO_MAX):
            body = {**base_body, "startResult": start, "maxRow": PAGE_ROWS}
            resp = page.request.post(captured["url"], headers=headers,
                                     data=json.dumps(body), timeout=45000)
            if resp.status != 200:
                raise RuntimeError(
                    f"[{slug}] paged list replay HTTP {resp.status} at "
                    f"startResult={start}: gated or changed.")
            batch = resp.json().get("bidInfoList") or []
            fresh = [r for r in batch if r.get("tenderId") not in seen]
            if not fresh:
                break
            rows.extend(fresh)
            seen.update(r.get("tenderId") for r in fresh)
            start += PAGE_ROWS
            page.wait_for_timeout(2000)    # politeness between pages
        if len(rows) < bid_count:
            raise RuntimeError(
                f"[{slug}] paged the portfolio to {len(rows)} rows but "
                f"bidCount={bid_count}: replay shape changed. Refusing to "
                f"silently truncate.")
    return rows, bid_count, captured["sys_id"], captured["org_id"]


def collect(dry_run: bool = True) -> dict:
    from playwright.sync_api import sync_playwright  # lazy: heavy optional dep

    keywords = load_keywords()
    sources = supabase_client.fetch_rows("sources", "id,url")
    src_by_url = {(s.get("url") or "").rstrip("/"): s["id"] for s in sources}
    stats = {"read": 0, "inserted": 0, "skipped_duplicate": 0, "errors": 0,
             "per_buyer": {}}
    failed: list = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for buyer in BUYERS:
            url = buyer_page_url(buyer["slug"])
            source_id = src_by_url.get(url.rstrip("/"))
            if not source_id and not dry_run:
                raise RuntimeError(
                    f"no sources row for {url}; apply the Biddingo sources "
                    f"seed migration first")
            val = {"rows": 0, "ref_parsed": 0, "closing_parsed": 0,
                   "posted_parsed": 0, "tender": 0, "award": 0,
                   "statuses": {}}
            stats["per_buyer"][buyer["slug"]] = val
            page = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1400, "height": 900}).new_page()
            try:
                rows, bid_count, sys_id, org_id = read_bid_list(
                    page, buyer["slug"])
                log.info("[%s] list captured: %d rows (bidCount=%s)",
                         buyer["slug"], len(rows), bid_count)
                for jr in rows:
                    row = map_row(jr, buyer["slug"], sys_id, org_id)
                    if not row["ref"]:
                        # Unkeyable for the spine; count loudly, never insert.
                        log.warning("[%s] row without tenderNumber skipped: %s",
                                    buyer["slug"], row["title"][:60])
                        stats["errors"] += 1
                        continue
                    stats["read"] += 1
                    val["rows"] += 1
                    val["ref_parsed"] += 1
                    s = row["status"] or "(blank)"
                    val["statuses"][s] = val["statuses"].get(s, 0) + 1
                    val["tender" if row["doc_type"] == "tender_notice"
                        else "award"] += 1
                    payload = build_payload(buyer, source_id, row, keywords)
                    if parse_us_date(row.get("closing")):
                        val["closing_parsed"] += 1
                    if parse_us_date(row.get("posted")):
                        val["posted_parsed"] += 1
                    if supabase_client.get_document_by_hash(
                            payload["content_hash"]):
                        stats["skipped_duplicate"] += 1
                        continue
                    if dry_run:
                        log.info("[dry-run] %-13s ref=%-16s close=%s :: %s",
                                 row["doc_type"], row["ref"],
                                 payload["published_on"],
                                 (payload["title"] or "")[:60])
                    else:
                        supabase_client.insert_document(payload)
                    stats["inserted"] += 1
                n = val["rows"] or 1
                log.info(
                    "VALIDATION [biddingo:%s]: rows=%d ref_parsed=%d (%d%%) "
                    "closing_parsed=%d (%d%%) posted_parsed=%d (%d%%) "
                    "tender=%d award=%d statuses=%s",
                    buyer["slug"], val["rows"], val["ref_parsed"],
                    round(100 * val["ref_parsed"] / n), val["closing_parsed"],
                    round(100 * val["closing_parsed"] / n),
                    val["posted_parsed"], round(100 * val["posted_parsed"] / n),
                    val["tender"], val["award"], val["statuses"])
            except Exception:
                # One buyer failing must not cost the others, but the RUN
                # still fails loudly after the sweep.
                log.exception("[%s] buyer failed", buyer["slug"])
                failed.append(buyer["slug"])
            finally:
                page.close()
        browser.close()

    if failed:
        raise RuntimeError(f"biddingo buyers failed: {', '.join(failed)}")
    log.info("biddingo totals: read=%d inserted=%d duplicates=%d errors=%d",
             stats["read"], stats["inserted"], stats["skipped_duplicate"],
             stats["errors"])
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="render + validate + report; write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    collect(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
