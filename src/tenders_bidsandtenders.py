"""Municipal tender + award collector for the bids&tenders platform.

Access method A (headless render-and-read), decided on evidence in
docs/peel-tenders-design.md. bids&tenders serves a CSRF-guarded, JS-rendered
fuelux grid with no inline data and a soft-404 robots. Five probes and a
feasibility spike established:

  * a REAL browser User-Agent is REQUIRED: the HeadlessChrome UA is served a
    dead (empty) grid. This is the silent-empty failure mode, so it is guarded
    against loudly (see LOUD-FAILURE GUARD below);
  * with a real UA the OPEN grid auto-loads on page render (67 live Peel rows in
    the spike, counted before any interaction). The awarded rung comes from the
    same guarded data call, POST /Module/Tenders/en/Tender/Search/<moduleGUID>
    ?status=Awarded (Method B): a spike proved it returns HTTP 200 JSON of
    genuinely awarded bids (disjoint from Open), so we capture that call on load
    and replay it. The JS tab-click does NOT switch the grid to Awarded (it
    returns the Open rows relabelled), so the grid is used for Open only.

LOUD-FAILURE GUARDS: a municipality's OPEN grid returning zero rows, OR the
awarded replay returning zero rows, is treated as an error (raise), never a
silent no-op. A live bids&tenders portal essentially always has open bids and
years of awarded history, so zero means we were gated or the endpoint changed.
Silent-empty is the failure we most need to avoid for a hit-rate product.

Mapping to the existing spine (no schema change): an open bid is a
`tender_notice` (in_market, grade 4) whose CLOSING date is a future event
(Path B imminent in the brief); an awarded bid is an `award_notice` (awarded,
grade 5). Both write the bid reference number (e.g. 2026-104P) to
`documents.reference_number`, the hard key the procurement proposer clusters on
and the link the demand-arc backtest walks, so an awarded doc reconciles against
the tender it settles. The awarded JSON exposes reference, title, status and
closing date but NOT the winning vendor or value (a deferred per-bid enrichment);
the reference is all the awarded rung needs to reconcile.

Coverage multiplier: parameterized by {org_key, subdomain}. Peel is the first
row; every other *.bidsandtenders.ca municipality is a config row, no new code.

    python -m src.tenders_bidsandtenders --dry-run   # render + report, write nothing
    python -m src.tenders_bidsandtenders             # collect for real
"""
import argparse
import logging
import re
import sys
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from . import config, supabase_client
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

# {org_key, subdomain, name}. Add a row per municipality; no code change.
# Tier 1 (docs/big12-tier1-design.md, approved 2026-07-20): every enabled row
# passed the publisher-linked provenance check, official page recorded in the
# design doc. `name` doubles as documents.buyer_name (the buyer is structural
# on these portals) and must match a resolve_orgs ORG_SEED canonical name.
MUNICIPALITIES = [
    {"org_key": "peel", "subdomain": "peelregion", "name": "Region of Peel"},
    {"org_key": "york", "subdomain": "york", "name": "York Region"},
    {"org_key": "london", "subdomain": "london", "name": "City of London"},
    {"org_key": "durham", "subdomain": "durham", "name": "Region of Durham"},
    {"org_key": "yrp", "subdomain": "yrp", "name": "York Regional Police"},
    # PERMANENTLY PARKED on provenance, with evidence (operator browse,
    # 2026-07-20): drps.ca/about-us/procurement-services/ states DRPS posts
    # tenders, RFPs, and competitive opportunities on the Biddingo portal,
    # and that link resolves to biddingo.com/login (a login wall). The
    # publisher-named channel is Biddingo; the branded bids&tenders tenant
    # is legacy/secondary and must not be enabled. Any Biddingo access is a
    # separate operator policy decision (terms-of-service compliance and
    # whether a registered-account collector fits the provenance and
    # politeness rules), not a config flip here.
    # {"org_key": "drps", "subdomain": "drps", "name": "Durham Regional Police Service"},
]

