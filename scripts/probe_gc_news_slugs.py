"""GC news dept-slug repair probe (operator 2026-07-28, dead-feed fix):
the DND and RCMP feeds return empty because the API department slugs
changed. The operator's advanced-search URL shows dprtmnt=
departmentnationaldefense (no 'of', US 'defense'), so test candidates and
find the live slugs; also probe rcmp.ca/en/news, since the RCMP moved to
its own domain and may be off the canada.ca API entirely.

Read-only. CI only.
"""
import json
import re
import sys
import time
import urllib.robotparser

import requests

UA = "SignalNorthIntel/1.0"
API = ("https://api.io.canada.ca/io-server/gc/news/en/v2"
       "?dept={dept}&sort=publishedDate&orderBy=desc&pick=8&format=json")

CANDIDATES = {
    "DND": ["departmentnationaldefense", "departmentofnationaldefence",
            "departmentnationaldefence", "nationaldefence",
            "departmentofnationaldefense", "nationaldefense"],
    "RCMP": ["royalcanadianmountedpolice", "rcmp", "rcmpgrc",
             "royalcanadianmountedpolicercmp", "royalcanadianmountedpolicegrc"],
    "PS (control)": ["publicsafetycanada"],
}


def main() -> int:
    print("=" * 70 + "\n1. GC NEWS API SLUG HUNT\n" + "=" * 70)
    for label, slugs in CANDIDATES.items():
        print(f"\n  {label}:")
        for slug in slugs:
            time.sleep(2)
            try:
                r = requests.get(API.format(dept=slug),
                                 headers={"User-Agent": UA}, timeout=30)
                items = r.json().get("feed", {}).get("entry", [])
            except (requests.RequestException, ValueError):
                print(f"    {slug:<38} FETCH/PARSE FAILED")
                continue
            mark = "<== LIVE" if items else ""
            print(f"    {slug:<38} {len(items)} items {mark}")
            for i in items[:3]:
                print(f"        - {str(i.get('title', ''))[:76]}")

    print("\n" + "=" * 70 + "\n2. RCMP.CA NEWS SURFACE\n" + "=" * 70)
    base = "https://rcmp.ca"
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = requests.get(f"{base}/robots.txt", headers={"User-Agent": UA},
                         timeout=30)
        rp.parse(r.text.splitlines())
        print(f"  robots status={r.status_code}; allows /en/news: "
              f"{rp.can_fetch(UA, base + '/en/news')}")
    except requests.RequestException as e:
        print(f"  robots fetch failed ({type(e).__name__})")
        return 0
    if not rp.can_fetch(UA, base + "/en/news"):
        print("  robots disallows; RCMP news is human-research-only.")
        return 0
    time.sleep(2)
    r = requests.get(f"{base}/en/news", headers={"User-Agent": UA}, timeout=30)
    html = r.text
    print(f"  /en/news status={r.status_code} bytes={len(r.content)} "
          f"scripts={len(re.findall(r'<script', html, re.IGNORECASE))}")
    feeds = sorted(set(re.findall(
        r'href="([^"]*(?:rss|feed|atom|\.xml|/api/)[^"]*)"', html,
        re.IGNORECASE)))[:8]
    print(f"  feed-ish links: {feeds or 'none'}")
    print("  news items visible server-side:")
    n = 0
    for m in re.finditer(r'<a[^>]+href="(/en/news/[^"]+)"[^>]*>(.*?)</a>',
                         html, re.IGNORECASE | re.DOTALL):
        t = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if len(t) > 15:
            print(f"    - {t[:80]} -> {m.group(1)[:60]}")
            n += 1
            if n >= 10:
                break
    if not n:
        print("    none found in raw HTML (likely a JS app)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
