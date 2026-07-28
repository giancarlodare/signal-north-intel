"""Provincial public-gaps probe, pass 7 (operator 2026-07-28): three specific
checks before the provincial verdict finalizes.

  1. Supply Ontario procurement bulletins (/procurement-bulletins/ and
     /bulletins/): the July 25 pass judged them non-OPP-isolable and moved
     on; THIS pass evaluates them as a collectable public feed in their own
     right: item shape, dates, detail links, volume.
  2. OEB public tenders (oeb.ca/about-oeb/public-tenders): a provincial
     agency publishing tenders openly. If real, it evidences the pattern
     that agencies publish outside the walled OTP, so a collectable set of
     agency tender pages may exist.
  3. MERX breadth: merx.com robots welcomes crawlers and the Ottawa
     collector proves the per-buyer-page pattern; test whether provincial,
     transit, crown, and university buyers expose the same public buyer
     pages, plus the shape of the public open-solicitations search.

Read-only, robots honored, 2s politeness. CI only.
"""
import re
import sys
import time
import urllib.robotparser

import requests

UA = "SignalNorthCollector/1.0"
SLUG = re.compile(r"opportunit|tender|bid|rfp|rfq|solicitation|procurement",
                  re.IGNORECASE)


def get(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30,
                     allow_redirects=True)
    print(f"\n=== {url}\n    status={r.status_code} final={r.url[:80]} "
          f"bytes={len(r.content)}")
    return r


def robots_ok(base, path):
    try:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(requests.get(f"{base}/robots.txt",
                              headers={"User-Agent": UA},
                              timeout=20).text.splitlines())
        return rp.can_fetch(UA, base + path)
    except requests.RequestException:
        return None


def shape(html, max_links=20):
    scripts = len(re.findall(r"<script\b", html, re.IGNORECASE))
    print(f"    scripts={scripts}")
    for m in re.finditer(r"<(h[1-3])[^>]*>(.*?)</\1>", html,
                         re.IGNORECASE | re.DOTALL):
        t = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if t:
            print(f"    {m.group(1)}: {t[:84]}")
    dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2}|"
                       r"(?:January|February|March|April|May|June|July|August|"
                       r"September|October|November|December)\s+\d{1,2},?\s+20\d{2})\b",
                       html)[:8]
    print(f"    dates seen: {dates or 'none'}")
    n = 0
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html,
                         re.IGNORECASE | re.DOTALL):
        href, label = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if SLUG.search(href + " " + label) and len(label) > 3:
            print(f"      {label[:70]!r} -> {href[:90]}")
            n += 1
            if n >= max_links:
                print("      ... (truncated)")
                break
    if not n:
        print("      no opportunity-flavoured links")


def main() -> int:
    print("=" * 70 + "\n1. SUPPLY ONTARIO BULLETINS AS A FEED\n" + "=" * 70)
    for path in ("/procurement-bulletins/", "/bulletins/"):
        base = "https://www.supplyontario.ca"
        print(f"\n  robots allows {path}: {robots_ok(base, path)}")
        try:
            shape(get(base + path).text, max_links=25)
        except requests.RequestException as e:
            print(f"    fetch failed ({type(e).__name__})")
        time.sleep(2)

    print("\n" + "=" * 70 + "\n2. OEB PUBLIC TENDERS + AGENCY PATTERN\n" + "=" * 70)
    print(f"\n  robots allows /about-oeb/public-tenders: "
          f"{robots_ok('https://www.oeb.ca', '/about-oeb/public-tenders')}")
    try:
        shape(get("https://www.oeb.ca/about-oeb/public-tenders").text)
    except requests.RequestException as e:
        print(f"    fetch failed ({type(e).__name__})")
    for url in ("https://www.metrolinx.com/en/about-us/doing-business-with-metrolinx",
                "https://www.ieso.ca/en/Sector-Participants/Supply-Acquisition",
                "https://www.opg.com/suppliers/"):
        time.sleep(2)
        try:
            r = get(url)
            hits = len(SLUG.findall(r.text))
            scripts = len(re.findall(r"<script\b", r.text, re.IGNORECASE))
            print(f"    slug-hits={hits} scripts={scripts}")
        except requests.RequestException as e:
            print(f"    fetch failed ({type(e).__name__})")

    print("\n" + "=" * 70 + "\n3. MERX BREADTH (public buyer pages)\n" + "=" * 70)
    base = "https://www.merx.com"
    for slug in ("/metrolinx", "/infrastructureontario", "/lcbo",
                 "/universityoftoronto", "/cityoftoronto",
                 "/public/solicitations/open?"):
        path = slug if slug.startswith("/public") else slug
        ok = robots_ok(base, path)
        time.sleep(2)
        try:
            r = get(base + path)
            hits = len(SLUG.findall(r.text))
            scripts = len(re.findall(r"<script\b", r.text, re.IGNORECASE))
            titleish = re.search(r"<title[^>]*>(.*?)</title>", r.text,
                                 re.IGNORECASE | re.DOTALL)
            print(f"    robots={ok} slug-hits={hits} scripts={scripts} "
                  f"title={(titleish.group(1).strip()[:60] if titleish else '?')}")
        except requests.RequestException as e:
            print(f"    robots={ok} fetch failed ({type(e).__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
