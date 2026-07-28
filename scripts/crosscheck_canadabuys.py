"""CanadaBuys capture-leak cross-check (operator go 2026-07-28).

The suspicion: 11 CanadaBuys tender docs in 14 days is too low. The daily
collector reads the NEW-tenders CSV once a day; if that file is a rolling
since-last-refresh window regenerated more often, notices leak between reads.

Method, read-only: fetch the FULL open-tenders CSV (every currently-open
notice), take the rows PUBLISHED in the last 14 days, run the keep-filter
exactly as the collector does, and check each kept notice's content_hash
against the corpus. Every kept-but-absent row is a leaked notice, listed.

    python scripts/crosscheck_canadabuys.py   # CI only (sandbox blocks both)
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import config, supabase_client
from src.filters import evaluate, load_keywords
from src.hashing import content_hash
from src.main import fetch_csv_rows, parse_tender_row


def main() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
    keywords = load_keywords()

    rows = fetch_csv_rows(config.OPEN_TENDER_NOTICES_URL)
    print(f"open-tenders CSV: {len(rows)} currently-open notices")
    if not rows:
        print("LOUD FAILURE: empty open-tenders CSV; cannot cross-check.")
        return 2
    fields = list(rows[0].keys())
    pub_field = next((f for f in fields if f.startswith("publicationDate")), None)

    recent, kept = [], []
    for row in rows:
        pub = (row.get(pub_field) or "")[:10]
        if pub >= cutoff:
            t = parse_tender_row(row, fields)
            recent.append(t)
            r = evaluate(t["title"], t["description"], t["unspsc_raw"], keywords)
            if r.kept:
                kept.append((t, r, pub))
    print(f"published in last 14d: {len(recent)}; keep-filter KEEPS: {len(kept)}")

    corpus = supabase_client.fetch_all_rows_where(
        "documents", "content_hash", {"doc_type": "eq.tender_notice"})
    hashes = {c["content_hash"] for c in corpus}
    print(f"corpus tender_notice docs (all time): {len(hashes)}")

    missing = []
    for t, r, pub in kept:
        ref = t["cb_reference"]
        url = config.TENDER_NOTICE_URL_TEMPLATE.format(reference=ref or t["title"])
        chash = content_hash(ref or url, "tender_notice")
        if chash not in hashes:
            missing.append((t, r, pub))

    print(f"\nVERDICT: {len(missing)} of {len(kept)} kept notices from the "
          f"last 14 days are ABSENT from the corpus"
          + (f" ({100 * len(missing) / len(kept):.0f}% leak rate)" if kept else ""))
    for t, r, pub in missing[:25]:
        why = r.matched_keyword or f"unspsc {r.matched_unspsc_segment}"
        print(f"  MISSING {pub}  {(t['title'] or '')[:70]} | "
              f"buyer: {(t['buyer_name'] or '?')[:36]} | matched: {why}")
    if len(missing) > 25:
        print(f"  ... and {len(missing) - 25} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
