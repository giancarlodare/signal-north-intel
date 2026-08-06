"""Diagnostic probe for the four held bids&tenders buyers.

Runs a dry-run render of each held tenant and dumps the raw grid rows so we
can see exactly why each parser returns 0 items: header label variant, ref
format variant, or render-timing issue. Never writes to the database.

    python scripts/probe_held_buyers.py
"""
import logging
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from src.tenders_bidsandtenders import (
    ROW_SEL, REAL_UA, _HAS_BID_ROW_JS, _CLICK_TAB_JS, TAB_DOC_TYPE,
    dedupe_phrase, read_grid, BID_REF_WORD,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

HELD_TENANTS = [
    {"org_key": "markham",     "subdomain": "markham",        "name": "City of Markham"},
    {"org_key": "niagara",     "subdomain": "niagararegion",  "name": "Niagara Region"},
    {"org_key": "haltonhills", "subdomain": "haltonhills",    "name": "Town of Halton Hills"},
    {"org_key": "mississauga", "subdomain": "mississauga",    "name": "City of Mississauga"},
]

PORTAL_BASE = "https://{subdomain}.bidsandtenders.ca/Module/Tenders/en"
SEARCH_RE_STR = r"/Tender/Search/[0-9a-fA-F-]{36}"

import re
SEARCH_RE = re.compile(SEARCH_RE_STR)


def probe_tenant(page, muni: dict) -> None:
    url = PORTAL_BASE.format(**muni)
    key = muni["org_key"]
    log.info("[%s] Loading %s", key, url)

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
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        # Try to wait for a bid reference; log whether it succeeds.
        ref_found = False
        try:
            page.wait_for_function(_HAS_BID_ROW_JS, arg=ROW_SEL, timeout=30000)
            ref_found = True
        except Exception:
            pass
        log.info("[%s] _HAS_BID_ROW_JS wait: %s", key, "OK" if ref_found else "TIMED OUT (no ref match)")
        page.wait_for_timeout(1000)

        # Dump raw grid rows BEFORE any parsing filter.
        raw_grid = page.eval_on_selector_all(
            ROW_SEL,
            "trs => trs.map(tr => [...tr.querySelectorAll('th,td')].map(c => (c.innerText||'').trim()))")
        raw_grid = [[dedupe_phrase(c) for c in row] for row in raw_grid]
        log.info("[%s] ROW_SEL returned %d rows total", key, len(raw_grid))
        for i, row in enumerate(raw_grid[:8]):
            log.info("[%s]   row[%d]: %r", key, i, row)

        # Check if any row contains a bid reference.
        ref_in_any_row = any(BID_REF_WORD.search(" ".join(r)) for r in raw_grid)
        log.info("[%s] bid reference present in raw rows: %s", key, ref_in_any_row)

        # Run the real parser and report outcome.
        parsed = read_grid(page, "Open", is_default=True)
        log.info("[%s] read_grid parsed %d rows", key, len(parsed))
        for r in parsed[:5]:
            log.info("[%s]   parsed: ref=%s title=%r", key, r.get("ref"), r.get("title", "")[:60])

        # Report whether the Search call was captured (needed for awarded).
        log.info("[%s] Search call captured: %s", key, "yes" if "url" in captured else "NO")

    except Exception as e:
        log.error("[%s] probe failed: %s", key, e)
    finally:
        page.remove_listener("request", _grab)


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for muni in HELD_TENANTS:
            page = browser.new_context(
                user_agent=REAL_UA, viewport={"width": 1400, "height": 900}
            ).new_page()
            probe_tenant(page, muni)
            page.close()
        browser.close()
    log.info("Probe complete.")


if __name__ == "__main__":
    main()
