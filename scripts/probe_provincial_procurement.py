"""Read-only probe: does Ontario's provincial procurement layer publish
opportunities/awards collectably, and can OPP / SolGen buys be isolated?

Front 1 of the mid-August scope (operator 2026-07-25): OPP operational
procurement, no dependency, this week. Scopes the CPO/provincial probe to the
provincial marketplace and vendor-of-record layer:

  - doingbusiness.mgs.gov.on.ca  (Supply Chain Ontario marketplace / "Doing
    Business with the Ontario Government")
  - ontario.ca Supply Chain Ontario + Vendor of Record (VOR) pages
  - the Ontario Tenders Portal recheck (Jaggaer; robots posture only)

For each surface this reports: robots posture (can_fetch), server-side HTML vs
JS shell, whether procurement content (opportunities/awards/VOR) is present in
the raw HTML, any structured-feed/API hints, and whether OPP / Solicitor
General buys are namable in the text. PROBE ONLY: no accounts, no collection,
2s politeness, robots honored absolutely (a Disallow is reported, never
bypassed).

    python scripts/probe_provincial_procurement.py
"""
import sys

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher

TARGETS = [
    ("SCO marketplace root", "https://doingbusiness.mgs.gov.on.ca/"),
    ("SCO marketplace (en)", "https://www.doingbusiness.mgs.gov.on.ca/"),
    ("Ontario Tenders Portal", "https://ontariotenders.app.jaggaer.com/"),
    ("ontario.ca supply chain", "https://www.ontario.ca/page/supply-chain-ontario"),
    ("ontario.ca vendor of record", "https://www.ontario.ca/page/vendor-record-arrangements"),
    ("ontario.ca doing business", "https://www.ontario.ca/page/doing-business-ontario-government"),
]

# Content markers we look for in the raw (server-side) HTML.
PROC_MARKERS = ["tender", "opportunit", "solicitation", "bid ", "rfp", "rft",
                "vendor of record", "vor ", "award", "procurement", "competition"]
ISOLATE_MARKERS = ["ontario provincial police", "opp", "solicitor general",
                   "ministry of the solicitor", "community safety"]
FEED_MARKERS = ["/api/", "rss", ".json", "opendata", "ckan", "sitemap", "feed"]


def _hits(text: str, markers: list) -> list:
    low = text.lower()
    return [m.strip() for m in markers if m in low]


def safe_probe(fetcher: PoliteFetcher, label: str, url: str) -> None:
    print("=" * 70)
    print(f"{label}\n  {url}")
    try:
        allowed = fetcher.allowed(url)
        print(f"  robots can_fetch: {allowed}")
        if not allowed:
            print("  -> DISALLOWED by robots; human-research-only, not collected.")
            return
        resp = fetcher.get(url)
        if resp is None:
            print("  -> fetch returned None (robots); skipping.")
            return
        html = resp.text or ""
        n_script = html.lower().count("<script")
        # A JS shell is a small body dominated by scripts with little text.
        text_only = " ".join(
            s for s in html.replace(">", "> ").split() if not s.startswith("<"))
        print(f"  status={resp.status_code} bytes={len(html)} "
              f"<script>={n_script} approx_text_chars={len(text_only)}")
        js_shell = len(html) < 40000 and n_script > 0 and len(text_only) < 2000
        print(f"  server-side-content: {'NO (looks like a JS shell)' if js_shell else 'YES'}")
        print(f"  procurement markers: {_hits(html, PROC_MARKERS) or 'none'}")
        print(f"  OPP/SolGen isolable: {_hits(html, ISOLATE_MARKERS) or 'none'}")
        print(f"  feed/API hints:      {_hits(html, FEED_MARKERS) or 'none'}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {str(e)[:160]}")


def main() -> None:
    fetcher = PoliteFetcher()
    for label, url in TARGETS:
        safe_probe(fetcher, label, url)
    print("=" * 70)
    print("PROBE COMPLETE (read-only). Design verdict follows in "
          "docs/opp-provincial-procurement-design.md once results land.")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
    sys.exit(0)
