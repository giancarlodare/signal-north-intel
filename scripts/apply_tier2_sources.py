"""Apply the tier-2 bids&tenders sources rows over REST (operator go
2026-07-26). Same URL-guarded semantics as
migrations/2026-07-26_big12_tier2_source_seed.sql, which is the durable
record. Idempotent; prints one line per row."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src import supabase_client

ROWS = [
    ("City of Hamilton Bids and Tenders portal", "https://hamilton.bidsandtenders.ca/Module/Tenders/en"),
    ("City of Brampton Bids and Tenders portal", "https://brampton.bidsandtenders.ca/Module/Tenders/en"),
    ("City of Kitchener Bids and Tenders portal", "https://kitchener.bidsandtenders.ca/Module/Tenders/en"),
    ("City of Vaughan Bids and Tenders portal", "https://vaughan.bidsandtenders.ca/Module/Tenders/en"),
    ("Halton Region Bids and Tenders portal", "https://haltonregion.bidsandtenders.ca/Module/Tenders/en"),
]

def main() -> int:
    existing = {(s.get("url") or "").rstrip("/")
                for s in supabase_client.fetch_rows("sources", "id,url")}
    for name, url in ROWS:
        if url.rstrip("/") in existing:
            print(f"exists: {url}")
            continue
        row = supabase_client.insert_row("sources", {
            "name": name, "url": url, "source_type": "gov_website",
            "jurisdiction": "municipal", "collector": "scraper",
            "cadence": "daily"})
        print(f"inserted: {url} id={row['id']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
