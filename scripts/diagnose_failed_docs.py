"""Print extraction-failed documents with their stored error detail (read-only).

The extract-backfill drain marks a failing doc status='failed' with
error_detail, so the diagnosis is a query, not a log trawl.

    python scripts/diagnose_failed_docs.py
"""
import sys

sys.path.insert(0, ".")

from src import supabase_client


def main():
    rows = supabase_client.fetch_all_rows_where(
        "documents", "id,title,doc_type,url,error_detail,published_on",
        {"status": "eq.failed"})
    print(f"failed documents: {len(rows)}")
    for r in rows:
        print("=" * 70)
        print(f"id={r['id']} doc_type={r.get('doc_type')} published={r.get('published_on')}")
        print(f"title: {(r.get('title') or '')[:120]}")
        print(f"url:   {(r.get('url') or '')[:120]}")
        print(f"error: {(r.get('error_detail') or '(none stored)')[:400]}")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
    sys.exit(0)
