"""Backfill: enrich the existing title-only federal tender documents.

The daily CanadaBuys file carries only NEW notices, so the title-only stock
collected before enrichment (docs/canadabuys-enrichment-design.md) cannot be
filled from it. This pass downloads the COMPLETE open-tenders CSV, matches
existing federal tender_notice documents by the CanadaBuys reference embedded
in their URL, and fills content, close date (the event date), UNSPSC codes,
buyer, and solicitation number through the same row parser the daily
collector uses, so backfill and forward path cannot drift.

Dry-run (the default) writes nothing and reports, per the approved design:
  - how many documents would be filled and how many cannot be (notice no
    longer in the open file: closed since collection; they stay title-only
    and age out honestly), and
  - THE OPERATOR FLAG: which enriched close dates would pull an existing
    federal tender into the CURRENT brief's imminent window, listed
    individually, so the operator sees what enters the draft before apply.

    python -m src.backfill_tender_details --dry-run
    python -m src.backfill_tender_details --apply
"""
import argparse
import logging
import sys
from datetime import date, timedelta

from . import config, supabase_client
from .brief_generator import lead_days_for
from .canadabuys import fetch_csv_rows
from .main import parse_tender_row

log = logging.getLogger(__name__)


def _url_reference(url: str) -> str:
    """The CanadaBuys reference from a stored tender URL (last path segment)."""
    return (url or "").rstrip("/").rsplit("/", 1)[-1]


def run(dry_run: bool = True, today: date | None = None) -> dict:
    today = today or date.today()
    lead = lead_days_for("tender_notice")
    horizon = today + timedelta(days=lead)

    docs = supabase_client.fetch_all_rows_where(
        "documents", "id,url,title,published_on,content",
        {"doc_type": "eq.tender_notice",
         "content": "is.null",
         "url": "like.*canadabuys.canada.ca*"})
    log.info("%d federal tender documents are title-only (content NULL)", len(docs))

    rows = fetch_csv_rows(config.OPEN_TENDER_NOTICES_URL)
    fields = list(rows[0].keys()) if rows else []
    by_ref: dict = {}
    for row in rows:
        t = parse_tender_row(row, fields)
        if t["cb_reference"]:
            # Amendments repeat a reference; the file is ordered oldest-first
            # per notice, so the last row wins (the latest amendment).
            by_ref[t["cb_reference"]] = t

    fillable, unmatched, pulled_imminent = [], [], []
    for doc in docs:
        t = by_ref.get(_url_reference(doc.get("url")))
        if not t:
            unmatched.append(doc)
            continue
        fillable.append((doc, t))
        close = t["published_on"]
        if close and today < close <= horizon:
            pulled_imminent.append((doc, t))

    log.info("backfill %s: %d fillable, %d not in the open file (closed since "
             "collection; stay title-only and age out)",
             "dry-run" if dry_run else "APPLY", len(fillable), len(unmatched))
    log.info("OPERATOR FLAG: %d enriched close dates would pull an existing "
             "tender into the current imminent window (today %s .. +%d days)",
             len(pulled_imminent), today, lead)
    for doc, t in pulled_imminent:
        log.info("  -> closes %s  %s  [%s]", t["published_on"],
                 (doc.get("title") or "")[:80], t["buyer_name"] or "no buyer")

    stats = {"title_only": len(docs), "fillable": len(fillable),
             "unmatched": len(unmatched),
             "pulled_into_imminent": len(pulled_imminent), "filled": 0,
             "dry_run": dry_run}
    if dry_run:
        log.info("dry-run: nothing written. Re-run with --apply to fill.")
        return stats

    for doc, t in fillable:
        supabase_client.update_row("documents", doc["id"], {
            "published_on": t["published_on"],
            "reference_number": t["solicitation"] or None,
            "content": t["content"],
            "unspsc_codes": t["unspsc_codes"] or None,
            "buyer_name": t["buyer_name"],
        })
        stats["filled"] += 1
    log.info("filled %d documents", stats["filled"])
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich title-only federal tenders from the complete open-tenders CSV")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="report counts + the imminent-window flag, write nothing")
    group.add_argument("--apply", action="store_true", help="fill the documents")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(dry_run=not args.apply)
    sys.exit(0)
