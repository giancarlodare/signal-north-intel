"""Supply Ontario pass 6 (operator 2026-07-28): before "provincial is a
dead zone" closes as a disclosed boundary, confirm it is genuinely walled
and not a surface we missed. The operator has a nagging memory of live
opportunities on a Supply Ontario / provincial site.

Genuinely new in this pass (everything else was probed in passes 1-5 and
the CPO-layer probe):
  1. supplyontario.ca robots + FULL sitemap enumeration, grepping every
     URL for opportunity/tender/bid/rfp/solicitation slugs.
  2. A fresh fetch of /opportunities/ and any sitemap-discovered candidate
     pages: server-side vs JS, live listings vs navigation stubs, and
     whether items name a buyer.
  3. OECM marketplace and Kinetic GPO solicitations recheck (the group
     purchasing surfaces the memory could be from), verdict lines only.

Read-only, robots honored, 2s politeness. CI only.
"""
import re
import sys
import time
import urllib.robotparser

import requests

UA = "SignalNorthIntel/1.0"
SLUG = re.compile(r"opportunit|tender|bid|rfp|solicitation|procurement",
                  re.IGNORECASE)


def get(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    print(f"\n=== {url}\n    status={r.status_code} "
          f"type={r.headers.get('content-type', '?')[:36]} bytes={len(r.content)}")
    return r


def page_shape(html: str) -> None:
    scripts = len(re.findall(r"<script\b", html, re.IGNORECASE))
    text = re.sub(r"<script.*?</script>|<[^>]+>", " ", html,
                  flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    print(f"    scripts={scripts} visible-text-chars={len(text)}")
    print("\n    headings:")
    for m in re.finditer(r"<(h[1-3])[^>]*>(.*?)</\1>", html,
                         re.IGNORECASE | re.DOTALL):
        t = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if t:
            print(f"      {m.group(1)}: {t[:80]}")
    print("\n    opportunity-flavoured links:")
    n = 0
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html,
                         re.IGNORECASE | re.DOTALL):
        href, label = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if SLUG.search(href + " " + label):
            print(f"      {label[:56]!r} -> {href[:96]}")
            n += 1
            if n >= 25:
                print("      ... (truncated)")
                break
    if not n:
        print("      none")


def main() -> int:
    base = "https://www.supplyontario.ca"
    rp = urllib.robotparser.RobotFileParser()
    r = get(f"{base}/robots.txt")
    rp.parse(r.text.splitlines())
    print(f"    robots allows /opportunities/: "
          f"{rp.can_fetch(UA, base + '/opportunities/')}")
    sitemaps = re.findall(r"(?im)^sitemap:\s*(\S+)", r.text) or \
        [f"{base}/sitemap.xml", f"{base}/sitemap_index.xml",
         f"{base}/wp-sitemap.xml"]

    seen_urls = []
    for sm in sitemaps[:6]:
        time.sleep(2)
        try:
            r = get(sm)
        except requests.RequestException as e:
            print(f"    fetch failed ({type(e).__name__})")
            continue
        if r.status_code != 200:
            continue
        locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", r.text)
        print(f"    {len(locs)} <loc> entries")
        for loc in locs:
            if loc.endswith(".xml") and len(sitemaps) < 24:
                sitemaps.append(loc)   # sitemap index: walk children
            elif SLUG.search(loc):
                seen_urls.append(loc)
    print(f"\n  sitemap URLs with opportunity/tender/bid slugs "
          f"({len(seen_urls)}):")
    for u in sorted(set(seen_urls))[:30]:
        print(f"    {u}")

    candidates = [f"{base}/opportunities/"] + sorted(set(seen_urls))[:5]
    for url in candidates:
        if not rp.can_fetch(UA, url):
            print(f"\n=== {url}\n    robots-disallowed; skipping")
            continue
        time.sleep(2)
        try:
            page_shape(get(url).text)
        except requests.RequestException as e:
            print(f"    fetch failed ({type(e).__name__})")

    print("\n--- group-purchasing rechecks (verdict lines) ---")
    for url in ("https://oecm.ca/marketplace/",
                "https://kineticgpo.ca/solicitations"):
        time.sleep(2)
        try:
            r = get(url)
            hits = len(SLUG.findall(r.text))
            scripts = len(re.findall(r"<script\b", r.text, re.IGNORECASE))
            print(f"    slug-hits={hits} scripts={scripts} "
                  f"(server-side listings likely: {hits > 20 and scripts < 30})")
        except requests.RequestException as e:
            print(f"    fetch failed ({type(e).__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
