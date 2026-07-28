"""Step-1 structure probe for the London Police Service bids page
(docs/london-police-tenders-design.md, gated design approved 2026-07-28).

Read-only, no DB writes, no LLM: fetches robots.txt and the bids page,
reports the markup shape (tables, lists, headings), the links and any PDF
documents, and whether open/awarded sections are distinguishable. The output
decides whether the collector build (step 2) proceeds or the source parks
with evidence, Niagara-Falls style.

Run from CI (the sandbox proxy blocks external sites):
    python scripts/probe_londonpolice_bids.py
"""
import os
import re
import sys
import time
import urllib.robotparser

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE = "https://www.londonpolice.ca"
PAGE = f"{BASE}/about/bids-and-tenders/"
UA = "SignalNorthIntel/1.0"


def fetch(url: str) -> requests.Response:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    print(f"\n=== {url}\n    status={r.status_code} type={r.headers.get('content-type')} "
          f"bytes={len(r.content)}")
    return r


def main() -> int:
    rp = urllib.robotparser.RobotFileParser()
    robots = fetch(f"{BASE}/robots.txt")
    rp.parse(robots.text.splitlines())
    allowed = rp.can_fetch(UA, PAGE)
    print(f"    robots allows {PAGE}: {allowed}")
    if not allowed:
        print("STOP: robots disallows the bids page; park the source.")
        return 2

    time.sleep(2)  # politeness
    r = fetch(PAGE)
    html = r.text

    for tag in ("table", "ul", "ol", "article", "section", "iframe", "form"):
        n = len(re.findall(rf"<{tag}\b", html, re.IGNORECASE))
        if n:
            print(f"    <{tag}> x{n}")

    print("\n--- headings ---")
    for m in re.finditer(r"<(h[1-4])[^>]*>(.*?)</\1>", html, re.IGNORECASE | re.DOTALL):
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if text:
            print(f"    {m.group(1)}: {text[:100]}")

    print("\n--- table headers (th) ---")
    for m in re.finditer(r"<th[^>]*>(.*?)</th>", html, re.IGNORECASE | re.DOTALL):
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if text:
            print(f"    th: {text[:80]}")

    print("\n--- links (bid-relevant sample) ---")
    seen = 0
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                         html, re.IGNORECASE | re.DOTALL):
        href, label = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        low = (href + " " + label).lower()
        if any(k in low for k in (".pdf", "bid", "tender", "rfp", "rfq",
                                  "proposal", "quotation", "award", "media",
                                  "purchas", "procure")):
            print(f"    {label[:70]!r} -> {href[:120]}")
            seen += 1
            if seen >= 40:
                print("    ... (truncated at 40)")
                break

    print("\n--- iframe/embed sources (third-party widget check) ---")
    for m in re.finditer(r'<(?:iframe|embed|script)[^>]+src="([^"]+)"', html,
                         re.IGNORECASE):
        src = m.group(1)
        if BASE not in src and not src.startswith("/"):
            print(f"    external: {src[:140]}")

    print("\nProbe complete. Read the sections above against the design's "
          "step-2 bar: parseable listing with fields, or park with evidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
