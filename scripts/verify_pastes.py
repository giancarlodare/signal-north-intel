"""Independent verification of the 2026-08-02 operator pastes. Read-only.

Verifies from the database, not from the operator's report:
  1. brief_signups         table + expected column shape
  2. salary_disclosures    table + expected column shape
  3. police_admin_stats    table + expected column shape
  4. extraction_envelopes  row 'peel-portal-2026-08': declared 54.00, open,
                           seeded rate -- the gate for the approved Peel drain

Column shape is verified by selecting the expected columns explicitly (a
missing column 400s, the phantom-column property working FOR us here).
Policy verification is stated honestly as out of reach: PostgREST cannot
read pg_policies, so policy counts remain the operator's SQL-editor check.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from src import supabase_client as sc  # noqa: E402

CHECKS = {
    "brief_signups": ("id,email,consent_source,confirmed_at,unsubscribed_at,"
                      "unsubscribe_token,created_at"),
    "salary_disclosures": ("id,year,sector,employer,last_name,first_name,"
                           "position,salary_paid,taxable_benefits,source_url,"
                           "ingested_at"),
    "police_admin_stats": "id,year,service,metric,value,source_url,ingested_at",
}


def main() -> int:
    print("PASTE VERIFICATION -- independent, read-only")
    ok = True

    for table, cols in CHECKS.items():
        try:
            rows = sc.fetch_rows_where(table, cols, {}, limit=3)
            print(f"  {table:22s} PRESENT, all {len(cols.split(','))} expected "
                  f"columns select cleanly, rows={len(rows)}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"  {table:22s} FAILED: {e}")

    try:
        env = sc.fetch_rows_where(
            "extraction_envelopes",
            "key,label,declared_usd,seed_rate_usd_per_doc,status,approved_on",
            {"key": "eq.peel-portal-2026-08"})
        if not env:
            ok = False
            print("  peel-portal-2026-08    MISSING from extraction_envelopes")
        else:
            r = env[0]
            print(f"  peel-portal-2026-08    declared={r['declared_usd']} "
                  f"rate={r['seed_rate_usd_per_doc']} status={r['status']} "
                  f"approved_on={r['approved_on']}")
            if float(r["declared_usd"]) != 54.0 or r["status"] != "open":
                ok = False
                print("    MISMATCH vs approved: expected declared=54.00 status=open")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"  extraction_envelopes   FAILED: {e}")

    print("\nverdict:", "ALL VERIFIED" if ok else "NOT VERIFIED -- see above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
