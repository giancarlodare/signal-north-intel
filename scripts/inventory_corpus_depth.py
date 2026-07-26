"""Corpus depth inventory (read-only): the COLLECTED/EXTRACTED side of the
backward-reconstruction gap report (docs/demand-arc-backtest-design.md 0c).

Per doc_type and per service (url/buyer marker): document count, date reach
(min/max published_on), and status breakdown (captured vs extracted vs
failed). The gap report compares this against each source's ARCHIVE reach
(known from collector listing counts and probes) to show where deepening buys
arc history.

    python scripts/inventory_corpus_depth.py
"""
import sys
from collections import defaultdict

sys.path.insert(0, ".")

from src import supabase_client

# Service / entity -> corpus markers (url substring or buyer_name).
SERVICES = [
    ("Toronto (city procurement)", "buyer", "City of Toronto"),
    ("Ottawa (MERX)", "buyer", "City of Ottawa"),
    ("Windsor (open data)", "buyer", "City of Windsor"),
    ("Peel (tenders+awarded)", "buyer", "Region of Peel"),
    ("TPSB", "url", "tpsb.ca"),
    ("Peel Police Board", "url", "peelpoliceboard.ca"),
    ("York Police Board", "url", "yrpsb.ca"),
    ("Durham Police Board", "url", "durhampoliceboard.ca"),
    ("Halton Police Board", "url", "haltonpoliceboard.ca"),
    ("Waterloo Police Board", "url", "wrps"),
    ("Sudbury Police Board", "url", "gsps.ca"),
    ("Infrastructure Ontario", "url", "infrastructureontario.ca"),
]


def fetch_group(filters: dict) -> list:
    return supabase_client.fetch_all_rows_where(
        "documents", "doc_type,status,published_on", filters)


def summarize(rows: list) -> dict:
    out = defaultdict(lambda: {"n": 0, "min": None, "max": None,
                               "captured": 0, "extracted": 0, "failed": 0})
    for r in rows:
        d = out[r.get("doc_type") or "?"]
        d["n"] += 1
        st = r.get("status") or "?"
        if st in d:
            d[st] += 1
        p = (r.get("published_on") or "")[:10] or None
        if p:
            d["min"] = p if d["min"] is None or p < d["min"] else d["min"]
            d["max"] = p if d["max"] is None or p > d["max"] else d["max"]
    return dict(out)


def main():
    print("=" * 78)
    print("CORPUS DEPTH INVENTORY (collected + extracted side of the gap report)")
    print("=" * 78)
    for label, kind, marker in SERVICES:
        filters = ({"buyer_name": f"eq.{marker}"} if kind == "buyer"
                   else {"url": f"ilike.*{marker}*"})
        rows = fetch_group(filters)
        print(f"\n{label}  (marker: {marker}; total docs {len(rows)})")
        for dt, d in sorted(summarize(rows).items()):
            print(f"  {dt:20s} n={d['n']:<6d} reach={d['min']}..{d['max']}  "
                  f"captured={d['captured']} extracted={d['extracted']} "
                  f"failed={d['failed']}")
    # Global signals view: how much of the corpus has become arc fuel.
    sigs = supabase_client.fetch_all_rows_where(
        "signals", "evidence_grade", {"evidence_grade": "not.is.null"})
    grades = defaultdict(int)
    for s in sigs:
        grades[s["evidence_grade"]] += 1
    print("\n" + "=" * 78)
    print(f"SIGNALS by evidence_grade (arc fuel): {dict(sorted(grades.items()))}")
    print("INVENTORY COMPLETE (read-only).")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    main()
    sys.exit(0)
