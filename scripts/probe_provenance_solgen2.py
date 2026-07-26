"""Read-only sweep (2026-07-26, operator go):

A) PROVENANCE for the 7 live bids&tenders tenants: does each city's official
site link its portal? (Fetch candidate procurement pages, grep for
bidsandtenders.) Publisher-linked provenance is the enablement requirement.
B) ArcGIS open-data candidates (Kitchener, Waterloo Region, Brampton): search
their APIs for tender/procurement datasets.
C) Host discovery for the 404'd open-data cities (Hamilton, London, Ottawa,
Mississauga): try their real open-data hosts.
D) SOLGEN round 2: real Inspectorate of Policing domain candidates + the
e-Laws static/alternate paths for the CSPA roster + allocation formula.

Robots honored, 2s politeness, read-only.
"""
import sys

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher

PROVENANCE = [
    ("niagarafalls", ["https://niagarafalls.ca/city-hall/procurement/",
                      "https://niagarafalls.ca/business/bid-opportunities.aspx"]),
    ("stcatharines", ["https://www.stcatharines.ca/en/business-and-development/bid-opportunities.aspx"]),
    ("thunderbay", ["https://www.thunderbay.ca/en/city-hall/bid-opportunities.aspx"]),
    ("whitby", ["https://www.whitby.ca/en/business-development/bids-and-tenders.aspx"]),
    ("burlington", ["https://www.burlington.ca/en/business-and-development/bids-and-tenders.aspx"]),
    ("vaughan", ["https://www.vaughan.ca/business/bids-tenders",
                 "https://www.vaughan.ca/services/business/purchasing/Pages/default.aspx"]),
    ("sarnia", ["https://www.sarnia.ca/business-development/bids-tenders/"]),
]
ARCGIS = [
    ("Kitchener", "https://open-kitchenergis.opendata.arcgis.com/api/search/v1?q=tender%20procurement%20bid"),
    ("Waterloo Region", "https://rowopendata-rmw.opendata.arcgis.com/api/search/v1?q=tender%20procurement%20bid"),
    ("Brampton", "https://geohub.brampton.ca/api/search/v1?q=tender%20procurement%20bid"),
]
HOSTS = [
    ("Hamilton", "https://open.hamilton.ca/api/search/v1?q=tender"),
    ("Hamilton ckan", "https://data.hamilton.ca/api/3/action/package_search?q=tender&rows=3"),
    ("London", "https://opendata.london.ca/api/search/v1?q=tender"),
    ("London datahub", "https://data.london.ca/api/3/action/package_search?q=tender&rows=3"),
    ("Ottawa", "https://open.ottawa.ca/api/search/v1?q=tender"),
    ("Mississauga", "https://data.mississauga.ca/api/search/v1?q=tender"),
]
SOLGEN2 = [
    ("IoP .ca", "https://inspectorateofpolicing.ca/"),
    ("IoP ontario.ca page", "https://www.ontario.ca/page/inspectorate-policing"),
    ("e-Laws CSPA plain", "https://www.ontario.ca/laws/statute/19c01?search=community+safety"),
    ("e-Laws O.Reg 392/23 v1", "https://www.ontario.ca/laws/regulation/230392/v1"),
    ("CSP grants ontario.ca search", "https://www.ontario.ca/search/search-results?query=community+safety+policing+grant+allocation"),
    ("SolGen grants page", "https://www.ontario.ca/page/safety-grants-police-services"),
]


def fetch(fetcher, url):
    if not fetcher.allowed(url):
        return "ROBOTS", ""
    try:
        r = fetcher.get(url)
    except Exception as e:
        import re as _re
        m = _re.search(r"(\d{3}) (?:Client|Server) Error", str(e))
        return (m.group(1) if m else type(e).__name__), ""
    return (str(r.status_code) if r is not None else "none"), (r.text or "") if r is not None else ""


def main():
    fetcher = PoliteFetcher()
    print("=" * 72); print("A) TENANT PROVENANCE (official site links its portal?)")
    for slug, pages in PROVENANCE:
        found = False
        for u in pages:
            st, body = fetch(fetcher, u)
            hit = "bidsandtenders" in body.lower()
            print(f"  {slug:14s} {st:6s} {u[:70]} {'-> LINKS PORTAL' if hit else ''}")
            found = found or hit
        print(f"  {slug:14s} PROVENANCE: {'PASS' if found else 'not found on candidates'}")
    print("=" * 72); print("B) ARCGIS DATASET SEARCH")
    for name, u in ARCGIS:
        st, body = fetch(fetcher, u)
        low = body.lower()
        hits = [w for w in ("tender", "procurement", "bid", "contract") if w in low]
        print(f"  {name:16s} {st} bytes={len(body)} marks={hits}")
    print("=" * 72); print("C) HOST DISCOVERY (404'd cities)")
    for name, u in HOSTS:
        st, body = fetch(fetcher, u)
        print(f"  {name:16s} {st} bytes={len(body)} json={'Y' if body.strip().startswith(('{','[')) else ''}")
    print("=" * 72); print("D) SOLGEN ROUND 2")
    for name, u in SOLGEN2:
        st, body = fetch(fetcher, u)
        low = body.lower()
        marks = [w for w in ("police service", "allocation", "formula", "grant",
                             "board") if w in low]
        print(f"  {name:28s} {st} bytes={len(body)} marks={marks}")
    print("=" * 72); print("SWEEP COMPLETE (read-only).")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    main()
    sys.exit(0)
