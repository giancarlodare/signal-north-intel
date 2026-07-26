"""Read-only sweep for three fronts in one run (2026-07-26):

FRONT 4: full-Ontario bids&tenders tenant enumeration ({slug}.bidsandtenders.ca
status per candidate municipality) -> the enablement-ready table's raw input.
FRONT 5: MERX buyer-slug sweep (merx.com/{slug}) + {city} open-data endpoint
sweep on the Windsor/Toronto pattern (CKAN package_search for bids/tenders).
SOLGEN: CSPA roster + CSP local-priorities allocation-formula hunt
(Inspectorate of Policing, CSPA regulations, grant guideline pages).

Robots honored, 2s politeness, status-only checks (no accounts, no scraping).

    python scripts/probe_front45_solgen.py
"""
import re
import sys

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher

BT = [  # bids&tenders tenant candidates (tier-2 known ones excluded; sweep adds)
    "hamilton", "ottawa", "london", "windsor", "kitchener", "cambridge",
    "guelph", "kingston", "barrie", "brantford", "niagarafalls", "stcatharines",
    "thunderbay", "sudbury", "oshawa", "whitby", "ajax", "pickering",
    "burlington", "oakville", "miltonon", "newmarket", "aurora", "vaughan",
    "richmondhill", "markham", "cityofwaterloo", "stratford", "sarnia",
    "chathamkent", "northbay", "peterborough", "belleville", "cornwall",
]
MERX = ["cityofhamilton", "cityoflondon", "cityofkitchener", "cityofguelph",
        "cityofkingston", "cityofbarrie", "cityofwindsor",
        "cityofgreatersudbury", "cityofthunderbay", "regionofpeel",
        "yorkregion", "regionofdurham", "cityofvaughan", "cityofmarkham"]
OPENDATA = [
    ("Hamilton", "https://open.hamilton.ca/api/3/action/package_search?q=tender&rows=3"),
    ("London", "https://opendata.london.ca/api/3/action/package_search?q=tender&rows=3"),
    ("Ottawa", "https://open.ottawa.ca/api/3/action/package_search?q=tender&rows=3"),
    ("Kitchener", "https://open-kitchenergis.opendata.arcgis.com/api/search/v1?q=tender"),
    ("Waterloo Region", "https://rowopendata-rmw.opendata.arcgis.com/api/search/v1?q=tender"),
    ("Mississauga", "https://data.mississauga.ca/api/3/action/package_search?q=tender&rows=3"),
    ("Brampton", "https://geohub.brampton.ca/api/search/v1?q=tender"),
]
SOLGEN = [
    ("Inspectorate of Policing", "https://www.inspectorateofpolicing.ca/"),
    ("IoP policing directory", "https://www.inspectorateofpolicing.ca/police-service-boards/"),
    ("CSPA O.Reg 392/23", "https://www.ontario.ca/laws/regulation/230392"),
    ("CSPA 2019 statute", "https://www.ontario.ca/laws/statute/19c01"),
    ("CSP grant page", "https://www.ontario.ca/page/community-safety-and-policing-grant"),
    ("CSP grant guidelines", "https://www.ontario.ca/document/community-safety-and-policing-grant-guidelines"),
]


def status(fetcher, url):
    if not fetcher.allowed(url):
        return "ROBOTS-DISALLOWED", 0, ""
    try:
        r = fetcher.get(url)
    except Exception as e:
        m = re.search(r"(\d{3}) (?:Client|Server) Error", str(e))
        return (m.group(1) if m else type(e).__name__), 0, ""
    if r is None:
        return "none", 0, ""
    return str(r.status_code), len(r.text or ""), (r.text or "")[:400]


def main():
    fetcher = PoliteFetcher()
    print("=" * 72); print("FRONT 4: bids&tenders tenants")
    for slug in BT:
        st, size, _ = status(fetcher, f"https://{slug}.bidsandtenders.ca/Module/Tenders/en")
        if st == "200":
            print(f"  TENANT {slug:16s} 200 bytes={size}")
        else:
            print(f"  -      {slug:16s} {st}")
    print("=" * 72); print("FRONT 5a: MERX buyer slugs")
    for slug in MERX:
        st, size, body = status(fetcher, f"https://www.merx.com/{slug}/solicitations/open-bids?pageNumber=1&selectedContent=BUYER")
        mark = "BUYER" if (st == "200" and "solicitation" in body.lower()) else ("200?" if st == "200" else st)
        print(f"  {slug:22s} {mark} bytes={size}")
    print("=" * 72); print("FRONT 5b: open-data endpoints")
    for name, url in OPENDATA:
        st, size, body = status(fetcher, url)
        hint = "JSON" if body.strip().startswith("{") else ""
        print(f"  {name:16s} {st} bytes={size} {hint}")
    print("=" * 72); print("SOLGEN: CSPA roster + formula hunt")
    for name, url in SOLGEN:
        st, size, body = status(fetcher, url)
        low = body.lower()
        marks = [w for w in ("police service", "board", "grant", "allocation",
                             "formula") if w in low]
        print(f"  {name:26s} {st} bytes={size} marks={marks}")
    print("=" * 72); print("SWEEP COMPLETE (read-only).")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    main()
    sys.exit(0)
