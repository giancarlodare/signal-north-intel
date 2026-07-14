"""Municipal tender + award collector for the bids&tenders platform.

Access method A (headless render-and-read), decided on evidence in
docs/peel-tenders-design.md. bids&tenders serves a CSRF-guarded, JS-rendered
fuelux grid with no inline data and a soft-404 robots. Five probes and a
feasibility spike established:

  * a REAL browser User-Agent is REQUIRED: the HeadlessChrome UA is served a
    dead (empty) grid. This is the silent-empty failure mode, so it is guarded
    against loudly (see LOUD-FAILURE GUARD below);
  * the open-bids grid renders once loaded with a real UA (67 live Peel rows in
    the spike); the guarded data endpoint is
    POST /Module/Tenders/en/Tender/Search/<moduleGUID>?status=<Status>, kept
    documented as a future Method-B fast-path if CI cost bites, NOT used now.

LOUD-FAILURE GUARD: a municipality's OPEN tab returning zero rows is treated as
an error (raise), never a silent no-op, because a live bids&tenders portal
essentially always has open bids and zero rows means we were gated (bad UA,
blocked, markup change). Silent-empty is the failure we most need to avoid for a
hit-rate product.

Mapping to the existing spine (no schema change): an open bid is a
`tender_notice` (in_market, grade 4) whose CLOSING date is a future event
(Path B imminent in the brief); an awarded bid is an `award_notice` (awarded,
grade 5) that settles reconciliation. The bid reference number (e.g. 2026-104P)
is written to `documents.reference_number`, the hard key the procurement
proposer clusters on and the link the demand-arc backtest walks.

Coverage multiplier: parameterized by {org_key, subdomain}. Peel is the first
row; every other *.bidsandtenders.ca municipality is a config row, no new code.

    python -m src.tenders_bidsandtenders --dry-run   # render + report, write nothing
    python -m src.tenders_bidsandtenders             # collect for real
"""
import argparse
import logging
import re
import sys

from . import config, supabase_client
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

# {org_key, subdomain, name}. Add a row per municipality; no code change.
MUNICIPALITIES = [
    {"org_key": "peel", "subdomain": "peelregion", "name": "Region of Peel"},
]

# A real desktop Chrome UA. The headless UA is gated to an empty grid, so this
# is not cosmetic: it is load-bearing (see module docstring).
REAL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# Status tab label -> doc_type. Open bids are the forward signal; Awarded settles
# reconciliation. (Closed and Unofficial Results are deliberately not collected:
# closed-no-award is not a demand event, and unofficial results are preliminary.)
TAB_DOC_TYPE = [("Open", "tender_notice"), ("Awarded", "award_notice")]

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

BID_REF = re.compile(r"^\d{4}-\d{2,5}[A-Za-z]{0,3}$")
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


def map_columns(header_cells):
    """Header text -> column index, so extraction is driven by the grid's own
    headers (robust across municipalities and the Open vs Awarded views)."""
    idx = {}
    for i, c in enumerate(header_cells):
        key = " ".join((c or "").split()).lower()
        if key:
            idx[key] = i
    return idx


def _col(idx: dict, row: list, *names):
    for n in names:
        j = idx.get(n)
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
    }


ROW_SEL = "table tr, .repeater-canvas tr, .repeater-list-items tr"
# A populated grid has at least one data cell holding a bid-name <strong>.
BID_CELL = "table td strong, .repeater-canvas td strong"


