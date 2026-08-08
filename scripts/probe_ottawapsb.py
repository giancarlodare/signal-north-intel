"""Ottawa Police Services Board WordPress surface probe. Read-only, no DB.

Probes ottawapoliceboard.ca/opsb-cspo/meetings.html: robots posture, page
reachability, and document link structure. Candidate links are any anchor
whose href or text mentions minutes/agenda, or any same-host PDF link.

Operator ruling 2026-08-08: eScribe bucket C path parked (undocumented
internal endpoint). WordPress listing surface is the clean alternative;
this probe determines whether it carries collectible documents.

    python scripts/probe_ottawapsb.py
"""
import re
import sys
import time
import urllib.robotparser
import os

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from scripts.coverage_probe import UA  # noqa: E402

TIMEOUT = 20
DELAY = 1.0
HOST = "ottawapoliceboard.ca"
TARGET = f"https://www.{HOST}/opsb-cspo/meetings.html"

DOC_LINK_RE = re.compile(r"minutes|agenda", re.IGNORECASE)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)


def robots_check(session: requests.Session) -> bool:
    robots_url = f"https://www.{HOST}/robots.txt"
    try:
        r = session.get(robots_url, timeout=TIMEOUT)
        print(f"  robots.txt: HTTP {r.status_code}")
        if r.ok:
            print(f"  robots.txt body ({len(r.text)} chars):")
            print("  " + r.text[:500].replace("\n", "\n  "))
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(r.text.splitlines())
            allowed = rp.can_fetch(UA, TARGET)
            print(f"  can_fetch({TARGET!r}): {allowed}")
            return allowed
        elif 400 <= r.status_code < 500:
            print(f"  robots.txt 4xx => allow-all per RFC 9309")
            return True
        else:
            print(f"  robots.txt 5xx => treat as disallowed")
            return False
    except Exception as e:
        print(f"  robots.txt unreachable: {e}")
        return False


def probe(session: requests.Session) -> None:
    print(f"\n### Ottawa PSB WordPress probe: {TARGET}")
    print(f"\n-- robots.txt --")
    allowed = robots_check(session)
    if not allowed:
        print("ABORT: robots.txt disallows the target URL")
        return

    time.sleep(DELAY)
    print(f"\n-- page fetch --")
    try:
        r = session.get(TARGET, timeout=TIMEOUT)
        print(f"  HTTP {r.status_code}, {len(r.text)} chars")
    except Exception as e:
        print(f"  fetch failed: {type(e).__name__}: {str(e)[:120]}")
        return

    html = r.text
    from urllib.parse import urljoin, urlparse

    # Extract all links
    all_hrefs = HREF_RE.findall(html)
    all_links = [(urljoin(TARGET, h), h) for h in all_hrefs]
    host_links = [(abs_url, raw) for abs_url, raw in all_links
                  if urlparse(abs_url).netloc in (f"www.{HOST}", HOST)]

    print(f"  total href values: {len(all_hrefs)}")
    print(f"  same-host links: {len(host_links)}")

    # Document candidates: href or text says minutes/agenda, OR same-host PDF
    candidates = []
    seen = set()
    for abs_url, raw in all_links:
        if abs_url in seen:
            continue
        is_pdf = abs_url.lower().endswith(".pdf") or ".pdf?" in abs_url.lower()
        named = bool(DOC_LINK_RE.search(raw))
        if named or is_pdf:
            candidates.append((abs_url, raw))
            seen.add(abs_url)

    print(f"\n-- document candidates ({len(candidates)}) --")
    if candidates:
        for url, raw in candidates[:20]:
            print(f"  {url}")
            if raw != url:
                print(f"    (raw href: {raw[:80]})")
    else:
        print("  NONE -- no minutes/agenda/PDF links found")

    print(f"\n-- first 20 same-host links (structure sample) --")
    for url, raw in host_links[:20]:
        print(f"  {url}")

    print("\nProbe complete.")


def main() -> int:
    session = requests.Session()
    session.headers["User-Agent"] = UA
    probe(session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
