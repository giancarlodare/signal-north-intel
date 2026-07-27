"""Read-only extraction-headroom check for the 4 near-cell services (operator
targeted-drain approval, 2026-07-27). Before spending the ~$20-40 targeted
drain, measure whether depth even remains to drain: count captured (not yet
extracted) vs extracted documents for the near-cell services' publisher hosts.

If headroom is large, the targeted drain has fuel and is worth running. If
headroom is near-zero, depth is already exhausted for these services and the
answer to 'does depth convert to significance' is moot for extraction: the
route is the partial-pooling estimator (0b), not more drain. Either way this
read costs nothing and de-risks the spend.

    python scripts/check_near_cell_headroom.py
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import supabase_client

# The near-cell services publish on these hosts (Peel RP + Peel Board share
# peelpoliceboard.ca; TPS Board is tpsb.ca).
HOSTS = {
    "tpsb.ca": "Toronto Police Service Board",
    "peelpoliceboard.ca": "Peel RP + Peel Police Board",
}
ARC_DOC_TYPES = ("board_minutes", "award_notice", "news_release")


def main() -> int:
    # Pull id, url, status, doc_type for the arc-bearing doc types, page through.
    rows = []
    for dt in ARC_DOC_TYPES:
        for status in ("captured", "extracted", "failed"):
            page = supabase_client.fetch_all_rows_where(
                "documents", "id,url,doc_type,status",
                {"doc_type": f"eq.{dt}", "status": f"eq.{status}"})
            rows.extend(page)

    counts = defaultdict(lambda: defaultdict(int))
    for r in rows:
        url = (r.get("url") or "").lower()
        host = next((h for h in HOSTS if h in url), None)
        if not host:
            continue
        counts[host][(r.get("doc_type"), r.get("status"))] += 1

    print("=" * 66)
    print("NEAR-CELL EXTRACTION HEADROOM (read-only)")
    print("=" * 66)
    total_captured = 0
    for host, label in HOSTS.items():
        print(f"\n{label}  ({host})")
        c = counts[host]
        for dt in ARC_DOC_TYPES:
            cap = c.get((dt, "captured"), 0)
            ext = c.get((dt, "extracted"), 0)
            fail = c.get((dt, "failed"), 0)
            if cap or ext or fail:
                print(f"  {dt:14s} captured(headroom)={cap:<4d} extracted={ext:<4d} failed={fail}")
                total_captured += cap
    print("\n" + "=" * 66)
    print(f"TOTAL CAPTURED (drainable headroom) across near-cell hosts: {total_captured}")
    est_cost = total_captured * 0.006
    print(f"Rough extraction cost if fully drained: ~${est_cost:.2f} "
          f"(board PDFs run higher than the $0.006 mix rate)")
    if total_captured < 50:
        print("VERDICT: headroom EXHAUSTED. Extraction depth is spent for these "
              "services; growing longlag_n needs deeper COLLECTION first, or the "
              "partial-pooling route. A drain now would find little.")
    else:
        print(f"VERDICT: {total_captured} drainable docs remain. The targeted "
              "drain has fuel; run it scoped to these hosts and re-measure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
