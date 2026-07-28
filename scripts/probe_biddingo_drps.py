"""Biddingo/DRPS step-1 probe, re-run under the renamed UA (operator go
2026-07-28): robots + structure, deepened for the adapter build.

Provenance is settled (drps.ca names Biddingo as its posting channel;
operator browser 2026-07-20 saw 38 public bids with DRPS-2026-002-style
references and Awarded/Closed statuses). Robots is NEVER assumed: this
script prints biddingo.com robots.txt VERBATIM, evaluates can_fetch for
/m/drps under SignalNorthIntel/1.0 (renamed from SignalNorthCollector/1.0,
whose "Collector" token falsely matched a banned-tool group aimed at a
different product), and renders NOTHING unless robots permits.

Structure pass (only after the robots gate): renders /m/drps with the house
Playwright stack under our HONEST UA first — if the grid only populates
under a browser UA we need to know that now (the bids&tenders silent-empty
lesson), and it is reported loudly either way. While rendering, every
JSON/XHR response is recorded so the adapter can read the grid's actual
data channel instead of scraping the DOM if one exists.

Read-only, 2s politeness. CI only.
"""
import json
import re
import sys
import time
import urllib.robotparser

import requests

UA = "SignalNorthIntel/1.0"
BASE = "https://www.biddingo.com"
PAGE = f"{BASE}/m/drps"
REF = re.compile(r"\bDRPS-?\d{2,4}-\d{2,4}\b", re.IGNORECASE)
STATUS = re.compile(r"\b(Open|Closed|Awarded|Cancelled)\b")


def render_and_report(p, user_agent: str, label: str) -> dict:
    """Render PAGE under user_agent; print structure; return summary."""
    browser = p.chromium.launch()
    page = browser.new_page(user_agent=user_agent)

    xhr: list = []

    def on_response(resp):
        ct = (resp.headers.get("content-type") or "").lower()
        if "json" not in ct:
            return
        try:
            body = resp.text()
        except Exception:
            return
        xhr.append({"url": resp.url, "status": resp.status,
                    "bytes": len(body), "body": body[:3000]})

    page.on("response", on_response)
    page.goto(PAGE, wait_until="networkidle", timeout=60000)
    time.sleep(2)
    html = page.content()
    text = page.inner_text("body")
    print(f"\n=== RENDER [{label}] UA={user_agent[:60]}")
    print(f"    rendered: {len(html)} chars html, {len(text)} chars text")

    refs = sorted(set(REF.findall(text)))
    print(f"    DRPS references visible: {len(refs)}")
    for x in refs[:12]:
        print(f"      {x}")
    statuses = sorted(set(STATUS.findall(text)))
    print(f"    statuses visible: {statuses}")

    rows = page.locator("table tr, [role=row]").count()
    print(f"    table/grid rows: {rows}")
    print("    sample row text:")
    for i in range(min(rows, 10)):
        t = page.locator("table tr, [role=row]").nth(i).inner_text()
        t = " | ".join(s.strip() for s in t.splitlines() if s.strip())
        if len(t) > 10:
            print(f"      {t[:150]}")

    links = sorted(set(re.findall(
        r'href="([^"]*(?:bid|opportunity|detail|doc)[^"]*)"',
        html, re.IGNORECASE)))[:12]
    print("    detail-ish links:")
    for l in links:
        print(f"      {l[:120]}")
    pager = page.locator("text=/next|›|page/i").count()
    print(f"    pagination markers: {pager}")
    dates = re.findall(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", text)[:10]
    print(f"    dates visible: {dates}")

    print(f"    JSON/XHR responses captured: {len(xhr)}")
    for x in xhr[:8]:
        print(f"      {x['status']} {x['bytes']:>8}B  {x['url'][:120]}")
        try:
            data = json.loads(x["body"])
            if isinstance(data, dict):
                print(f"        keys: {sorted(data.keys())[:12]}")
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                print(f"        list[{len(data)}], row keys: "
                      f"{sorted(data[0].keys())[:14]}")
        except Exception:
            snippet = x["body"][:160].replace("\n", " ")
            print(f"        (truncated/unparsed) {snippet}")
    browser.close()
    return {"refs": len(refs), "rows": rows, "text": len(text),
            "xhr": len(xhr)}


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
    old = rp.can_fetch("SignalNorthCollector/1.0", PAGE)
    print(f"    can_fetch(/m/drps): SignalNorthIntel={ok} wildcard={star} "
          f"old-Collector-name={old}")
    if not ok:
        print("\nVERDICT: robots disallows /m/drps for SignalNorthIntel. "
              "Nothing rendered; the source stays human-research-only and "
              "the adapter build stops here honestly.")
        return 0

    print("\nrobots permits SignalNorthIntel; rendering with the house "
          "Playwright stack under the honest UA...")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        honest = render_and_report(p, UA, "honest UA")
        if honest["refs"] == 0 and honest["rows"] <= 1:
            print("\n    grid EMPTY under the honest UA — re-rendering with "
                  "a browser UA to see whether Biddingo UA-gates content "
                  "(the bids&tenders silent-empty pattern). This is a "
                  "diagnostic render, not a collection posture decision.")
            time.sleep(2)
            browser_ua = ("Mozilla/5.0 (X11; Linux x86_64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120 Safari/537.36")
            render_and_report(p, browser_ua, "browser UA diagnostic")
    return 0


if __name__ == "__main__":
    sys.exit(main())
