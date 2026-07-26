"""Read-only probe: find the authoritative CSPA police-services roster (the
Tier-1 denominator) and isolate the CSP LOCAL-priorities recipients from the
grant-recipient ledger, so the forfeited-allocation absentee list can be built.

Robots honored, 2s politeness, no accounts.

    python scripts/probe_cspa_roster.py
"""
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher

# Candidate CSPA / Inspectorate-of-Policing / police-services-list pages.
ROSTER_CANDIDATES = [
    "https://www.ontario.ca/page/police-services-ontario",
    "https://www.ontario.ca/page/list-of-police-services",
    "https://www.ontario.ca/page/policing-services-ontario",
    "https://www.ontario.ca/page/inspectorate-of-policing",
    "https://www.ontario.ca/page/community-safety-and-policing-act-2019",
    "https://www.ontario.ca/page/contact-police-service",
    "https://www.oiprd.on.ca/police-services/",
]
RECIP_PAGE = "https://www.ontario.ca/page/current-community-safety-project-grant-recipients"
SVC_MARK = ["police service", "police services", "regional police", "police board"]


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.cur_h = [], ""
        self._h = self._buf = self._row = self._tbl = None
        self._incell = False

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4"):
            self._h = []
        elif tag == "table":
            self._tbl = {"heading": self.cur_h, "rows": []}
        elif tag == "tr" and self._tbl is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._buf, self._incell = [], True

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4") and self._h is not None:
            self.cur_h = " ".join("".join(self._h).split())[:90]
            self._h = None
        elif tag in ("td", "th") and self._incell:
            self._row.append(" ".join("".join(self._buf).split()))
            self._incell = False
        elif tag == "tr" and self._row is not None:
            if any(c.strip() for c in self._row):
                self._tbl["rows"].append(self._row)
            self._row = None
        elif tag == "table" and self._tbl is not None:
            self.tables.append(self._tbl)
            self._tbl = None

    def handle_data(self, data):
        if self._incell:
            self._buf.append(data)
        elif self._h is not None:
            self._h.append(data)


def _get(fetcher, url):
    if not fetcher.allowed(url):
        print(f"  robots DISALLOWED: {url}")
        return None
    try:
        return fetcher.get(url)
    except Exception as e:
        print(f"  {url} -> {type(e).__name__}: {str(e)[:90]}")
        return None


def main():
    fetcher = PoliteFetcher()
    print("=" * 74)
    print("CSPA POLICE-SERVICES ROSTER candidates")
    for u in ROSTER_CANDIDATES:
        r = _get(fetcher, u)
        if r is None:
            continue
        html = r.text or ""
        svc = sum(html.lower().count(m) for m in SVC_MARK)
        print(f"  200 {u}\n      bytes={len(html)} police-service-mentions={svc}")

    print("=" * 74)
    print("CSP LOCAL-priorities recipients (isolated from the ledger)")
    r = _get(fetcher, RECIP_PAGE)
    if r is not None:
        p = Tables()
        p.feed(r.text or "")
        print(f"  ledger tables={len(p.tables)}; headings:")
        for t in p.tables:
            print(f"    - {t['heading']!r}  rows={len(t['rows'])}")
        local = [t for t in p.tables if "local" in t["heading"].lower()
                 and "priorit" in t["heading"].lower()]
        for t in local:
            names = sorted({row[0] for row in t["rows"][1:]
                            if row and row[0] and "total" not in row[0].lower()})
            print(f"  LOCAL-PRIORITIES table {t['heading']!r}: "
                  f"{len(names)} distinct recipient strings")
            for n in names:
                print(f"      {n}")
    print("=" * 74)
    print("PROBE COMPLETE (read-only).")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
    sys.exit(0)
