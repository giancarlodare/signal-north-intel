"""Front 1 pass-4 (read-only): probe Supply Ontario's procurement-bulletins
surface for the actual opportunity/award listings, robots posture, server-side
vs JS, and whether OPP / SolGen buys are isolable.

Pass-3 established supplyontario.ca is the real provincial procurement surface
(the ontario.ca hub links it; become-a-vendor named OPP). This follows the
bulletins listing to its items. Robots honored, 2s politeness, no accounts.

    python scripts/probe_supplyontario.py
"""
import sys
from urllib.parse import urlparse

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher, extract_links

TARGETS = [
    ("Procurement bulletins", "https://www.supplyontario.ca/procurement-bulletins/"),
    ("Become a vendor", "https://www.supplyontario.ca/become-a-vendor/"),
    ("Opportunities", "https://www.supplyontario.ca/opportunities/"),
    ("Bulletins (alt)", "https://www.supplyontario.ca/bulletins/"),
]
PROC = ["tender", "opportunit", "solicitation", "award", "closing date",
        "vendor of record", "procurement", "rfp", "rfq", "bulletin", "posting"]
ISOLATE = ["ontario provincial police", "opp", "solicitor general",
           "community safety", "ministry of the solicitor"]
ITEM_HINT = ["bulletin", "opportunit", "tender", "posting", "notice", "award",
             "solicitation"]


def _hits(text, markers):
    low = (text or "").lower()
    return [m for m in markers if m in low]


def probe(fetcher, label, url):
    print("=" * 72)
    print(f"{label}\n  {url}")
    if not fetcher.allowed(url):
        print("  robots DISALLOWED; human-research-only.")
        return
    try:
        r = fetcher.get(url)
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {str(e)[:130]}")
        return
    if r is None:
        return
    html = r.text or ""
    n_script = html.lower().count("<script")
    text_only = " ".join(s for s in html.replace(">", "> ").split()
                         if not s.startswith("<"))
    js_shell = len(html) < 40000 and n_script > 3 and len(text_only) < 2000
    print(f"  status={r.status_code} bytes={len(html)} <script>={n_script} "
          f"text_chars={len(text_only)}")
    print(f"  server-side: {'NO (JS shell)' if js_shell else 'YES'}")
    print(f"  proc markers: {_hits(html, PROC) or 'none'}")
    print(f"  OPP/SolGen:   {_hits(html, ISOLATE) or 'none'}")
    # item-shaped links (the individual bulletins / opportunities)
    items, seen = [], set()
    for u, t in extract_links(html, url):
        blob = f"{u} {t}".lower()
        if any(h in blob for h in ITEM_HINT) and u not in seen \
                and urlparse(u).netloc.endswith("supplyontario.ca"):
            seen.add(u)
            items.append((u, " ".join((t or "").split())[:60]))
    print(f"  item-shaped links: {len(items)}")
    for u, t in items[:12]:
        print(f"    {u}  :: {t}")


def main():
    fetcher = PoliteFetcher()
    for label, url in TARGETS:
        probe(fetcher, label, url)
    print("=" * 72)
    print("PASS-4 COMPLETE (read-only).")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
    sys.exit(0)
