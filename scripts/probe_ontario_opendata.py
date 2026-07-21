"""PROBE (probe/ontario-opendata branch only, never merged): does Ontario's
open data catalogue publish an OTP / tender / procurement dataset?

Rationale (ROADMAP OPP entry): the Ontario Tenders Portal is Jaggaer-hosted
with robots disallowing /esop entirely, so publisher open data is the only
automation-compatible route to provincial procurement including OPP, the
same shape as the Windsor open-data find. data.ontario.ca is CKAN, so this
searches the package API and characterizes any hits. Read-only, robots
respected, 2s shared delay, no accounts.
"""
import re
import sys
from urllib.parse import quote

sys.path.insert(0, ".")

from src.board_minutes import PoliteFetcher

BASE = "https://data.ontario.ca"
QUERIES = ["tender", "tenders portal", "procurement", "solicitation",
           "contract award", "vendor of record", "bids",
           "provincial police", "OPP"]
# A package is worth a detail look when its title smells like procurement.
RELEVANT = re.compile(r"tender|procure|solicit|contract|award|vendor|bid|police",
                      re.IGNORECASE)

fetcher = PoliteFetcher()
packages: dict[str, dict] = {}

print("=" * 70)
print("1. PACKAGE SEARCH")
print("=" * 70)
for q in QUERIES:
    url = f"{BASE}/api/3/action/package_search?q={quote(q)}&rows=15"
    r = fetcher.get(url)
    if r is None:
        print(f"[{q}] robots disallow / unreachable")
        continue
    doc = r.json()
    result = doc.get("result") or {}
    count = result.get("count")
    print(f"[{q}] {count} package(s)")
    for pkg in result.get("results") or []:
        name = pkg.get("name")
        if name and name not in packages:
            org = ((pkg.get("organization") or {}).get("title")) or "?"
            packages[name] = {
                "title": pkg.get("title"),
                "org": org,
                "formats": sorted({(res.get("format") or "?").upper()
                                   for res in pkg.get("resources") or []}),
                "n_res": len(pkg.get("resources") or []),
                "modified": pkg.get("metadata_modified"),
                "frequency": pkg.get("update_frequency") or pkg.get("frequency"),
            }

print("=" * 70)
print("2. UNIQUE PACKAGES SEEN")
print("=" * 70)
relevant = []
for name, p in sorted(packages.items()):
    tag = ""
    if RELEVANT.search(p["title"] or "") or RELEVANT.search(name):
        tag = "  <== RELEVANT"
        relevant.append(name)
    print(f"- {name} :: {p['title']!r} [{p['org']}] "
          f"res={p['n_res']} {p['formats']} mod={p['modified']} "
          f"freq={p['frequency']}{tag}")

print("=" * 70)
print("3. DETAIL ON RELEVANT PACKAGES (resources + urls)")
print("=" * 70)
for name in relevant[:10]:
    url = f"{BASE}/api/3/action/package_show?id={quote(name)}"
    r = fetcher.get(url)
    if r is None:
        print(f"[{name}] robots disallow / unreachable")
        continue
    pkg = (r.json().get("result")) or {}
    notes = " ".join((pkg.get("notes") or "").split())
    print(f"[{name}] {pkg.get('title')!r}")
    print(f"  org={((pkg.get('organization') or {}).get('title'))} "
          f"freq={pkg.get('update_frequency')} "
          f"modified={pkg.get('metadata_modified')}")
    print(f"  notes: {notes[:400]!r}")
    for res in (pkg.get("resources") or [])[:8]:
        print(f"  RES {res.get('format')}: {res.get('name')!r} "
              f"last_modified={res.get('last_modified')} url={res.get('url')}")
print("done")