# A real desktop Chrome UA. The headless UA is gated to an empty grid, so this
# is not cosmetic: it is load-bearing (see module docstring).
REAL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# The Open (in_market) rung is read from the rendered grid (Method A). The JS
# tab-click does NOT switch the grid to Awarded (a live run proved it returned
# the Open rows relabelled), so Awarded is NOT taken from the grid.
TAB_DOC_TYPE = [("Open", "tender_notice")]

# The Awarded (awarded) rung uses Method B: replay the page's own guarded data
# call with ?status=Awarded. A validation spike proved this returns HTTP 200 JSON
# of genuinely awarded bids (a set disjoint from Open), each Title carrying the
# same reference format (e.g. '2017-695N - ...') that hard-keys to the tender.
# The endpoint exposes the reference, title, status and closing date, but NOT the
# winning vendor or award value (those live on a per-bid results page and are a
# deferred enrichment); the reference number is all the awarded rung needs to
# reconcile. Paged, bounded, deduped on the reference.
SEARCH_RE = re.compile(r"/Tender/Search/[0-9a-fA-F-]{36}")
AWARDED_PAGE = 100          # rows per replayed page
AWARDED_MAX = 3000          # safety cap on the paged awarded history
AWARDED_ERROR_BUDGET = 25   # per-row failures tolerated before the run fails loudly

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

# Two reference shapes are live across the tier-1 tenants (markup probe,
# 2026-07-20): Peel's digits-first form (2026-104P) and the letter-prefixed
# form the others use (York RFPQ-3823-26 / T-10-108, Durham T-1083-2026 /
# RFP-303-2017-C, London RFT-2026-143 / RFP17-50). The letter prefix is capped
# at 4 chars and the token must carry two adjacent digits, so title words that
# look reference-ish (COVID-19 is 5 letters, E-BIDDING has no digits) never
# read as references. Never fabricate a reference.
_REF_PAT = (r"(?:\d{4}-\d{2,5}[A-Za-z]{0,3}"
            r"|(?=\S*\d\d)[A-Z]{1,4}\d{0,4}(?:-[A-Za-z0-9]{1,7}){1,3})")
BID_REF = re.compile(rf"^{_REF_PAT}$")
BID_REF_WORD = re.compile(rf"\b{_REF_PAT}\b")
MAX_STORED_CHARS = 20000


def portal_url(subdomain: str) -> str:
    return f"https://{subdomain}.bidsandtenders.ca/Module/Tenders/en"


def bid_preview_url(subdomain: str, guid: str) -> str:
    return f"https://{subdomain}.bidsandtenders.ca/Module/Tenders/en/Tender/Preview/{guid}"


def parse_bid_name(strong_text: str):
    """'2026-104P - Pre-Purchase of Flow Meters...' -> ('2026-104P', 'Pre-Purchase...').
    If the leading token is not a bid reference, ref is None and the whole
    string is the title (never fabricate a reference)."""
    text = " ".join((strong_text or "").split())
    parts = re.split(r"\s[-–]\s", text, maxsplit=1)
    if len(parts) == 2 and BID_REF.match(parts[0]):
        return parts[0], parts[1].strip()
    return None, text


def parse_event_date(text: str):
    """'Wed Jul 15, 2026 12:00:00 PM (EDT)' -> ('2026-07-15', 'day'). Returns
    (None, None) when no full date parses (None beats a wrong date)."""
    m = re.search(r"\b([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})", text or "")
    if not m:
        return None, None
    mon = MONTHS.get(m.group(1))
    if not mon:
        return None, None
    return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(2)):02d}", "day"


