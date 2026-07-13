"""Review triage: auto-approve clean structured-disclosure signals, reserve
manual review for the ones that actually need judgment.

Operator-approved rules (2026-07-13). A signal is AUTO-APPROVED only when ALL:
  1. Structured federal disclosure provenance: its source document comes from a
     search.open.canada.ca proactive-disclosure dataset (federal contract
     awards and grant awards). These are authoritative government records the
     extractor reformats, not prose it interprets. CanadaBuys and every
     interpreted source (board minutes, news, program pages) are deliberately
     NOT structured here and always go to a human.
  2. confidence = confirmed.
  3. needs_org_resolution = false.
  4. Not high-stakes: materiality < 4 AND (amount_max_cad null or < $1,000,000).
Anything else stays MANUAL.

Two invariants are non-negotiable (operator):
  * Auto-approval stamps reviewed_by='triage@v1' (vs 'human'), so the record
    always shows which signals a person actually eyeballed. Triage writes the
    same review_note='approved' a human approval does, so downstream consumers
    (the procurement proposer) treat an auto-approval and a human approval
    identically -- the only difference recorded is the reviewer.
  * Triage touches ONLY the signal review state (reviewed, review_note,
    reviewed_by). It NEVER authors a prediction and NEVER confirms a
    procurement. The wall between triage and the ledger is absolute: nothing in
    this module writes to predictions, prediction_outcomes, or procurements.

    python -m src.triage --dry-run   # classify and report counts, write nothing
    python -m src.triage --apply     # additionally auto-approve the clean set
"""
import argparse
import logging
import sys
from collections import Counter

from . import supabase_client

log = logging.getLogger(__name__)

STAKES_THRESHOLD_CAD = 1_000_000.0
HIGH_MATERIALITY = 4
STAMP = "triage@v1"
DISCLOSURE_URL_PREFIX = "https://search.open.canada.ca/"


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def is_structured_disclosure(source_url) -> bool:
    """The federal proactive-disclosure datasets (contract awards, grant
    awards). Keyed on the source URL, which uniquely identifies those rows.
    CanadaBuys (canadabuys.canada.ca) is intentionally excluded: it is a
    distinct source class the operator keeps eyes on."""
    return (source_url or "").startswith(DISCLOSURE_URL_PREFIX)


def gate_failures(signal: dict, source_url) -> list:
    """The list of auto-approve gates this signal FAILS (empty => auto-approve).
    Each name is an independent reason it needs a human: a signal can trip
    several, so these are counted independently, not mutually exclusive."""
    conf = signal.get("confidence")
    try:
        mat = int(signal.get("materiality") or 3)
    except (TypeError, ValueError):
        mat = 3
    amt = signal.get("amount_max_cad")
    try:
        amt = float(amt) if amt is not None else None
    except (TypeError, ValueError):
        amt = None
    needs_org = bool(signal.get("needs_org_resolution"))

    fails = []
    if not is_structured_disclosure(source_url):
        fails.append("not_structured_source")
    if conf != "confirmed":
        fails.append("confidence_%s" % (conf or "null"))
    if needs_org:
        fails.append("needs_org_resolution")
    if mat >= HIGH_MATERIALITY:
        fails.append("materiality_ge_4")
    if amt is not None and amt >= STAKES_THRESHOLD_CAD:
        fails.append("amount_ge_1M")
    return fails


def classify(signal: dict, source_url) -> str:
    """'auto_approve' or 'manual' for one signal, per the approved rules."""
    return "auto_approve" if not gate_failures(signal, source_url) else "manual"


def run(dry_run: bool = True) -> dict:
    """Classify every unreviewed signal. In --apply mode, auto-approve the clean
    structured set (reviewed=true, review_note='approved', reviewed_by=STAMP)
    and leave everything else for a human. Idempotent: only unreviewed signals
    are fetched, so a re-run never re-touches an already-approved row."""
    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,confidence,materiality,needs_org_resolution,amount_max_cad,"
        "documents(doc_type,source_id)",
        {"reviewed": "is.false"})

    url_by_source = {s["id"]: s.get("url")
                     for s in supabase_client.fetch_rows("sources", "id,url")}

    by_doctype = Counter()          # (doc_type, decision) -> count
    reasons_by_doctype = {}         # doc_type -> Counter(reason -> count)
    to_approve = []                 # signal ids classified auto_approve
    for s in signals:
        doc = _one(s.get("documents")) or {}
        doc_type = doc.get("doc_type") or "unknown"
        src_url = url_by_source.get(doc.get("source_id"))
        fails = gate_failures(s, src_url)
        decision = "auto_approve" if not fails else "manual"
        by_doctype[(doc_type, decision)] += 1
        if decision == "auto_approve":
            to_approve.append(s["id"])
        else:
            rc = reasons_by_doctype.setdefault(doc_type, Counter())
            for f in fails:
                rc[f] += 1

    doc_types = sorted({dt for (dt, _) in by_doctype})
    total_auto = total_manual = 0
    mode = "dry-run" if dry_run else "APPLY"
    log.info("Triage %s over %d unreviewed signals", mode, len(signals))
    log.info("%-16s %12s %8s", "doc_type", "auto_approve", "manual")
    for dt in doc_types:
        a = by_doctype[(dt, "auto_approve")]
        m = by_doctype[(dt, "manual")]
        total_auto += a
        total_manual += m
        log.info("%-16s %12d %8d", dt, a, m)
    log.info("%-16s %12d %8d", "TOTAL", total_auto, total_manual)
    for dt in doc_types:
        rc = reasons_by_doctype.get(dt)
        if not rc:
            continue
        log.info("why-manual [%s]:", dt)
        for reason, n in rc.most_common():
            log.info("    %-24s %6d", reason, n)

    approved = 0
    if not dry_run:
        for sid in to_approve:
            # ONLY the review state. No prediction, no procurement -- the wall.
            supabase_client.update_row("signals", sid, {
                "reviewed": True,
                "review_note": "approved",
                "reviewed_by": STAMP,
            })
            approved += 1
        log.info("Applied: auto-approved %d signals as %s; %d remain for manual "
                 "review", approved, STAMP, total_manual)
    else:
        log.info("Summary: %d would auto-approve, %d stay manual, of %d unreviewed",
                 total_auto, total_manual, len(signals))

    return {"auto": total_auto, "manual": total_manual,
            "approved": approved, "examined": len(signals)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review triage (auto-approve clean structured signals)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="classify and report counts, write nothing")
    group.add_argument("--apply", action="store_true",
                       help="auto-approve the clean structured set (writes reviewed_by='triage@v1')")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Default to dry-run: writing requires an explicit --apply.
    run(dry_run=not args.apply)
    sys.exit(0)
