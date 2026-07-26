"""One-off housekeeping: reset the credit-dry extraction casualties to
'captured' so the drain re-extracts them.

Scope is deliberately narrow: only documents whose status is 'failed' AND
whose stored error_detail is the Anthropic credit-balance error (the Friday
2026-07-25 outage window). The two large-doc JSON-parse failures are NOT
reset here; they are a known class banked for the max_tokens fix
(docs/ROADMAP.md) and would fail again unchanged.

    python scripts/reset_credit_failed_docs.py --dry-run
    python scripts/reset_credit_failed_docs.py
"""
import argparse
import sys

sys.path.insert(0, ".")

from src import supabase_client


def main(dry_run: bool):
    rows = supabase_client.fetch_all_rows_where(
        "documents", "id,title,error_detail", {"status": "eq.failed"})
    credit = [r for r in rows
              if "credit balance" in (r.get("error_detail") or "").lower()]
    print(f"failed docs: {len(rows)}; credit-dry casualties: {len(credit)}")
    for r in credit:
        print(f"  {'would reset' if dry_run else 'resetting'} {r['id']} :: "
              f"{(r.get('title') or '')[:80]}")
        if not dry_run:
            supabase_client.update_document_status(r["id"], "captured")
    print("done" + (" (dry-run, nothing written)" if dry_run else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset credit-dry failed docs to captured")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main(args.dry_run)
    sys.exit(0)
