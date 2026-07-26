"""Read-only link discovery for two fronts (2026-07-25):

Front 1 pass-3: crawl the ontario.ca doing-business hub for its links to the
actual opportunity/award/marketplace endpoint, follow the top procurement
candidates, and report structure + OPP/SolGen isolation.

Front 2: crawl the Peel Regional Police and Police Services Board homepages for
their real news/statement listing URLs (the guessed .aspx paths 404'd), so the
upstream-intent adapter can be built against the true URLs.

Robots honored, 2s politeness, no accounts.

    python scripts/probe_discovery_links.py
"""
import sys
from urllib.parse import urlparse

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher, extract_links

HUB = "https://www.ontario.ca/page/doing-business-government-ontario"
HUB_KW = ["tender", "opportunit", "procure", "vendor", "supply chain",
          "supplychain", "marketplace", "bid", "award", "doingbusiness",
          "solicitation", "sourcing"]
NEWS_SITES = [
    ("Peel Regional Police", "https://www.peelpolice.ca/"),
    ("Peel Police Services Board", "https://www.peelpoliceboard.ca/"),
]
NEWS_KW = ["news", "media", "release", "statement", "newsroom", "press",
           "bulletin", "announce"]
PROC = ["tender", "opportunit", "solicitation", "award", "closing date",
        "vendor of record", "procurement", "rfp", "rfq"]
ISOLATE = ["ontario provincial police", "opp", "solicitor general",
           "community safety"]


def _hits(text, markers):
    low = (text or "").lower()
    return [m for m in markers if m in low]


def _links(fetcher, url):
    if not fetcher.allowed(url):
        print(f"  robots DISALLOWED: {url}")
        return None, []
    try:
        r = fetcher.get(url)
    except Exception as e:
        print(f"  ERROR {url}: {type(e).__name__}: {str(e)[:120]}")
        return None, []
    if r is None:
        return None, []
    return r, extract_links(r.text or "", url)


def _candidates(links, keywords):
    seen, out = set(), []
    for u, t in links:
        blob = f"{u} {t}".lower()
        if any(k in blob for k in keywords) and u not in seen:
            seen.add(u)
            out.append((u, " ".join((t or "").split())[:60]))
    return out


def main():
    fetcher = PoliteFetcher()
    print("=" * 70)
    print("FRONT 1 pass-3: ontario.ca doing-business hub links")
    r, links = _links(fetcher, HUB)
    if r is not None:
        cands = _candidates(links, HUB_KW)
        print(f"  hub status={r.status_code} total_links={len(links)} "
              f"procurement-shaped={len(cands)}")
        for u, t in cands[:20]:
            print(f"    {u}  :: {t}")
        # follow up to 3 candidate endpoints that leave ontario.ca/page
        followed = 0
        for u, _ in cands:
            host = urlparse(u).netloc
            if "ontario.ca" in host and "/page/" in u:
                continue   # sibling info pages, not the endpoint
            print(f"  -> FOLLOW {u}")
            rr, _ = _links(fetcher, u)
            if rr is not None:
                html = rr.text or ""
                print(f"       status={rr.status_code} bytes={len(html)} "
                      f"proc={_hits(html, PROC) or 'none'} "
                      f"OPP/SolGen={_hits(html, ISOLATE) or 'none'}")
            followed += 1
            if followed >= 3:
                break
    print("=" * 70)
    print("FRONT 2: Peel homepage news links")
    for label, url in NEWS_SITES:
        print(f"  {label}  {url}")
        r, links = _links(fetcher, url)
        if r is None:
            continue
        cands = _candidates(links, NEWS_KW)
        print(f"    total_links={len(links)} news-shaped={len(cands)}")
        for u, t in cands[:12]:
            print(f"      {u}  :: {t}")
    print("=" * 70)
    print("DISCOVERY COMPLETE (read-only).")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
    sys.exit(0)
