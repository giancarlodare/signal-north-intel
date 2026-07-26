"""Hansard enablement helper (operator go 2026-07-26). Two halves:

1. SOURCES ROW (DML): ensure the ola.org row from
   migrations/2026-07-26_hansard_doc_type_and_source.sql exists, via the
   same URL-guarded insert semantics over REST. Idempotent.
2. ENUM PROBE (read-only): the legislative_debate doc_type value is DDL
   (ALTER TYPE) and can only be applied in the Supabase SQL Editor. This
   script cannot and does not apply it; it PROBES whether it exists by
   filtering documents on the value: 200 means the enum value is live,
   a 22P02-style 400 means the operator must paste the migration's DO
   block before the collector's first real run.

Exit 0 when both halves are ready; exit 2 when the enum value is missing
(loud, so the enablement run goes red rather than half-enabled).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import supabase_client

SOURCE_URL = "https://www.ola.org/en/legislative-business/house-documents"
ROW = {
    "name": "Legislative Assembly of Ontario Hansard",
    "url": SOURCE_URL,
    "source_type": "gov_website",
    "jurisdiction": "provincial",
    "collector": "scraper",
    "cadence": "daily",
}


def main() -> int:
    rows = supabase_client.fetch_rows("sources", "id,url")
    existing = next((r for r in rows
                     if (r.get("url") or "").rstrip("/") == SOURCE_URL.rstrip("/")), None)
    if existing:
        print(f"sources row exists: {existing['id']}")
    else:
        row = supabase_client.insert_row("sources", ROW)
        print(f"sources row inserted: {row['id']}")

    try:
        supabase_client._request(
            "GET", "documents", headers=supabase_client._headers(),
            params={"select": "id", "doc_type": "eq.legislative_debate", "limit": 1})
        print("enum probe: legislative_debate EXISTS; Hansard fully enabled")
        return 0
    except Exception as exc:   # noqa: BLE001 - any failure means not provable
        print(f"enum probe: legislative_debate NOT usable yet ({exc})")
        print("ACTION: paste the DO block from "
              "migrations/2026-07-26_hansard_doc_type_and_source.sql "
              "into the Supabase SQL Editor (its own tab), then re-run.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
