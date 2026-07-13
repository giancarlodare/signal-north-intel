"""Review triage: sort every unreviewed signal into one of three outcomes so a
human only reviews the genuinely-uncertain middle.

  auto_approve -- clean structured-disclosure records (below)
  auto_reject  -- signals we are confident are noise (conservative; below)
  flag         -- everything else, left for a human

Operator-approved rules (2026-07-13).

AUTO-APPROVE only when ALL:
  1. Structured federal disclosure provenance: the source document comes from a
     search.open.canada.ca proactive-disclosure dataset (federal contract and
     grant awards). Authoritative government records the extractor reformats,
     not prose it interprets. CanadaBuys and every interpreted source (board
     minutes, news, program pages) are deliberately NOT structured here.
  2. confidence = confirmed.
  3. needs_org_resolution = false.
  4. Not high-stakes: materiality < 4 AND (amount_max_cad null or < $1,000,000).

AUTO-REJECT (rule AR1) only when ALL of the following hold at once -- the
weakest a signal can be on every axis simultaneously:
  * materiality = 1 (lowest importance), AND
  * confidence = speculative (lowest confidence), AND
  * amount_max_cad is null (no dollar figure at all), AND
  * NOT defence-tagged.
Auto-reject is deliberately narrow: a wrong auto-reject silently discards real
intelligence the operator never sees, which is worse than a wrong auto-approve.
So the four conditions are AND-ed, and defence_relevant is used only to SPARE a
signal (a defence-tagged record is never auto-rejected), never to reject one --
the collectors keep non-defence records on purpose, so "not defence" is not
evidence of noise.

Everything else FLAGS for a human.

Two invariants are non-negotiable (operator):
  * Every triage outcome stamps reviewed_by='triage@v1' (vs 'human'), so the
    record always shows which signals a person actually eyeballed. Auto-approve
    writes review_note='approved' and auto-reject writes a 'rejected: ...' note,
    exactly as a human approval/rejection would, so downstream consumers (the
    procurement proposer) treat them identically apart from the reviewer.
  * Triage touches ONLY the signal review state (reviewed, review_note,
    reviewed_by). It NEVER authors a prediction and NEVER confirms a
    procurement. The wall between triage and the ledger is absolute.

    python -m src.triage --dry-run   # classify and report counts, write nothing
    python -m src.triage --apply     # auto-approve the clean set + auto-reject noise
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

# AR1 auto-reject: the bottom of every axis at once.
AUTOREJECT_RULE = "AR1"
AUTOREJECT_MATERIALITY = 1
AUTOREJECT_NOTE = (
    "rejected: auto AR1 (materiality 1, speculative, no amount, non-defence)")


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def _int_materiality(signal, default=3):
    try:
        return int(signal.get("materiality") or default)
    except (TypeError, ValueError):
        return default


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
    mat = _int_materiality(signal)
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


def auto_reject_reason(signal: dict, defence_relevant) -> str | None:
    """Rule tag if this signal is conservatively safe to auto-reject, else None.
    AR1: weakest on every axis at once (see module docstring). defence_relevant
    only spares -- it never causes a rejection."""
    mat = _int_materiality(signal)
    conf = signal.get("confidence")
    amt = signal.get("amount_max_cad")
    if (mat == AUTOREJECT_MATERIALITY and conf == "speculative"
            and amt is None and defence_relevant is not True):
        return AUTOREJECT_RULE
    return None


def classify(signal: dict, source_url) -> str:
    """Back-compatible two-way label: 'auto_approve' or 'manual'. (The
    three-outcome decision is decide(); this is retained for callers/tests that
    only care whether a signal clears the auto-approve gates.)"""
    return "auto_approve" if not gate_failures(signal, source_url) else "manual"


def decide(signal: dict, source_url, defence_relevant) -> tuple:
    """The three-outcome decision: ('auto_approve'|'auto_reject'|'flag', reason).
    Auto-approve wins first (a clean record is never a reject candidate), then
    the conservative auto-reject, else flag for a human."""
    if not gate_failures(signal, source_url):
        return "auto_approve", "clean_structured"
    reason = auto_reject_reason(signal, defence_relevant)
    if reason:
        return "auto_reject", reason
    return "flag", "flag"


def run(dry_run: bool = True) -> dict:
    """Classify every unreviewed signal into auto_approve / auto_reject / flag.
    In --apply mode, write the two automated outcomes (both stamped
    reviewed_by=STAMP) and leave flagged signals for a human. Idempotent: only
    unreviewed signals are fetched, so a re-run never re-touches a decided row."""
    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,confidence,materiality,needs_org_resolution,amount_max_cad,"
        "documents(doc_type,source_id,defence_relevant)",
        {"reviewed": "is.false"})

    url_by_source = {s["id"]: s.get("url")
                     for s in supabase_client.fetch_rows("sources", "id,url")}

    by_doctype = Counter()          # (doc_type, outcome) -> count
    flag_reasons = {}               # doc_type -> Counter(gate -> count)
    to_approve = []                 # signal ids -> auto_approve
    to_reject = []                  # signal ids -> auto_reject
    for s in signals:
        doc = _one(s.get("documents")) or {}
        doc_type = doc.get("doc_type") or "unknown"
        src_url = url_by_source.get(doc.get("source_id"))
        outcome, _reason = decide(s, src_url, doc.get("defence_relevant"))
        by_doctype[(doc_type, outcome)] += 1
        if outcome == "auto_approve":
            to_approve.append(s["id"])
        elif outcome == "auto_reject":
            to_reject.append(s["id"])
        else:
            rc = flag_reasons.setdefault(doc_type, Counter())
            for f in gate_failures(s, src_url):
                rc[f] += 1

    outcomes = ("auto_approve", "auto_reject", "flag")
    doc_types = sorted({dt for (dt, _) in by_doctype})
    mode = "dry-run" if dry_run else "APPLY"
    log.info("Triage %s over %d unreviewed signals", mode, len(signals))
    log.info("%-16s %12s %12s %8s", "doc_type", "auto_approve", "auto_reject", "flag")
    tot = Counter()
    for dt in doc_types:
        row = tuple(by_doctype[(dt, o)] for o in outcomes)
        for o, c in zip(outcomes, row):
            tot[o] += c
        log.info("%-16s %12d %12d %8d", dt, *row)
    log.info("%-16s %12d %12d %8d", "TOTAL",
             tot["auto_approve"], tot["auto_reject"], tot["flag"])
    for dt in doc_types:
        rc = flag_reasons.get(dt)
        if not rc:
            continue
        log.info("why-flagged [%s]:", dt)
        for reason, n in rc.most_common():
            log.info("    %-24s %6d", reason, n)

    approved = rejected = 0
    if not dry_run:
        # ONLY the review state on each row. No prediction, no procurement --
        # the wall holds for both automated outcomes.
        for sid in to_approve:
            supabase_client.update_row("signals", sid, {
                "reviewed": True, "review_note": "approved", "reviewed_by": STAMP})
            approved += 1
        for sid in to_reject:
            supabase_client.update_row("signals", sid, {
                "reviewed": True, "review_note": AUTOREJECT_NOTE, "reviewed_by": STAMP})
            rejected += 1
        log.info("Applied: %d auto-approved, %d auto-rejected as %s; %d flagged "
                 "for manual review", approved, rejected, STAMP, tot["flag"])
    else:
        log.info("Summary: %d auto-approve, %d auto-reject, %d flag, of %d unreviewed",
                 tot["auto_approve"], tot["auto_reject"], tot["flag"], len(signals))

    return {"auto_approve": tot["auto_approve"], "auto_reject": tot["auto_reject"],
            "flag": tot["flag"], "approved": approved, "rejected": rejected,
            "examined": len(signals)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review triage (three outcomes)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="classify and report counts, write nothing")
    group.add_argument("--apply", action="store_true",
                       help="auto-approve clean records and auto-reject AR1 noise")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Default to dry-run: writing requires an explicit --apply.
    run(dry_run=not args.apply)
    sys.exit(0)
