"""Corpus hygiene: suppress the obvious-noise signals so the live corpus, the
/corpus browser, the proposer, and the weekly brief never carry them.

Under the editorial model (docs/editorial-model-redesign.md) there is no signal
approval gate: every signal is corpus-live the moment it is inserted, and the
machine's scores (confidence, evidence_grade, materiality) are the trust layer.
The only automated write to review state is SUPPRESSION of noise, by one
conservative rule:

  AR1 -- the weakest a signal can be on every axis at once:
    materiality = 1  AND  confidence = speculative  AND  amount_max_cad is null
    AND  NOT defence-tagged.
  The four conditions are AND-ed so a signal strong on any single axis survives.
  defence_relevant is used ONLY to spare a signal, never to suppress one -- the
  collectors keep non-defence records on purpose, so "not defence" is not
  evidence of noise. A wrong suppression silently hides real intelligence, so
  the rule is deliberately narrow.

Invariants (operator):
  * Suppression stamps suppressed_by='triage@v1' (vs a human editor's 'human'),
    so the record always shows who hid a signal. It sets suppressed=true with
    suppressed_reason='AR1'. It is reversible and non-destructive: the signal
    stays in the database and in provenance, only excluded from the corpus.
  * Triage touches ONLY signal suppression state. It NEVER authors a prediction
    and NEVER confirms a procurement. The wall to the ledger is absolute.

    python -m src.triage --dry-run   # classify and report counts, write nothing
    python -m src.triage --apply     # suppress AR1 noise (writes suppressed=true)
"""
import argparse
import logging
import sys
from collections import Counter

from . import supabase_client

log = logging.getLogger(__name__)

STAMP = "triage@v1"
AR1_MATERIALITY = 1
SUPPRESS_REASON = "AR1"


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def is_ar1_noise(signal: dict, defence_relevant) -> bool:
    """True iff the signal is conservatively safe to suppress as noise (AR1):
    weakest on every axis at once. defence_relevant only spares -- it never
    causes a suppression."""
    try:
        mat = int(signal.get("materiality") or 3)
    except (TypeError, ValueError):
        mat = 3
    conf = signal.get("confidence")
    amt = signal.get("amount_max_cad")
    return (mat == AR1_MATERIALITY and conf == "speculative"
            and amt is None and defence_relevant is not True)


def run(dry_run: bool = True) -> dict:
    """Scan the live (non-suppressed) corpus and suppress AR1 noise. Idempotent:
    only non-suppressed signals are fetched, so a re-run never re-touches a row
    already suppressed."""
    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,confidence,materiality,amount_max_cad,"
        "documents(doc_type,defence_relevant)",
        {"suppressed": "is.false"})

    by_doctype = Counter()          # (doc_type, kept|suppress) -> count
    to_suppress = []
    for s in signals:
        doc = _one(s.get("documents")) or {}
        doc_type = doc.get("doc_type") or "unknown"
        if is_ar1_noise(s, doc.get("defence_relevant")):
            by_doctype[(doc_type, "suppress")] += 1
            to_suppress.append(s["id"])
        else:
            by_doctype[(doc_type, "kept")] += 1

    doc_types = sorted({dt for (dt, _) in by_doctype})
    total_sup = total_kept = 0
    mode = "dry-run" if dry_run else "APPLY"
    log.info("Triage (AR1 noise suppression) %s over %d live signals", mode, len(signals))
    log.info("%-16s %10s %8s", "doc_type", "suppress", "kept")
    for dt in doc_types:
        sup = by_doctype[(dt, "suppress")]
        kept = by_doctype[(dt, "kept")]
        total_sup += sup
        total_kept += kept
        log.info("%-16s %10d %8d", dt, sup, kept)
    log.info("%-16s %10d %8d", "TOTAL", total_sup, total_kept)

    suppressed = 0
    if not dry_run:
        for sid in to_suppress:
            # ONLY suppression state. No prediction, no procurement -- the wall.
            supabase_client.update_row("signals", sid, {
                "suppressed": True,
                "suppressed_reason": SUPPRESS_REASON,
                "suppressed_by": STAMP,
            })
            suppressed += 1
        log.info("Applied: suppressed %d AR1-noise signals as %s; %d remain live",
                 suppressed, STAMP, total_kept)
    else:
        log.info("Summary: %d would be suppressed, %d stay live, of %d scanned",
                 total_sup, total_kept, len(signals))

    return {"suppress": total_sup, "kept": total_kept,
            "suppressed": suppressed, "examined": len(signals)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corpus hygiene: suppress AR1 noise")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="classify and report counts, write nothing")
    group.add_argument("--apply", action="store_true",
                       help="suppress AR1 noise (writes suppressed=true, suppressed_by='triage@v1')")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Default to dry-run: writing requires an explicit --apply.
    run(dry_run=not args.apply)
    sys.exit(0)
