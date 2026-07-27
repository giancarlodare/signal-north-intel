"""Cooperative purchasing layer probe (week-2 sprint item, pulled forward
2026-07-27 after the ten-buyer wave landed clean, per the operator's
standing condition).

READ-ONLY. For each of the eleven CPOs named across the three official
vendor-page sightings (docs/ROADMAP.md, cooperative purchasing layer):
does it publish OPPORTUNITIES and/or AWARDS publicly and collectably (no
login, robots-compatible, server-rendered)? Public-and-collectable
surfaces get a design-first proposal; walled or JS-only ones get recorded
verdicts. Robots honored, 2s politeness, no accounts, status-only reads.

    python scripts/probe_cpo_layer.py
"""
import re
import sys

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher

# (CPO, candidate public URLs). Multiple candidates per CPO because homes
# vary; the probe records every hit so the design phase picks the real one.
CPOS = [
    ("HCPG (Halton Co-op Purchasing Group)", [
        "https://www.halton.ca/the-region/finance-and-transparency/doing-business-with-the-region/halton-cooperative-purchasing-group",
        "https://hcpg.ca/",
    ]),
    ("PCPG (Police Co-op Purchasing Group)", [
        "https://pcpg.ca/",
        "https://www.pcpg.ca/",
    ]),
    ("Supply Ontario / Supply Chain Ontario", [
        "https://www.supplyontario.ca/",
        "https://www.doingbusiness.mgs.gov.on.ca/",
    ]),
    ("OECM", [
        "https://oecm.ca/",
        "https://oecm.ca/marketplace/",
        "https://oecm.ca/agreements/",
    ]),
    ("Ontario VOR directory", [
        "https://www.doingbusiness.mgs.gov.on.ca/mbs/psb/psb.nsf/English/VORDirectory",
        "https://www.ontario.ca/page/vendor-record-arrangements",
    ]),
    ("MPBSD marketplace", [
        "https://www.doingbusiness.mgs.gov.on.ca/mbs/psb/psb.nsf/english/bids-tenders",
    ]),
    ("Canoe Procurement Group", [
        "https://canoeprocurement.ca/",
        "https://canoeprocurement.ca/current-opportunities/",
    ]),
    ("Kinetic GPO", [
        "https://kineticgpo.ca/",
        "https://kineticgpo.ca/solicitations",
    ]),
    ("YPCO (York Purchasing Co-op)", [
        "https://www.york.ca/business/doing-business-york-region",
    ]),
    ("HealthPRO", [
        "https://www.healthprocanada.com/",
        "https://www.healthprocanada.com/contract-opportunities",
    ]),
    ("SGP (St. Lawrence/Great Plains?)", [
        "https://sgp.coop/",
    ]),
]

OPP_MARKS = ("bid", "tender", "rfp", "solicitation", "opportunit", "posting")
AWARD_MARKS = ("award", "contract", "vendor of record", "agreement")
WALL_MARKS = ("login", "sign in", "register", "password", "account")


def status(fetcher, url):
    if not fetcher.allowed(url):
        return "ROBOTS", 0, ""
    try:
        r = fetcher.get(url)
    except Exception as e:
        m = re.search(r"(\d{3}) (?:Client|Server) Error", str(e))
        return (m.group(1) if m else type(e).__name__), 0, ""
    if r is None:
        return "none", 0, ""
    return str(r.status_code), len(r.text or ""), (r.text or "")


def main():
    fetcher = PoliteFetcher()
    print("=" * 72)
    print("CPO LAYER PROBE (read-only; robots honored; no accounts)")
    print("=" * 72)
    for name, urls in CPOS:
        print(f"\n{name}")
        for url in urls:
            st, size, body = status(fetcher, url)
            low = body.lower()
            opp = [m for m in OPP_MARKS if m in low]
            awd = [m for m in AWARD_MARKS if m in low]
            wall = [m for m in WALL_MARKS if m in low]
            js = "JS?" if (st == "200" and size < 6000) else ""
            print(f"  {st:8s} bytes={size:<8d} opp={opp[:3]} award={awd[:3]} "
                  f"wall={wall[:2]} {js} {url[:80]}")
    print("\n" + "=" * 72)
    print("PROBE COMPLETE (read-only). Verdicts and any design-first "
          "proposals go to the operator; nothing is collected.")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    main()
    sys.exit(0)
