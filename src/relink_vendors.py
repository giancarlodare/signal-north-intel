"""Backfill: re-link contract_awards rows that inserted with vendor_id=None.

Issue #74: find_or_create_vendor's lookup used a double-quoted ilike value,
which PostgREST matches literally, so an existing vendor silently never
matched. Every repeat vendor then fell through to the ignore-duplicates
insert, whose body is empty on a duplicate, and the award row linked
vendor_id=None. Repeat vendors are the incumbents, and incumbents are the
recompete data, so those NULLs cost real analysis.

With the lookup fixed (supabase_client.find_or_create_vendor now uses eq and
re-fetches after a lost insert race), this pass walks every award that has a
vendor_name but no vendor_id and links it through the SAME find_or_create
path, so the backfill and the forward path cannot drift.

Idempotent: a second run finds nothing left to link (vendor_id is set), and
find_or_create_vendor never duplicates a vendor. Writes ONLY
contract_awards.vendor_id and (for genuinely new names) vendors rows.

    python -m src.relink_vendors --dry-run   # count and report, write nothing
    python -m src.relink_vendors --apply     # link them
"""
import argparse
import logging
from collections import Counter

from . import supabase_client

log = logging.getLogger(__name__)


def run(dry_run: bool = True) -> dict:
    rows = supabase_client.fetch_all_rows_where(
        "contract_awards", "id,vendor_name",
        {"vendor_id": "is.null", "vendor_name": "not.is.null"})
    names = Counter(" ".join((r.get("vendor_name") or "").split())
                    for r in rows)
    names.pop("", None)
    log.info("%d award rows have a vendor_name but vendor_id=NULL "
             "(%d distinct vendor names)", len(rows), len(names))
    for name, n in names.most_common(15):
        log.info("  %3dx %s", n, name[:70])

    stats = {"rows": len(rows), "distinct_names": len(names),
             "linked": 0, "unlinkable": 0}
    if dry_run:
        log.info("dry-run: nothing written. Re-run with --apply to link.")
        return stats

    # Link name-by-name so each distinct vendor is resolved once, then every
    # affected award row is patched.
    vendor_ids: dict = {}
    for name in names:
        vendor_ids[name] = supabase_client.find_or_create_vendor(name)
    for r in rows:
        name = " ".join((r.get("vendor_name") or "").split())
        vid = vendor_ids.get(name)
        if not vid:
            stats["unlinkable"] += 1
            continue
        supabase_client.update_row("contract_awards", r["id"], {"vendor_id": vid})
        stats["linked"] += 1
    log.info("linked %d award rows; %d unlinkable (empty or unresolvable name)",
             stats["linked"], stats["unlinkable"])
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Re-link contract awards left with vendor_id=None by issue #74")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="count and report, write nothing")
    group.add_argument("--apply", action="store_true", help="link the awards")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(dry_run=not args.apply)
