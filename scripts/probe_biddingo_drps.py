"""Biddingo/DRPS step-1 probe (operator go 2026-07-28): robots + structure.

Provenance is settled (drps.ca names Biddingo as its posting channel;
operator browser 2026-07-20 saw 38 public bids with DRPS-2026-002-style
references and Awarded/Closed statuses). Robots is NEVER assumed: this
script prints biddingo.com robots.txt VERBATIM, evaluates can_fetch for
/m/drps, and renders NOTHING unless robots permits. The page is a JS shell
to plain requests, so the structure pass uses the house Playwright stack
(the daily-tenders pattern) only after the robots gate passes.

Read-only, 2s politeness. CI only.
"""
import re
import sys
import time
import urllib.robotparser

import requests

UA = "SignalNorthCollector/1.0"
BASE = "https://www.biddingo.com"
PAGE = f"{BASE}/m/drps"
REF = re.compile(r"\bDRPS-?\d{2,4}-\d{2,4}\b", re.IGNORECASE)
STATUS = re.compile(r"\b(Open|Closed|Awarded|Cancelled)\b")


def main() -> int:
    r = requests.get(f"{BASE}/robots.txt", headers={"User-Agent": UA},
                     timeout=30)
    print(f"=== {BASE}/robots.txt\n    status={r.status_code} "
          f"bytes={len(r.content)}\n--- VERBATIM ---")
    print(r.text[:2000])
    print("--- END ---")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(r.text.splitlines())
    ok = rp.can_fetch(UA, PAGE)
    star = rp.can_fetch("*", PAGE)
    print(f"    can_fetch(/m/drps): UA={ok} wildcard={star}")
    if not ok:
        print("\nVERDICT: robots disallows /m/drps. Nothing rendered; the "
              "source stays human-research-only and the adapter build stops "
              "here honestly.")
        return 0

    print("\nrobots permits; rendering with the house Playwright stack...")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120 Safari/537.36"))
        page.goto(PAGE, wait_until="networkidle", timeout=60000)
        time.sleep(2)
        html = page.content()
        text = page.inner_text("body")
        print(f"    rendered: {len(html)} chars html, {len(text)} chars text")

        refs = sorted(set(REF.findall(text)))
        print(f"    DRPS references visible: {len(refs)}")
        for x in refs[:12]:
            print(f"      {x}")
        statuses = sorted(set(STATUS.findall(text)))
        print(f"    statuses visible: {statuses}")

        rows = page.locator("table tr, [role=row]").count()
        print(f"    table/grid rows: {rows}")
        print("\n    sample row text:")
        for i in range(min(rows, 10)):
            t = page.locator("table tr, [role=row]").nth(i).inner_text()
            t = " | ".join(s.strip() for s in t.splitlines() if s.strip())
            if len(t) > 10:
                print(f"      {t[:130]}")

        links = sorted(set(re.findall(r'href="([^"]*(?:bid|opportunity|detail|doc)[^"]*)"',
                                      html, re.IGNORECASE)))[:12]
        print(f"\n    detail-ish links: ")
        for l in links:
            print(f"      {l[:110]}")
        pager = page.locator("text=/next|›|page/i").count()
        print(f"    pagination markers: {pager}")

        dates = re.findall(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", text)[:10]
        print(f"    dates visible: {dates}")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
