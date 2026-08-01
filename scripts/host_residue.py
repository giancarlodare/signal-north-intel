"""What remains unextracted at a set of hosts (operator 2026-08-01).

"Complete" has to mean complete, or say what it is complete FOR. A drain
report that states spend without stating residue lets a scoped batch look
finished when it only finished one doc_type on one host.

Read-only. Writes nothing, calls no LLM.

    python scripts/host_residue.py --hosts stcatharines.bidsandtenders.ca,...
"""
import argparse
import os
import sys
from collections import Counter
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import supabase_client as sc  # noqa: E402

TIER3 = ["stcatharines.bidsandtenders.ca", "thunderbay.bidsandtenders.ca",
         "whitby.bidsandtenders.ca", "burlington.bidsandtenders.ca"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--hosts", default=",".join(TIER3))
    args = p.parse_args()
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]

    rows = sc.fetch_all_rows_where("documents", "url,doc_type,status", {})
    print(f"documents scanned: {len(rows)}\n")
    print(f"{'host':44s} {'status':12s} {'doc_type':16s} {'n':>6s}")
    print("-" * 82)

    grand = Counter()
    for host in hosts:
        sub = [r for r in rows if urlparse(r.get("url") or "").netloc == host]
        if not sub:
            print(f"{host:44s} {'(no documents at this host)'}")
            continue
        buckets = Counter((r.get("status") or "?", r.get("doc_type") or "?") for r in sub)
        for (st, dt), n in sorted(buckets.items()):
            print(f"{host:44s} {st:12s} {dt:16s} {n:6d}")
            grand[st] += n
        print()

    print("-" * 82)
    print("ACROSS THESE HOSTS:", dict(grand))
    remaining = grand.get("captured", 0)
    print(f"\nSTILL UNEXTRACTED (status=captured): {remaining}")
    if remaining == 0:
        print("  -> these hosts are drained for EVERY doc_type.")
    else:
        print("  -> NOT complete. The counts above say for which type and host.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
