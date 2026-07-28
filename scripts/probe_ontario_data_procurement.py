"""Provincial coverage probe, pass 5 (operator 2026-07-28): the surfaces the
closed OPP probe never checked, honoring every standing wall.

The 2026-07-25 final verdict stands: OTP /esop is robots-disallowed (never
scraped around) and Supply Ontario is category-level only. This pass probes:
  1. data.ontario.ca (Ontario Data Catalogue, CKAN): search for procurement,
     tender, contract, and vendor-of-record DATASETS. Structured open data is
     the Toronto pattern and the strongest legal surface if it exists.
  2. Robots drift recheck on the walled hosts (postures change; if the wall
     is gone the design doc's revive clause fires).

Read-only. CI only (sandbox blocks external hosts).
"""
import json
import sys
import time
import urllib.robotparser

import requests

UA = "SignalNorthCollector/1.0"
CKAN = "https://data.ontario.ca/api/3/action/package_search"


def get(url, **kw):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30, **kw)
    print(f"\n=== {url}\n    status={r.status_code} bytes={len(r.content)}")
    return r


def main() -> int:
    for q in ("procurement", "tender", "contract awards",
              "vendor of record", "solicitation"):
        r = get(CKAN, params={"q": q, "rows": 8})
        try:
            data = r.json()["result"]
        except (ValueError, KeyError):
            print("    NOT CKAN-JSON; catalogue shape changed")
            continue
        print(f"    query {q!r}: {data['count']} datasets")
        for pkg in data["results"]:
            org = (pkg.get("organization") or {}).get("title", "?")
            fmts = sorted({(res.get("format") or "?").upper()
                           for res in pkg.get("resources", [])})
            print(f"      - {pkg.get('title', '?')[:70]} | {org[:34]} | "
                  f"{'/'.join(fmts)} | modified {str(pkg.get('metadata_modified'))[:10]}")
        time.sleep(2)

    print("\n--- robots drift recheck (walled hosts, read robots.txt only) ---")
    for base, path in (("https://ontariotenders.app.jaggaer.com", "/esop/"),
                       ("https://doingbusiness.mgs.gov.on.ca", "/")):
        try:
            r = get(f"{base}/robots.txt")
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(r.text.splitlines())
            print(f"    can_fetch {base}{path}: {rp.can_fetch(UA, base + path)}")
        except requests.RequestException as e:
            print(f"    {base}: fetch failed ({type(e).__name__})")
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
