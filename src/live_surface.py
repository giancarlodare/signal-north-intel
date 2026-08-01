"""Member "closing soon" live surface writer (Wave 3, operator D1-D4 approved
2026-07-28; docs/wave3-live-surface-design.md).

Projects the gate-cleared slice of live opportunities into member_live_items,
the flat table the member portal reads. The database cannot leak what this
table does not contain, so the WHOLE gate lives here -- one reviewable,
deterministic (no-LLM) pass -- not in RLS predicates on the rich tables.

Slice (v1, D2; every condition fail-closed):
  * signals.public_safety IS TRUE       (the tested member barrier; NULL fails)
  * signals.suppressed IS FALSE
  * documents.doc_type in {tender_notice, grant_program}
  * documents.published_on (the closing/deadline date) in
    [today, today + lead], lead 30 days (45 for grants: prep runway)
  * evidence_grade >= 4                  (in-market or better; keeps board
                                          chatter off a surface named "closing soon")

Projected columns only (D3): headline, buyer, closing_on, date_precision,
doc_type, reference_number, url, category_slug, defence_relevant, signal_id.
NO grades, NO review state, NO amounts.

Delete-and-rewrite each run (the projection is small; a full rewrite keeps it
exactly in sync with the slice, so an item that closed yesterday drops off
today without needing a separate expiry pass). Idempotent by construction.

LOUD FAILURE: with the corpus at ~85 tenders/day a zero-row slice means a
broken join or a bad flag, never a quiet truth, so --apply raises rather than
writing an empty surface. Pre-migration guard: if member_live_items does not
exist yet, the pass logs and exits 0 so wiring it in before the paste never
reddens the pipeline.

    python -m src.live_surface --dry-run   # compute + validation table, write nothing
    python -m src.live_surface --apply      # rewrite the projection
"""
import argparse
import logging
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from . import supabase_client

log = logging.getLogger(__name__)

LIVE_DOC_TYPES = {"tender_notice", "grant_program"}
DEFAULT_LEAD_DAYS = 30
LEAD_DAYS_BY_DOCTYPE = {"grant_program": 45}
MIN_GRADE = 4
TABLE = "member_live_items"


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def lead_days_for(doc_type) -> int:
    return LEAD_DAYS_BY_DOCTYPE.get(doc_type, DEFAULT_LEAD_DAYS)


def in_window(published_on, today: date, doc_type) -> bool:
    """True iff the deadline is today..today+lead (future-dated, actionable)."""
    d = _parse_date(published_on)
    if d is None:
        return False
    return today <= d <= today + timedelta(days=lead_days_for(doc_type))


def project(signals, today: date) -> tuple:
    """Pure: (rows, rejected_counter). A signal enters the projection iff every
    slice condition holds. Each row carries only presentation columns."""
    rows = []
    rejected: Counter = Counter()
    for s in signals:
        # public_safety is the tested member barrier; NULL/false never passes.
        if not s.get("public_safety"):
            rejected["not_public_safety"] += 1
            continue
        if s.get("suppressed"):
            rejected["suppressed"] += 1
            continue
        if (s.get("evidence_grade") or 0) < MIN_GRADE:
            rejected["below_grade"] += 1
            continue
        doc = _one(s.get("documents")) or {}
        doc_type = doc.get("doc_type")
        if doc_type not in LIVE_DOC_TYPES:
            rejected["wrong_doc_type"] += 1
            continue
        if not in_window(doc.get("published_on"), today, doc_type):
            rejected["out_of_window"] += 1
            continue
        org = _one(s.get("organizations")) or {}
        rows.append({
            "signal_id": s["id"],
            "headline": (s.get("title") or "(untitled opportunity)")[:300],
            "buyer_name": org.get("canonical_name"),
            "doc_type": doc_type,
            "closing_on": str(_parse_date(doc.get("published_on"))),
            "date_precision": doc.get("date_precision") or "day",
            "reference_number": doc.get("reference_number"),
            "url": doc.get("url"),
            "category_slug": category_slug(s),
            # Open tag array, not a fixed domain boolean (generic-shape rule,
            # docs/spine-vertical-seam.md). The VERTICAL semantics are the tag
            # values this vertical happens to emit.
            "tags": (["defence"] if doc.get("defence_relevant") else []),
        })
    # Soonest-closing first: the member's most urgent opportunity leads.
    rows.sort(key=lambda r: r["closing_on"])
    return rows, rejected


