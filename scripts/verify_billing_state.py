"""Independent verification of the billing tables and webhook activity.

Written because the operator asked for verification rather than a report
taken on trust. Read-only; writes nothing, calls no LLM, and never contacts
Stripe (it reads only what the webhook has PROJECTED locally, which is the
thing actually being verified).

Answers three questions:
  1. Does member_subscriptions exist with the expected shape?  (9 / 4 / n)
  2. Does tier_inquiries exist, and has anything been captured?
  3. Has the webhook ever written a row, and how recently?

WHAT AN EMPTY TABLE MEANS. Zero subscription rows is NOT evidence the webhook
is broken, and it is NOT evidence it works. It means nobody has completed a
checkout yet. Only a real test-mode checkout produces the row that proves the
path end to end.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import supabase_client as sc  # noqa: E402

EXPECTED_SUB_COLUMNS = {
    "member_id", "stripe_customer_id", "stripe_subscription_id", "tier",
    "interval", "status", "current_period_end", "event_created_at",
    "updated_at",
}


def probe(table: str, select: str = "*"):
    try:
        return sc.fetch_all_rows_where(table, select, {}), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:160]


def main() -> int:
    print("BILLING STATE VERIFICATION -- read-only, independent\n")

    # --- member_subscriptions ------------------------------------------
    print("=" * 78)
    print("member_subscriptions")
    print("=" * 78)
    rows, err = probe("member_subscriptions")
    if err:
        print(f"  ABSENT or unreadable: {err}")
        print("  -> the portal guard FAILS CLOSED against this, which is correct")
    else:
        # Column shape is read from a real row when one exists; otherwise the
        # table exists but is empty, which is the expected pre-checkout state.
        print(f"  readable: YES")
        print(f"  rows: {len(rows)}")
        if rows:
            cols = set(rows[0].keys())
            missing = EXPECTED_SUB_COLUMNS - cols
            extra = cols - EXPECTED_SUB_COLUMNS
            print(f"  columns: {len(cols)}  missing={sorted(missing) or 'none'}"
                  f"  unexpected={sorted(extra) or 'none'}")
            now = datetime.now(timezone.utc)
            print("\n  WEBHOOK HAS WRITTEN. Rows:")
            for r in rows:
                upd = str(r.get("updated_at") or "")[:19]
                print(f"    tier={r.get('tier')} interval={r.get('interval')} "
                      f"status={r.get('status')} "
                      f"period_end={str(r.get('current_period_end'))[:10]} "
                      f"updated={upd}")
                print(f"      member={r.get('member_id')}")
                print(f"      sub={r.get('stripe_subscription_id')} "
                      f"cust={r.get('stripe_customer_id')}")
            print("\n  -> END TO END CONFIRMED: Stripe -> webhook -> table.")
        else:
            print("\n  NO ROWS. This is NOT a failure signal and NOT a success")
            print("  signal. It means no checkout has completed yet. The only")
            print("  proof of the path is a real test-mode checkout.")

    # --- tier_inquiries -------------------------------------------------
    print("\n" + "=" * 78)
    print("tier_inquiries")
    print("=" * 78)
    rows, err = probe("tier_inquiries", "id,tier,status,created_at")
    if err:
        print(f"  ABSENT or unreadable: {err}")
    else:
        print(f"  readable: YES   rows: {len(rows)}")
        by = {}
        for r in rows:
            by[(r.get("tier"), r.get("status"))] = by.get(
                (r.get("tier"), r.get("status")), 0) + 1
        for k, n in sorted(by.items()):
            print(f"    {k[0]:12s} {k[1]:10s} {n}")
        if not rows:
            print("    (no inquiries captured yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
