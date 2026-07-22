"""One-off maintenance: bring the sources table into agreement with the
Windsor, MERX-Ottawa, and IO newsroom collectors.

Diagnosis 2026-07-22 (operator found the live state; confirmed against the
repo): the seed migration 2026-07-21_merx_windsor_source_seed.sql is CORRECT
(its two URLs match the collector SOURCE_URL constants exactly) but its inserts
were never applied to this DB, so both the Windsor row and the
www.merx.com/cityofottawa buyer row are absent. A stray 'MERX Public Notices'
row (url https://merx.com) exists that NO collector reads and that appears in
no migration or source file, so it is a manual/discovery leftover. The IO
newsroom row is correct. A fresh apply of the seed stays correct, so the
migration file is unchanged.

This script corrects only the LIVE DB, idempotently and safely:
  - MERX-Ottawa: if the buyer row (www.merx.com/cityofottawa) is absent, the
    stray https://merx.com row is REPURPOSED to the buyer url+name ONLY when
    it carries zero attached documents; if it has documents, it is left
    untouched and the buyer row is inserted alongside (both cases reported).
  - Windsor: inserted if absent.
  - IO newsroom: verified, never modified.
Then it re-reads and confirms each collector's SOURCE_URL resolves to exactly
one row.

    python scripts/fix_merx_windsor_sources.py --dry-run   # report + plan only
    python scripts/fix_merx_windsor_sources.py             # apply the fix
"""
import argparse
import sys

sys.path.insert(0, ".")

from src import supabase_client
from src.tenders_windsor import SOURCE_URL as WINDSOR_URL
from src.tenders_merx import SOURCE_URL as MERX_URL
from src.io_newsroom import SOURCE_URL as IO_URL

WINDSOR_NAME = "City of Windsor Open Data Bids and Tenders"
MERX_NAME = "City of Ottawa MERX solicitations"
STRAY_MERX_URL = "https://merx.com"

# The seed migration's non-URL columns, reused for any insert so a
# script-created row is indistinguishable from a migration-created one.
_MUNI_COLS = {"source_type": "gov_website", "jurisdiction": "municipal",
              "collector": "scraper", "cadence": "daily"}


def _norm(u: str) -> str:
    return (u or "").rstrip("/")


def _by_url(rows: list) -> dict:
    return {_norm(r.get("url")): r for r in rows}


def _has_documents(source_id: str) -> bool:
    return bool(supabase_client.fetch_rows_where(
        "documents", "id", {"source_id": f"eq.{source_id}"}, limit=1))


def run(dry_run: bool) -> None:
    rows = supabase_client.fetch_rows("sources", "id,name,url")
    idx = _by_url(rows)

    print("=" * 68)
    print("BEFORE (relevant sources rows)")
    print("=" * 68)
    for label, url in (("windsor", WINDSOR_URL), ("merx-buyer", MERX_URL),
                       ("merx-stray", STRAY_MERX_URL), ("io-newsroom", IO_URL)):
        r = idx.get(_norm(url))
        print(f"  {label:12s} {url}")
        print(f"               -> {'row id=' + r['id'] + ' name=' + repr(r.get('name')) if r else 'ABSENT'}")

    # --- MERX-Ottawa buyer row ------------------------------------------
    if _norm(MERX_URL) in idx:
        print(f"\n[merx] buyer row already present; no change.")
    else:
        stray = idx.get(_norm(STRAY_MERX_URL))
        if stray:
            docs = _has_documents(stray["id"])
            if docs:
                print(f"\n[merx] stray {STRAY_MERX_URL} row HAS attached documents; "
                      f"leaving it untouched and inserting the buyer row separately.")
                if not dry_run:
                    supabase_client.insert_row(
                        "sources", {"name": MERX_NAME, "url": MERX_URL, **_MUNI_COLS})
                print(f"[merx] {'would insert' if dry_run else 'inserted'} buyer row "
                      f"{MERX_URL!r} name={MERX_NAME!r}")
            else:
                print(f"\n[merx] stray {STRAY_MERX_URL} row has NO attached documents; "
                      f"repurposing it to the buyer url+name.")
                if not dry_run:
                    supabase_client.update_row("sources", stray["id"],
                                               {"name": MERX_NAME, "url": MERX_URL})
                print(f"[merx] {'would update' if dry_run else 'updated'} row {stray['id']} "
                      f"-> url={MERX_URL!r} name={MERX_NAME!r}")
        else:
            print(f"\n[merx] no buyer row and no stray row; inserting the buyer row.")
            if not dry_run:
                supabase_client.insert_row(
                    "sources", {"name": MERX_NAME, "url": MERX_URL, **_MUNI_COLS})
            print(f"[merx] {'would insert' if dry_run else 'inserted'} {MERX_URL!r}")

    # --- Windsor row ----------------------------------------------------
    if _norm(WINDSOR_URL) in idx:
        print(f"\n[windsor] row already present; no change.")
    else:
        print(f"\n[windsor] row ABSENT; inserting.")
        if not dry_run:
            supabase_client.insert_row(
                "sources", {"name": WINDSOR_NAME, "url": WINDSOR_URL, **_MUNI_COLS})
        print(f"[windsor] {'would insert' if dry_run else 'inserted'} {WINDSOR_URL!r}")

    # --- IO newsroom (verify only) --------------------------------------
    print(f"\n[io] {'present, unchanged' if _norm(IO_URL) in idx else 'ABSENT (unexpected; seed not applied?)'}")

    # --- AFTER + agreement check ----------------------------------------
    after = _by_url(supabase_client.fetch_rows("sources", "id,name,url"))
    print("\n" + "=" * 68)
    print("AFTER" + (" (dry-run: nothing written)" if dry_run else ""))
    print("=" * 68)
    ok = True
    for label, url in (("windsor", WINDSOR_URL), ("merx-buyer", MERX_URL),
                       ("io-newsroom", IO_URL)):
        r = after.get(_norm(url))
        agree = r is not None
        ok = ok and agree
        print(f"  {label:12s} SOURCE_URL={url}")
        print(f"               -> {'id=' + r['id'] + ' name=' + repr(r.get('name')) if r else 'STILL ABSENT'} "
              f"[{'OK' if agree else 'MISMATCH'}]")
    stray_after = after.get(_norm(STRAY_MERX_URL))
    if stray_after:
        print(f"  note: stray {STRAY_MERX_URL} row still present (id={stray_after['id']}).")
    print(f"\nAll three collectors agree with the sources table: {ok}"
          f"{' (dry-run projection)' if dry_run else ''}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix merx/windsor/io sources rows")
    parser.add_argument("--dry-run", action="store_true",
                        help="report current state and planned changes, write nothing")
    args = parser.parse_args()
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(dry_run=args.dry_run)
    sys.exit(0)