def category_slug(signal: dict) -> str | None:
    """The signal's category slug, from the EMBED or a flat key.

    The slug lives on `categories`, never on `signals`. Selecting a bare
    `category_slug` from signals 400s the whole PostgREST query and takes the
    nightly run red (2026-07-30 and 07-31: "column signals.category_slug does
    not exist"). The bug stayed latent while member_live_items was unpasted,
    because table_present() returned early; pasting the migration un-skipped
    the writer and exposed it on the next run.

    Accepts either shape so a caller holding an already-flattened row (the
    unit tests, and any future projection that pre-normalizes) still works.
    """
    embedded = signal.get("categories")
    if isinstance(embedded, list):
        embedded = embedded[0] if embedded else None
    if isinstance(embedded, dict):
        return embedded.get("slug")
    return signal.get("category_slug")


def table_present() -> bool:
    try:
        supabase_client.fetch_rows_where(TABLE, "id", {}, limit=1)
        return True
    except Exception as e:  # noqa: BLE001 - any read error means "not pasted yet"
        log.info("%s not present yet (%s); skipping. Paste "
                 "migrations/2026-07-28_member_live_items.sql to enable the "
                 "live surface.", TABLE, type(e).__name__)
        return False


def _report(rows, rejected, today: date) -> None:
    by_buyer = Counter(r["buyer_name"] or "(unresolved)" for r in rows)
    by_type = Counter(r["doc_type"] for r in rows)
    parsed = sum(1 for r in rows if r["closing_on"] and r["closing_on"] != "None")
    log.info("live-surface projection for today=%s: %d rows", today, len(rows))
    log.info("  by doc_type: %s", dict(by_type))
    log.info("  by buyer: %s", dict(by_buyer.most_common(12)))
    log.info("  closing-date parsed: %d/%d (%d%%)", parsed, len(rows),
             round(100 * parsed / (len(rows) or 1)))
    log.info("  rejected by condition: %s", dict(rejected))
    for r in rows[:15]:
        log.info("  %s  %-16s  %-22s  %s", r["closing_on"], r["doc_type"],
                 (r["buyer_name"] or "-")[:22], (r["headline"] or "")[:60])


def run(dry_run: bool = True, today: date | None = None) -> dict:
    today = today or date.today()
    if not table_present():
        return {"skipped": "table_absent"}

    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,title,public_safety,suppressed,evidence_grade,"
        "categories(slug),"
        "organizations(canonical_name),"
        "documents!inner(doc_type,published_on,date_precision,url,"
        "reference_number,defence_relevant)",
        {"suppressed": "is.false", "public_safety": "is.true"})
    rows, rejected = project(signals, today)
    _report(rows, rejected, today)

    if not rows:
        # A live corpus always has opportunities closing in the next 30 days;
        # zero means a broken join or a bad flag, never a quiet truth.
        raise RuntimeError(
            "live-surface slice produced 0 rows: broken join or flag, not a "
            "quiet truth. Refusing to publish an empty member surface.")

    if dry_run:
        log.info("live-surface: %d rows (DRY RUN, nothing written)", len(rows))
        return {"rows": len(rows), "rejected": dict(rejected)}

    # Delete-and-rewrite: the projection mirrors the slice exactly each run.
    # Filter is non-empty (delete_rows refuses a bare table wipe); id=not.is.null
    # matches every row.
    supabase_client.delete_rows(TABLE, {"id": "not.is.null"})
    now = datetime.now(timezone.utc).isoformat()
    written = 0
    for r in rows:
        supabase_client.insert_row(TABLE, dict(r, refreshed_at=now))
        written += 1
    log.info("live-surface: rewrote %d rows", written)
    return {"rows": written, "rejected": dict(rejected)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true",
                   help="compute + print the validation table, write nothing")
    g.add_argument("--apply", action="store_true",
                   help="rewrite the member_live_items projection")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(dry_run=not args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
