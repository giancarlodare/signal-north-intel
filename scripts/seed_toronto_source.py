"""One-off enablement: seed the City of Toronto CKAN sources row, idempotently.

Mirrors migrations/2026-07-25_toronto_ckan_source_seed.sql exactly (same URL
key and non-URL columns), so a row this script creates is indistinguishable
from a migration-created one, and applying the SQL migration afterward stays a
no-op (its insert is guarded `where not exists`). Used to seed the live DB for
enablement without waiting on a manual SQL apply, so the daily-collect Toronto
step has its source row from its first run.

    python scripts/seed_toronto_source.py --dry-run   # report + plan only
    python scripts/seed_toronto_source.py             # apply
"""
import argparse
import sys

sys.path.insert(0, ".")

from src import supabase_client
from src.tenders_toronto import SOURCE_URL as TORONTO_URL

TORONTO_NAME = "City of Toronto Open Data (Toronto Bids)"
# The migration's non-URL columns, reused verbatim.
_MUNI_COLS = {"source_type": "gov_website", "jurisdiction": "municipal",
              "collector": "scraper", "cadence": "daily"}


def _norm(u: str) -> str:
    return (u or "").rstrip("/")


def run(dry_run: bool) -> None:
    rows = supabase_client.fetch_rows("sources", "id,name,url")
    existing = next((r for r in rows if _norm(r.get("url")) == _norm(TORONTO_URL)), None)

    print("=" * 68)
    print(f"Toronto CKAN sources row  (SOURCE_URL={TORONTO_URL})")
    print("=" * 68)
    if existing:
        print(f"  already present: id={existing['id']} name={existing.get('name')!r}; "
              f"no change.")
    else:
        print(f"  ABSENT; {'would insert' if dry_run else 'inserting'} "
              f"name={TORONTO_NAME!r}")
        if not dry_run:
            supabase_client.insert_row(
                "sources", {"name": TORONTO_NAME, "url": TORONTO_URL, **_MUNI_COLS})

    after = supabase_client.fetch_rows("sources", "id,name,url")
    row = next((r for r in after if _norm(r.get("url")) == _norm(TORONTO_URL)), None)
    ok = row is not None
    print(f"\nAFTER{' (dry-run: nothing written)' if dry_run else ''}: "
          f"{'id=' + row['id'] if row else 'STILL ABSENT'} "
          f"[{'OK' if ok else 'MISMATCH'}]")
    print(f"Collector SOURCE_URL resolves to a row: {ok}"
          f"{' (dry-run projection)' if dry_run else ''}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the Toronto CKAN sources row")
    parser.add_argument("--dry-run", action="store_true",
                        help="report current state and planned change, write nothing")
    args = parser.parse_args()
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(dry_run=args.dry_run)
    sys.exit(0)