def read_grid(page, status_label: str, is_default: bool) -> list:
    """Read a status tab's rendered rows, header-driven. Returns a list of
    {ref, title, status, date, guid, raw}. Playwright page in scope.

    is_default: the Open tab is the view the portal loads on its own; clicking
    it re-fetches and can leave the grid transiently empty (the 0-rows bug the
    dry-run caught). So we click ONLY non-default tabs, and either way we WAIT
    for real rows to populate (a bid-name cell) rather than a fixed sleep."""
    if not is_default:
        try:
            page.get_by_role("link", name=status_label, exact=True).first.click(timeout=8000)
        except Exception:
            page.evaluate(
                """(label) => { const el = [...document.querySelectorAll('a,button,li,span')]
                     .find(e => (e.innerText||'').trim().toLowerCase() === label.toLowerCase());
                     if (el) el.click(); }""", status_label)
    # Wait for the guarded data call to actually populate the grid. An empty
    # tab (a legitimately award-less municipality) just times out and returns [].
    try:
        page.wait_for_selector(BID_CELL, timeout=30000)
    except Exception:
        pass
    page.wait_for_timeout(1500)

    grid = page.eval_on_selector_all(
        ROW_SEL,
        "trs => trs.map(tr => [...tr.querySelectorAll('th,td')].map(c => (c.innerText||'').trim()))")
    # Bid GUID per reference: from each 'Register for this Bid - <ref> ...' link.
    links = page.eval_on_selector_all(
        "a[href*='/Tender/Terms/']",
        "els => els.map(e => ({href: e.getAttribute('href')||'', txt: (e.innerText||e.textContent||'')}))")
    guid_by_ref = {}
    for l in links:
        gm = re.search(r"/Tender/Terms/([0-9a-fA-F-]{36})", l["href"])
        rm = re.search(r"\b(\d{4}-\d{2,5}[A-Za-z]{0,3})\b", l["txt"])
        if gm and rm:
            guid_by_ref.setdefault(rm.group(1), gm.group(1))

    header = next((r for r in grid if any("bid name" in (c or "").lower() for c in r)), None)
    if not header:
        return []
    idx = map_columns(header)
    out = []
    for r in grid:
        if len(r) < len(header) or r is header:
            continue
        name = _col(idx, r, "bid name")
        ref, title = parse_bid_name(name)
        if not name or (ref is None and "bid name" in " ".join(r).lower()):
            continue  # skip the header echo / empty
        if not title:
            continue
        out.append({
            "ref": ref, "title": title,
            "status": _col(idx, r, "bid status") or status_label,
            "date": _col(idx, r, "bid closing date", "award date", "awarded date",
                         "closing date", "date awarded"),
            "guid": guid_by_ref.get(ref),
            "raw": " | ".join(c for c in r if c),
        })
    return out


def collect(dry_run: bool = True) -> dict:
    """Render each municipality's portal with a real UA and read its Open
    (tender_notice) and Awarded (award_notice) grids. LOUD-FAILURE GUARD: an
    empty Open grid raises."""
    from playwright.sync_api import sync_playwright  # lazy: heavy optional dep

    keywords = load_keywords()
    sources = supabase_client.fetch_rows("sources", "id,url")
    src_by_url = {(s.get("url") or "").rstrip("/"): s["id"] for s in sources}
    stats = {"read": 0, "inserted": 0, "skipped_duplicate": 0, "errors": 0}

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
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(3000)
                for label, doc_type in TAB_DOC_TYPE:
                    rows = read_grid(page, label, is_default=(label == "Open"))
                    log.info("[%s] %s: %d rows", muni["org_key"], label, len(rows))
                    # LOUD-FAILURE GUARD (Open only; Awarded may legitimately be empty).
                    if label == "Open" and not rows:
                        raise RuntimeError(
                            f"[{muni['org_key']}] OPEN grid returned 0 rows: gated or "
                            f"markup changed. Refusing to record silence.")
                    for row in rows:
                        stats["read"] += 1
                        payload = build_payload(muni, source_id, doc_type, row, keywords)
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
            except Exception:
                log.exception("[%s] collection error", muni["org_key"])
                stats["errors"] += 1
                if not dry_run:
                    raise  # fail loudly: a broken run must not look like a quiet one
            finally:
                page.close()
        browser.close()
    log.info("bids&tenders: %s", stats)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="bids&tenders municipal tender/award collector")
    parser.add_argument("--dry-run", action="store_true",
                        help="render and report, write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    collect(dry_run=args.dry_run)
    sys.exit(0)
