"""Front 1 pass-2 probe (read-only): find the provincial marketplace's
opportunity/award LISTINGS via its sitemap, test OPP/SolGen isolation, and
locate the real ontario.ca Supply Chain Ontario / Vendor of Record pages.

Pass 1 established www.doingbusiness.mgs.gov.on.ca is robots-allowed and
server-side with a sitemap, but the landing page was thin. This crawls the
sitemap for the listing pages and samples them. Robots honored absolutely, 2s
politeness, no accounts.

    python scripts/probe_provincial_pass2.py
"""
import re
import sys
from urllib.parse import urljoin

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher

BASE = "https://www.doingbusiness.mgs.gov.on.ca"
SITEMAPS = [f"{BASE}/sitemap.xml", f"{BASE}/sitemap_index.xml", f"{BASE}/sitemap"]
LISTING_HINT = re.compile(
    r"(tender|opportunit|solicitation|bid|rfp|award|procure|posting|notice)", re.I)
PROC = ["tender", "opportunit", "solicitation", "award", "vendor of record",
        "procurement", "closing date", "rfp", "rfq"]
ISOLATE = ["ontario provincial police", "opp", "solicitor general",
           "community safety", "ministry of the solicitor"]

ONTARIO_CANDIDATES = [
    "https://www.ontario.ca/page/how-buy-goods-and-services-ontario-government",
    "https://www.ontario.ca/page/supply-chain-management",
    "https://www.ontario.ca/page/selling-ontario-government",
    "https://www.ontario.ca/page/sell-ontario-government",
    "https://www.ontario.ca/page/vendor-record-arrangement",
    "https://www.ontario.ca/page/doing-business-government-ontario",
    "https://www.ontario.ca/page/ontario-public-service-procurement",
]


def _hits(text, markers):
    low = text.lower()
    return [m for m in markers if m in low]


def _get(fetcher, url):
    if not fetcher.allowed(url):
        print(f"  robots DISALLOWED: {url}")
        return None
    try:
        r = fetcher.get(url)
        return r
    except Exception as e:
        print(f"  ERROR {url}: {type(e).__name__}: {str(e)[:120]}")
        return None


def main():
    fetcher = PoliteFetcher()
    print("=" * 70)
    print("MARKETPLACE SITEMAP")
    locs = []
    for sm in SITEMAPS:
        r = _get(fetcher, sm)
        if r is None:
            continue
        found = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text or "")
        print(f"  {sm}: status={r.status_code} bytes={len(r.text)} locs={len(found)}")
        if found:
            locs = found
            break
    listings = [u for u in locs if LISTING_HINT.search(u)]
    print(f"  listing-shaped URLs: {len(listings)}")
    for u in listings[:10]:
        print(f"    {u}")
    print("=" * 70)
    print("SAMPLE LISTING PAGES")
    for u in (listings[:3] or locs[:3]):
        r = _get(fetcher, u)
        if r is None:
            continue
        html = r.text or ""
        print(f"  {u}\n    status={r.status_code} bytes={len(html)} "
              f"proc={_hits(html, PROC) or 'none'} "
              f"OPP/SolGen={_hits(html, ISOLATE) or 'none'}")
    print("=" * 70)
    print("ONTARIO.CA SCO / VOR CANDIDATES")
    for u in ONTARIO_CANDIDATES:
        r = _get(fetcher, u)
        if r is None:
            continue
        html = r.text or ""
        print(f"  {u}\n    status={r.status_code} bytes={len(html)} "
              f"proc={_hits(html, PROC) or 'none'}")
    print("=" * 70)
    print("PASS-2 COMPLETE (read-only).")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
    sys.exit(0)
