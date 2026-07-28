"""MERX-breadth step 1 (operator go 2026-07-28): the two OPP checks plus
buyer-slug discovery, per docs/merx-breadth-design.md.

  1. Enumerate the Infrastructure Ontario buyer page (open + awarded tabs,
     first pages) and count OPP-named items, with samples: turns "OPP
     capital flows through IO on MERX" from inference into evidence.
  2. Search the MERX public cross-buyer open list for direct OPP presence.
  3. Discover real buyer slugs from detail links on the public list (the
     LCBO/UofT guesses 404ed; slugs are discoverable, not guessable).

Read-only, robots-welcomed host (CI-verified), 2s politeness. CI only.
"""
import re
import sys
import time
from urllib.parse import quote

import requests

UA = "SignalNorthIntel/1.0"
BASE = "https://www.merx.com"
OPP = re.compile(r"\bOPP\b|Ontario Provincial Police|Provincial Police",
                 re.IGNORECASE)


def get(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    print(f"\n=== {url}\n    status={r.status_code} bytes={len(r.content)}")
    return r


def titles(html):
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"]*/solicitations/[^"]+)"[^>]*>(.*?)</a>',
                         html, re.IGNORECASE | re.DOTALL):
        t = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if len(t) > 8:
            out.append((t, m.group(1)))
    return out


def main() -> int:
    print("=" * 70 + "\n1. INFRASTRUCTURE ONTARIO BUYER PAGE, OPP CHECK\n" + "=" * 70)
    opp_hits, total = [], 0
    for tab in ("open-bids", "awarded-contracts", "closed-bids"):
        for page in (1, 2):
            time.sleep(2)
            r = get(f"{BASE}/infrastructureontario/solicitations/{tab}"
                    f"?pageNumber={page}&selectedContent=BUYER")
            if r.status_code != 200:
                break
            ts = titles(r.text)
            total += len(ts)
            print(f"    {len(ts)} solicitation links on {tab} p{page}")
            for t, u in ts[:6]:
                print(f"      - {t[:84]}")
            opp_hits += [(t, tab) for t, _ in ts if OPP.search(t)]
    print(f"\n  IO items sampled: {total}; OPP-NAMED: {len(opp_hits)}")
    for t, tab in opp_hits[:10]:
        print(f"    OPP HIT [{tab}]: {t[:90]}")

    print("\n" + "=" * 70 + "\n2. PUBLIC CROSS-BUYER LIST, DIRECT OPP CHECK\n" + "=" * 70)
    for q in ("Ontario Provincial Police", "OPP"):
        time.sleep(2)
        r = get(f"{BASE}/public/solicitations/open?keywords={quote(q)}")
        ts = titles(r.text)
        print(f"    query {q!r}: {len(ts)} solicitation links")
        for t, u in ts[:8]:
            print(f"      - {t[:80]}")

    print("\n" + "=" * 70 + "\n3. BUYER-SLUG DISCOVERY (public open list)\n" + "=" * 70)
    time.sleep(2)
    r = get(f"{BASE}/public/solicitations/open")
    slugs = sorted(set(re.findall(
        r'href="/((?!public|solicitations|login|signup|en|fr)[a-z0-9-]{3,40})(?:/|")',
        r.text)))
    print(f"    candidate buyer slugs on page: {slugs[:40]}")
    ont = [s for s in slugs if any(k in s for k in
           ("ontario", "toronto", "metrolinx", "oeb", "lcbo", "university",
            "college", "hydro", "police", "region", "city"))]
    print(f"    Ontario-flavoured: {ont}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
