"""One-time backfill: grade signals collected before the taxonomy existed.

New signals are graded at extraction (src/signal_extractor). This grades the
existing corpus once, using the same deterministic src/taxonomy map over each
signal's signal_type and its source document's doc_type. Never overwrites a
grade that is already set (so re-runs are harmless and a future taxonomy@v2
regrade is a separate, deliberate pass, not this script).

    python -m src.backfill_evidence_grade --dry-run   # show the distribution
    python -m src.backfill_evidence_grade             # apply

Safe to re-run: graded rows leave the NULL set; the rest are re-examined
harmlessly.
"""
import argparse
import logging
import sys
from collections import Counter

from . import supabase_client, taxonomy

log = logging.getLogger(__name__)


def run(dry_run: bool = False) -> dict:
    stats = {"examined": 0, "graded": 0, "errors": 0}
    dist: Counter = Counter()

    # Embed the source document's doc_type via the PostgREST relationship, so a
    # single paged scan carries everything grade() needs.
    rows = supabase_client.fetch_all_rows_where(
        "signals", "id,signal_type,documents(doc_type)",
        {"evidence_grade": "is.null"})

    for row in rows:
        stats["examined"] += 1
        doc = row.get("documents")
        if isinstance(doc, list):          # PostgREST may embed to-one as a list
            doc = doc[0] if doc else None
        doc_type = (doc or {}).get("doc_type") if doc else None
        g = taxonomy.grade(row.get("signal_type") or "", doc_type or "")
        dist[taxonomy.rung(g)] += 1
        payload = {"evidence_grade": g, "evidence_grade_version": taxonomy.TAXONOMY_VERSION}
        try:
            if dry_run:
                log.info("[dry-run] grade=%d [%s] for signal %s (type=%s doc_type=%s)",
                         g, taxonomy.rung(g), row["id"], row.get("signal_type"), doc_type)
            else:
                supabase_client.update_row("signals", row["id"], payload)
            stats["graded"] += 1
        except Exception:   # noqa: BLE001 - one bad row must not kill the pass
            log.exception("Failed to grade signal %s", row["id"])
            stats["errors"] += 1

    log.info("Backfill complete%s: %s distribution=%s",
             " (DRY RUN)" if dry_run else "", stats, dict(sorted(dist.items())))
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="One-time evidence-grade backfill")
    parser.add_argument("--dry-run", action="store_true",
                        help="log what would change, write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run(dry_run=args.dry_run)
    sys.exit(0 if result["errors"] == 0 else 1)