def dedupe_phrase(text: str) -> str:
    """Collapse a cleanly-doubled cell to a single copy. The fuelux repeater
    nests a `.repeater-list-heading` div inside each header cell, so the th's
    innerText is 'Bid Name Bid Name'; some data cells double the same way. When
    the string is exactly X + ' ' + X, return X; otherwise leave it untouched
    (never risk mangling a genuinely repetitive value)."""
    s = " ".join((text or "").split())
    n = len(s)
    if n and n % 2 == 1 and s[n // 2] == " " and s[: n // 2] == s[n // 2 + 1:]:
        return s[: n // 2]
    return s


def map_columns(header_cells):
    """Header text -> column index, so extraction is driven by the grid's own
    headers (robust across municipalities and the Open vs Awarded views)."""
    idx = {}
    for i, c in enumerate(header_cells):
        key = dedupe_phrase(c).lower()
        if key:
            idx[key] = i
    return idx


def _col(idx: dict, row: list, *names):
    for n in names:
        j = idx.get(n)
        if j is None:  # tolerate header drift: fall back to a substring match
            j = next((v for k, v in idx.items() if n in k), None)
        if j is not None and j < len(row):
            return row[j]
    return ""


def build_payload(muni: dict, source_id: str, doc_type: str, row: dict,
                  keywords: Keywords) -> dict:
    ref = row.get("ref")
    title = row.get("title") or "(untitled bid)"
    date_iso, precision = parse_event_date(row.get("date") or "")
    url = (bid_preview_url(muni["subdomain"], row["guid"]) if row.get("guid")
           else portal_url(muni["subdomain"]))
    body = row.get("raw") or title
    # Tag-only relevance: keep everything, mark defence_relevant if it matches.
    result = evaluate(title, body[:MAX_STORED_CHARS], "", keywords)
    # Identity: reference (the hard key) + doc_type + status, so a bid moving
    # open -> awarded inserts as a fresh document (the lifecycle is the signal),
    # while a re-seen unchanged row dedupes.
    chash = content_hash(ref or url, doc_type, row.get("status") or "")
    return {
        "source_id": source_id,
        "url": url,
        "title": title[:500],
        "doc_type": doc_type,
        "status": "captured",
        "published_on": date_iso,
        "date_precision": precision,
        "reference_number": ref,          # hard key for the proposer + arc walk
        "content_hash": chash,
        "content": body[:MAX_STORED_CHARS] or None,
        "defence_relevant": result.defence_relevant,
        # The buyer is structural on a municipal portal: store it
        # deterministically rather than leaving extraction to infer it.
        "buyer_name": muni.get("name"),
    }


# Broad row selector (fuelux repeater + plain table). A CSS selector list
# dedupes elements, so a <tr> matched by several clauses is read once.
ROW_SEL = ".repeater-canvas tr, .repeater-list-items tr, table tr, tbody tr"

# The default (Open) grid auto-loads on page render with a real UA (67 live Peel
# rows in the spike, counted BEFORE any click). The other status tabs are
# <li>/<a> JS handlers that fire the guarded Tender/Search call only on click;
# a plain JS exact-text click works where Playwright's get_by_role timed out.
_CLICK_TAB_JS = """(label) => {
  const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const el = [...document.querySelectorAll('a, li, button, span')]
    .find(e => norm(e.innerText) === label.toLowerCase());
  if (el) { el.click(); return true; }
  return false;
}"""

# A populated grid has at least one row whose text carries a bid reference.
# Waiting on this (not on a guessed td/strong structure) is what makes the read
# robust to the platform's exact cell markup. Built from _REF_PAT so the wait
# accepts every reference shape the parser accepts.
_HAS_BID_ROW_JS = ("(sel) => {\n"
                   f"  const re = /\\b{_REF_PAT}\\b/;\n"
                   "  return [...document.querySelectorAll(sel)]"
                   ".some(tr => re.test(tr.innerText || ''));\n"
                   "}")


def read_grid(page, status_label: str, is_default: bool) -> list:
    """Read one status grid, header-driven. The default (Open) grid auto-loads,
    so it is read without clicking (clicking the active tab races/clears it);
    any other tab is clicked to fire its guarded data call. Returns a list of
    {ref, title, status, date, guid, raw}. An empty tab (a legitimately
    award-less municipality) times out on the wait and returns []."""
    if is_default:
        # Just wait for the auto-loaded rows to actually paint.
        try:
            page.wait_for_function(_HAS_BID_ROW_JS, arg=ROW_SEL, timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(1000)
    else:
        page.evaluate(_CLICK_TAB_JS, status_label)
        page.wait_for_timeout(4500)  # let the guarded Search call repaint the grid

    grid = page.eval_on_selector_all(
        ROW_SEL,
        "trs => trs.map(tr => [...tr.querySelectorAll('th,td')].map(c => (c.innerText||'').trim()))")
    grid = [[dedupe_phrase(c) for c in row] for row in grid]
    # Bid GUID per reference: from each 'Register for this Bid - <ref> ...' link.
    links = page.eval_on_selector_all(
        "a[href*='/Tender/Terms/']",
        "els => els.map(e => ({href: e.getAttribute('href')||'', txt: (e.innerText||e.textContent||'')}))")
    guid_by_ref = {}
    for l in links:
        gm = re.search(r"/Tender/Terms/([0-9a-fA-F-]{36})", l["href"])
        rm = BID_REF_WORD.search(l["txt"])
        if gm and rm:
            guid_by_ref.setdefault(rm.group(0), gm.group(1))

    header = next((r for r in grid if any("bid name" in (c or "").lower() for c in r)), None)
    if not header:
        log.warning("[read_grid %s] no 'bid name' header in %d grid rows; first=%r",
                    status_label, len(grid), grid[:2])
        return []
    idx = map_columns(header)
    out = []
    for r in grid:
        if r is header or len(r) < 2:
            continue
        name = _col(idx, r, "bid name")
        ref, title = parse_bid_name(name)
        if not title or "bid name" in name.lower():
            continue  # skip the header echo / empty spacer rows
        if ref is None:
            # bids&tenders assigns every bid a reference number (e.g. 2026-104P);
            # the grid's trailing pager and page-size controls read as ref-less
            # rows ('<', page numbers). A ref-less row is not a bid, and would be
            # unkeyable for the spine anyway, so drop it rather than pollute.
            continue
        out.append({
            "ref": ref, "title": title,
            "status": _col(idx, r, "bid status") or status_label,
            "date": _col(idx, r, "bid closing date", "award date", "awarded date",
                         "closing date", "date awarded"),
            "guid": guid_by_ref.get(ref),
            "raw": " | ".join(c for c in r if c),
        })
    if not out:
        log.warning("[read_grid %s] header found but 0 data rows parsed; grid rows=%d",
                    status_label, len(grid))
    return out


def status_query_url(base: str, status: str, limit: int, start: int,
                     sort: str | None = None) -> str:
    """Rewrite the captured Open Search URL for a different status/page, keeping
    every other query param (sort/dir/from/to) so the awarded query stays bounded
    and ordered the same way the app orders it. `sort` overrides the captured
    sort when the caller needs a specific ordering."""
    parts = urlsplit(base)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q["status"] = status
    q["limit"] = str(limit)
    q["start"] = str(start)
    if sort:
        q["sort"] = sort
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def confirm_open_empty(page, captured: dict) -> bool:
    """An empty Open grid is believed ONLY when the portal's own guarded Search
    endpoint says total=0 for status=Open (YRP had zero open bids on
    2026-07-20: a single police service legitimately idles between postings).
    Everything else -- no captured call, non-200, non-JSON, total>0 -- stays a
    loud failure, because a gated portal also renders an empty grid."""
    if "url" not in captured:
        return False
    headers = {k: v for k, v in captured["headers"].items() if not k.startswith(":")}
    url = status_query_url(captured["url"], "Open", 1, 0)
    try:
        resp = page.request.post(url, headers=headers,
                                 data=captured.get("post_data") or "", timeout=45000)
        if resp.status != 200:
            return False
        return (resp.json().get("total") or 0) == 0
    except Exception:
        return False


def awarded_row_from_json(jr: dict) -> dict:
    """One awarded Search-JSON row -> the row shape build_payload expects. The
    reference comes from Title (the hard key); the date is the closing date, the
    only timestamp this endpoint exposes (there is no distinct award date, so we
    do not invent one). Vendor/value are not in this payload by design."""
    ref, title = parse_bid_name(jr.get("Title") or "")
    return {
        "ref": ref,
        "title": title or (jr.get("Description") or "").strip(),
        "status": jr.get("Status") or "Awarded",
        "date": jr.get("DateClosingDisplay") or "",
        "guid": jr.get("Id"),
        "raw": " | ".join(x for x in (jr.get("Title"), jr.get("Scope"),
                                      jr.get("Status")) if x),
    }


def fetch_awarded(page, captured: dict, muni: dict, source_id, keywords,
                  stats: dict, dry_run: bool) -> int:
    """Method B: replay the page's guarded Search call with ?status=Awarded,
    paging through the awarded history and emitting award_notice documents keyed
    on the bid reference. Returns the number of awarded rows read.

    LOUD-FAILURE GUARD: a live Peel portal has years of awarded bids, so zero
    awarded rows means the token capture or endpoint broke, not a quiet truth."""
    base = captured["url"]
    headers = {k: v for k, v in captured["headers"].items() if not k.startswith(":")}
    post_data = captured.get("post_data") or ""
    read = 0
    start = 0
    while start < AWARDED_MAX:
        # Newest-first, so when a portal's awarded history exceeds AWARDED_MAX
        # (York: 3301 rows) the cap drops the OLDEST awards, never the newest.
        # The captured call sorts DateClosing ASC; keeping that would cap away
        # the most recent -- exactly the rows the product is for.
        url = status_query_url(base, "Awarded", AWARDED_PAGE, start,
                               sort="DateClosing DESC,Id")
        resp = page.request.post(url, headers=headers, data=post_data, timeout=45000)
        if resp.status != 200:
            raise RuntimeError(f"[{muni['org_key']}] awarded endpoint HTTP {resp.status}")
        doc = resp.json()
        data = doc.get("data") or []
        total = doc.get("total") or 0
        if not data:
            break
        for jr in data:
            row = awarded_row_from_json(jr)
            if row["ref"] is None:
                continue  # no reference -> unkeyable, not a real awarded bid row
            read += 1
            # Resilient per-row: the awarded backfill is ~thousands of sequential
            # inserts; one transient DB/network blip must NOT abort the whole run
            # (content_hash makes a re-run resume). A row failure is logged and
            # counted; only a PILE of failures (systemic auth/endpoint/DB problem)
            # exceeds the budget and fails loudly.
            try:
                payload = build_payload(muni, source_id, "award_notice", row, keywords)
                if supabase_client.get_document_by_hash(payload["content_hash"]):
                    stats["skipped_duplicate"] += 1
                    continue
                if dry_run:
                    log.info("[dry-run] %-13s ref=%-10s closed=%s :: %s",
                             "award_notice", row["ref"], payload["published_on"],
                             (payload["title"] or "")[:66])
                else:
                    supabase_client.insert_document(payload)
                stats["inserted"] += 1
            except Exception:
                stats["errors"] += 1
                log.warning("[%s] awarded row failed (ref=%s); continuing",
                            muni["org_key"], row.get("ref"))
                if stats["errors"] > AWARDED_ERROR_BUDGET:
                    raise RuntimeError(
                        f"[{muni['org_key']}] awarded backfill exceeded the error budget "
                        f"({stats['errors']} row failures): systemic, not transient. Aborting.")
        start += AWARDED_PAGE
        if start >= total:
            break
    if read == 0:
        raise RuntimeError(
            f"[{muni['org_key']}] AWARDED endpoint returned 0 rows: token capture "
            f"or endpoint changed. Refusing to record silence.")
    stats["read"] += read
    return read


def collect(dry_run: bool = True) -> dict:
    """Render each municipality's portal with a real UA. Read the Open grid
    (tender_notice, Method A) and replay the awarded data call (award_notice,
    Method B). LOUD-FAILURE GUARDS: an empty Open grid or empty Awarded set
    raises."""
    from playwright.sync_api import sync_playwright  # lazy: heavy optional dep

    keywords = load_keywords()
    sources = supabase_client.fetch_rows("sources", "id,url")
    src_by_url = {(s.get("url") or "").rstrip("/"): s["id"] for s in sources}
    stats = {"read": 0, "inserted": 0, "skipped_duplicate": 0, "errors": 0,
             "per_portal": {}}
    failed_portals: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for muni in MUNICIPALITIES:
            url = portal_url(muni["subdomain"])
            source_id = src_by_url.get(url.rstrip("/"))
            if not source_id and not dry_run:
                raise RuntimeError(
                    f"no sources row for {url}; apply the bids&tenders sources seed first")
            page = browser.new_context(user_agent=REAL_UA,
                                        viewport={"width": 1400, "height": 900}).new_page()
            # Capture the page's own guarded Search call (Method B needs its URL,
            # CSRF token body and headers) as it auto-fires on load.
            captured: dict = {}

            def _grab(req, _c=captured):
                if SEARCH_RE.search(req.url) and req.method == "POST" and "url" not in _c:
                    _c["url"] = req.url
                    try:
                        _c["headers"] = req.all_headers()
                    except Exception:
                        _c["headers"] = dict(req.headers)
                    _c["post_data"] = req.post_data or ""

            page.on("request", _grab)
            val = {"open_rows": 0, "ref_parsed": 0, "date_parsed": 0, "awarded_rows": 0}
            stats["per_portal"][muni["org_key"]] = val
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(3000)
                for label, doc_type in TAB_DOC_TYPE:
                    rows = read_grid(page, label, is_default=(doc_type == "tender_notice"))
                    log.info("[%s] %s: %d rows", muni["org_key"], label, len(rows))
                    # LOUD-FAILURE GUARD (Open only; Awarded may legitimately be
                    # empty). Escape hatch: an empty Open grid is accepted when
                    # the portal's own endpoint confirms total=0 open bids.
                    if label == "Open" and not rows:
                        if confirm_open_empty(page, captured):
                            log.warning(
                                "[%s] OPEN grid empty; endpoint confirms total=0 "
                                "open bids. Continuing to Awarded.", muni["org_key"])
                        else:
                            raise RuntimeError(
                                f"[{muni['org_key']}] OPEN grid returned 0 rows: gated or "
                                f"markup changed. Refusing to record silence.")
                    for row in rows:
                        stats["read"] += 1
                        payload = build_payload(muni, source_id, doc_type, row, keywords)
                        if label == "Open":
                            val["open_rows"] += 1
                            val["ref_parsed"] += 1 if payload["reference_number"] else 0
                            val["date_parsed"] += 1 if payload["published_on"] else 0
                        if supabase_client.get_document_by_hash(payload["content_hash"]):
                            stats["skipped_duplicate"] += 1
                            continue
                        if dry_run:
                            log.info("[dry-run] %-13s ref=%-10s close=%s :: %s",
                                     doc_type, row.get("ref"), payload["published_on"],
                                     (payload["title"] or "")[:70])
                        else:
                            supabase_client.insert_document(payload)
                        stats["inserted"] += 1

                # Awarded rung (Method B): replay the captured guarded call.
                if "url" not in captured:
                    raise RuntimeError(
                        f"[{muni['org_key']}] never captured the Search call on load; "
                        f"cannot replay the awarded endpoint. Refusing to record silence.")
                n_awd = fetch_awarded(page, captured, muni, source_id, keywords,
                                      stats, dry_run)
                log.info("[%s] Awarded: %d rows", muni["org_key"], n_awd)
                val["awarded_rows"] = n_awd
                # The per-portal validation line the enablement bar reads
                # (docs/big12-tier1-design.md: >=90% parsed ref+date, live
                # awarded replay).
                o = val["open_rows"] or 1
                log.info("VALIDATION [%s]: open=%d ref_parsed=%d (%d%%) "
                         "date_parsed=%d (%d%%) awarded=%d",
                         muni["org_key"], val["open_rows"], val["ref_parsed"],
                         round(100 * val["ref_parsed"] / o), val["date_parsed"],
                         round(100 * val["date_parsed"] / o), val["awarded_rows"])
            except Exception:
                # Per-portal isolation (tier-1 design): one gated portal must
                # not blind the rest. Record it, keep going, and fail the run
                # at the END so the day still goes red naming the portal.
                log.exception("[%s] collection error", muni["org_key"])
                stats["errors"] += 1
                failed_portals.append(muni["org_key"])
            finally:
                page.close()
        browser.close()
    log.info("bids&tenders: %s", stats)
    if failed_portals and not dry_run:
        raise RuntimeError(
            f"bids&tenders: {len(failed_portals)} portal(s) failed "
            f"({', '.join(failed_portals)}); the others were collected. "
            f"See the per-portal errors above.")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="bids&tenders municipal tender/award collector")
    parser.add_argument("--dry-run", action="store_true",
                        help="render and report, write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    collect(dry_run=args.dry_run)
    sys.exit(0)
