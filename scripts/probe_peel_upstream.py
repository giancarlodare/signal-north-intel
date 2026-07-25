"""Front 2 probe (read-only): find Peel Regional Police's UPSTREAM intent
sources for the one-service precision proof, and the leading-indicator
(crime/auto-theft open-data) feeds.

Reports per candidate: robots posture, server-side HTML vs JS shell, presence
of news/statement/data content, and any RSS/feed/API. Robots honored, 2s
politeness, no accounts. The design (docs/upstream-intent-layer-design.md)
turns whatever passes here into the intent-extraction proof corpus.

    python scripts/probe_peel_upstream.py
"""
import re
import sys

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher

TARGETS = [
    # Service newsroom / media releases
    ("Peel Police home", "https://www.peelpolice.ca/"),
    ("Peel Police news", "https://www.peelpolice.ca/en/news.aspx"),
    ("Peel Police newsroom", "https://www.peelpolice.ca/en/news/news-releases.aspx"),
    ("Peel Police news RSS", "https://www.peelpolice.ca/Modules/News/en/rss"),
    # Police services board
    ("Peel Police Services Board", "https://www.peelpoliceboard.ca/"),
    ("Peel Police Board meetings", "https://www.peelpoliceboard.ca/en/board-meetings.aspx"),
    # Leading-indicator open data (crime / auto-theft pressure signals)
    ("Peel Police open data", "https://opendata.peelpolice.ca/"),
    ("Region of Peel open data", "https://data.peelregion.ca/"),
    ("Peel Police crime map", "https://www.peelpolice.ca/en/about-us/crime-statistics.aspx"),
]

NEWS = ["news", "media release", "statement", "chief", "announce", "press"]
DATA = ["dataset", "auto theft", "auto-theft", "crime", "open data", "csv",
        "api", "arcgis", "ckan"]
FEED = ["rss", "/feed", ".json", "atom", "opendata", "arcgis", "ckan"]


def _hits(text, markers):
    low = text.lower()
    return [m for m in markers if m in low]


def probe(fetcher, label, url):
    print("=" * 70)
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
        print("  fetch returned None.")
        return
    html = r.text or ""
    n_script = html.lower().count("<script")
    text_only = " ".join(s for s in html.replace(">", "> ").split()
                         if not s.startswith("<"))
    js_shell = len(html) < 40000 and n_script > 3 and len(text_only) < 2000
    print(f"  status={r.status_code} bytes={len(html)} <script>={n_script} "
          f"text_chars={len(text_only)}")
    print(f"  server-side: {'NO (JS shell)' if js_shell else 'YES'}")
    print(f"  news markers: {_hits(html, NEWS) or 'none'}")
    print(f"  data markers: {_hits(html, DATA) or 'none'}")
    print(f"  feed hints:   {_hits(html, FEED) or 'none'}")


def main():
    fetcher = PoliteFetcher()
    for label, url in TARGETS:
        probe(fetcher, label, url)
    print("=" * 70)
    print("PEEL UPSTREAM PROBE COMPLETE (read-only).")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
    sys.exit(0)
