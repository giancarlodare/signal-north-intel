"""One-time backfill: derive event dates for documents with published_on NULL.

The freshness rule (briefs filter/sort on event date, never collection date —
docs/ROADMAP.md) only works if event dates exist. Early board-minutes
collection ran with narrower date patterns and a smaller body window, leaving
many Peel documents dateless even though the meeting date sits at the top of
the stored PDF text. This re-derives published_on from the stored fields using
the collector's (now richer) guess_meeting_date — same title/url/body order,
same "None over a wrong guess" discipline. It never overwrites an existing
date and touches nothing else.

    python -m src.backfill_event_dates --dry-run   # show what would change
    python -m src.backfill_event_dates             # apply

Safe to re-run: documents that gain a date leave the NULL set; the rest are
re-examined harmlessly.
"""
import argparse
import logging
import sys

from . import supabase_client
from .board_minutes import derive_event_date

log = logging.getLogger(__name__)

BODY_WINDOW = 4000   # same window the collector reads


def run(doc_type: str = "board_minutes", dry_run: bool = False) -> dict:
    stats = {"examined": 0, "dated": 0, "still_unknown": 0, "errors": 0}
    # month-precision counts fold into "dated"; the log line shows [month]
    docs = supabase_client.fetch_all_rows_where(
        "documents", "id,title,url,content",
        {"doc_type": f"eq.{doc_type}", "published_on": "is.null"})

    for doc in docs:
        stats["examined"] += 1
        date, precision = derive_event_date(
            doc.get("title") or "", doc.get("url") or "",
            (doc.get("content") or "")[:BODY_WINDOW])
        if not date:
            stats["still_unknown"] += 1
            continue
        payload = {"published_on": date, "date_precision": precision}
        try:
            if dry_run:
                log.info("[dry-run] would set published_on=%s [%s] for %r (%s)",
                         date, precision, (doc.get("title") or "")[:70], doc["id"])
            else:
                supabase_client.update_row("documents", doc["id"], payload)
                log.info("set published_on=%s [%s] for %r", date, precision,
                         (doc.get("title") or "")[:70])
            stats["dated"] += 1
        except Exception:   # noqa: BLE001 - one bad row must not kill the pass
            log.exception("Failed to update %s", doc["id"])
            stats["errors"] += 1

    log.info("Backfill complete%s: %s", " (DRY RUN)" if dry_run else "", stats)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="One-time event-date backfill from stored document fields")
    parser.add_argument("--doc-type", default="board_minutes")
    parser.add_argument("--dry-run", action="store_true",
                        help="log what would change, write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run(doc_type=args.doc_type, dry_run=args.dry_run)
    sys.exit(0 if result["errors"] == 0 else 1)
