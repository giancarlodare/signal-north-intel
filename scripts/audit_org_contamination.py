"""Corpus-wide cross-buyer org-resolution contamination audit (operator
2026-07-27, escalated from the R3 pilot finding: a WRPS/Waterloo document's
signal was attributed to Peel).

CORRECTNESS GAP per the client-facing gate (docs/client-facing-gate.md): a
signal resolved to the WRONG buyer is a factually-wrong item that can pass
every confidence check. If it bled into R3 it likely bled elsewhere
invisibly, so this audits the WHOLE corpus before anything from the pilot
goes client-facing.

READ-ONLY. Detection: each signal's document is PUBLISHED on some host. A
publisher host maps to exactly one buyer (tpsb.ca -> Toronto Police Service
Board, wrps-public -> Waterloo, ...). If a signal's resolved organization is
buyer A but its document host belongs to buyer B, that is a contamination.
Precise and low-false-positive: it fires only when the host unambiguously
names a DIFFERENT known buyer than the resolved org.

    python scripts/audit_org_contamination.py
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import supabase_client

# Publisher-host token -> canonical buyer the host belongs to. A host that
# names one of these tokens is published BY that buyer, so a signal on that
# document must resolve to that buyer (or to a non-conflicting rollup like a
# city/region). Kept conservative: only unambiguous, single-owner hosts.
HOST_OWNER = {
    "tpsb.ca": "Toronto Police Service Board",
    "peelpoliceboard.ca": "Peel Police Service Board",
    "peelregion": "Region of Peel",
    "yrpsb.ca": "York Regional Police Services Board",
    "yrp.ca": "York Regional Police",
    "durhampoliceboard.ca": "Durham Regional Police Services Board",
    "drps.ca": "Durham Regional Police Service",
    "haltonpoliceboard.ca": "Halton Police Board",
    "hrps.on.ca": "Halton Regional Police Service",
    "wrps": "Waterloo Regional Police Service",
    "gsps.ca": "Greater Sudbury Police Service",
    "open.toronto.ca": "City of Toronto",
    "toronto.ca": "City of Toronto",
    "hamilton.bidsandtenders": "City of Hamilton",
    "brampton.bidsandtenders": "City of Brampton",
    "kitchener.bidsandtenders": "City of Kitchener",
    "vaughan.bidsandtenders": "City of Vaughan",
    "haltonregion.bidsandtenders": "Halton Region",
}

# Buyers that legitimately share a host family (a board and its service, a
# police service and its region): a host owned by one must not be flagged as
# contaminating the other. Group by the real-world entity cluster.
COMPATIBLE = [
    {"Toronto Police Service Board", "Toronto Police Service", "City of Toronto"},
    {"Peel Police Service Board", "Peel Regional Police", "Region of Peel"},
    {"York Regional Police Services Board", "York Regional Police", "York Region"},
    {"Durham Regional Police Services Board", "Durham Regional Police Service",
     "Region of Durham"},
    {"Halton Police Board", "Halton Regional Police Service", "Halton Region"},
    {"Waterloo Regional Police Services Board", "Waterloo Regional Police Service"},
    {"Greater Sudbury Police Services Board", "Greater Sudbury Police Service"},
]


def _one(embedded):
    if isinstance(embedded, list):
        return embedded[0] if embedded else None
    return embedded


def compatible(a: str, b: str) -> bool:
    if a == b:
        return True
    for grp in COMPATIBLE:
        if a in grp and b in grp:
            return True
    return False


def host_owner(url: str) -> str | None:
    low = (url or "").lower()
    for token, owner in HOST_OWNER.items():
        if token in low:
            return owner
    return None


def main() -> int:
    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,title,organization_id,organizations(canonical_name),"
        "documents(url)",
        {"organization_id": "not.is.null"})
    print(f"AUDIT: {len(signals)} org-resolved signals scanned")

    contaminated = []
    by_pair = Counter()
    unmapped_hosts = 0
    for s in signals:
        org = (_one(s.get("organizations")) or {}).get("canonical_name")
        doc = _one(s.get("documents")) or {}
        owner = host_owner(doc.get("url"))
        if not owner:
            unmapped_hosts += 1
            continue
        if org and not compatible(org, owner):
            contaminated.append({
                "signal_id": s["id"],
                "title": (s.get("title") or "")[:80],
                "resolved_org": org,
                "host_owner": owner,
                "url": (doc.get("url") or "")[:90],
            })
            by_pair[(org, owner)] += 1

    print(f"  host-mapped signals: {len(signals) - unmapped_hosts}; "
          f"host-unmapped (not audited): {unmapped_hosts}")
    print(f"\nCONTAMINATION FOUND: {len(contaminated)} signals")
    if by_pair:
        print("\nBy (resolved_org -> true host owner):")
        for (org, owner), n in by_pair.most_common():
            print(f"  {n:4d}  resolved={org!r}  but published by {owner!r}")
    print("\nSAMPLES (up to 25):")
    for c in contaminated[:25]:
        print(f"  [{c['resolved_org']} != {c['host_owner']}] {c['title']}")
        print(f"       {c['url']}  sig={c['signal_id']}")

    # Machine-readable line for the fix step to consume.
    ids = [c["signal_id"] for c in contaminated]
    print(f"\nCONTAMINATED_SIGNAL_IDS={','.join(ids)}")
    print(f"\nVERDICT: {'CLEAN' if not contaminated else str(len(contaminated)) + ' contaminated signals need re-resolution'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
