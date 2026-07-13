"""Prediction reconciliation (Phase B, propose-only).

The fourth node of the loop: propose, predict, approve, RECONCILE. A weekly
job that reads open predictions and proposes an outcome for each, for human
confirmation. It never confirms, never settles a claim as 'incorrect' on its
own, and never touches the immutable prediction row. Its only write surface is
'proposed' rows in prediction_outcomes.

Two automatable outcomes (the deterministic cases):
  * correct  -- a PUBLIC signal on the subject reached the predicted rung (or
                higher) within the horizon window [made_at date, horizon_ends_on].
                The settling document is the public evidence that closed it, and
                the earliest such signal is chosen so lead-time (how far ahead of
                the market the call was) is measured honestly.
  * expired  -- the horizon has passed with no settling evidence. Deliberately
                NOT 'incorrect': a procurement can simply be delayed, so the
                honest auto-state is expired, and a human confirms or overrides
                to incorrect (operator decision Q3).

Everything else (partial, incorrect, unresolved) is a human judgment the
reviewer records; reconcile does not guess them.

The confirming bar honors Q4: a claim predicts a strong rung (commitment or
higher), and only a signal at or above that rung settles it. Chatter and
intent (press releases, MOUs) can never close a claim.

Idempotent: a prediction that already has a confirmed terminal outcome is
skipped, and an outcome equivalent to one already proposed is not re-proposed,
so the weekly job never nags.

    python -m src.reconcile --dry-run
"""
import argparse
import logging
import sys
from datetime import date
from typing import Optional

from . import supabase_client

log = logging.getLogger(__name__)

STAMP = "reconcile@v1"
TERMINAL_OUTCOMES = {"correct", "partial", "incorrect", "expired"}


def _one(embedded):
    if isinstance(embedded, list):
        return embedded[0] if embedded else None
    return embedded


def decide_outcome(prediction: dict, subject_signals: list, today: date) -> Optional[tuple]:
    """Pure reconciliation decision for one prediction.

    subject_signals: dicts with evidence_grade, published_on (the document
    event date, YYYY-MM-DD or None), and document_id. Returns
    (outcome, settling_document_id, settling_published_on) or None when the
    claim is still open. The settling event date is returned so it can be
    FROZEN into the outcome at proposal, fixing lead-time at settlement.
    """
    predicted = prediction.get("predicted_rung")
    made_on = str(prediction.get("made_at") or "")[:10]
    horizon_end = str(prediction.get("horizon_ends_on") or "")

    # correct: earliest public signal at/above the predicted rung, with an event
    # date inside the window. Sorting by published_on makes lead-time honest.
    settling = [
        s for s in subject_signals
        if isinstance(s.get("evidence_grade"), int)
        and s["evidence_grade"] >= predicted
        and s.get("published_on")
        and made_on <= str(s["published_on"])[:10] <= horizon_end
    ]
    if settling:
        settling.sort(key=lambda s: str(s["published_on"]))
        winner = settling[0]
        return ("correct", winner.get("document_id"),
                str(winner["published_on"])[:10])

    if horizon_end and horizon_end < today.isoformat():
        return ("expired", None, None)

    return None   # still open, within horizon, no settling evidence yet


def _subject_signals(prediction: dict) -> list:
    """The public signals that could settle a prediction, by subject_kind.

    procurement: the signals linked to the subject procurement (the proposer
    keeps attaching new evidence as it arrives).
    organization_category: signals for that buyer in that category.
    Each returned dict carries evidence_grade, the document event date, and the
    document id.
    """
    kind = prediction.get("subject_kind")
    rows: list = []
    if kind == "procurement":
        links = supabase_client.fetch_all_rows_where(
            "procurement_signals",
            "active,signals(evidence_grade,documents(id,published_on))",
            {"procurement_id": f"eq.{prediction['subject_procurement_id']}",
             "active": "is.true"})
        for l in links:
            sig = _one(l.get("signals"))
            if sig:
                rows.append(sig)
    elif kind == "organization_category":
        filters = {"organization_id": f"eq.{prediction['subject_organization_id']}",
                   "evidence_grade": "not.is.null"}
        if prediction.get("subject_category_id"):
            filters["category_id"] = f"eq.{prediction['subject_category_id']}"
        rows = supabase_client.fetch_all_rows_where(
            "signals", "evidence_grade,documents(id,published_on)", filters)

    out = []
    for sig in rows:
        doc = _one(sig.get("documents")) or {}
        out.append({"evidence_grade": sig.get("evidence_grade"),
                    "published_on": doc.get("published_on"),
                    "document_id": doc.get("id")})
    return out


def _existing_outcomes(prediction_id: str) -> list:
    return supabase_client.fetch_all_rows_where(
        "prediction_outcomes", "outcome,status",
        {"prediction_id": f"eq.{prediction_id}"})


def run(dry_run: bool = False) -> int:
    stats = {"examined": 0, "proposed_correct": 0, "proposed_expired": 0,
             "still_open": 0, "skipped_closed": 0, "skipped_existing": 0, "errors": 0}
    today = date.today()

    predictions = supabase_client.fetch_all_rows_where(
        "predictions",
        "id,subject_kind,subject_procurement_id,subject_organization_id,"
        "subject_category_id,predicted_rung,made_at,horizon_ends_on",
        {})

    for pred in predictions:
        stats["examined"] += 1
        try:
            existing = _existing_outcomes(pred["id"])
            # A confirmed terminal outcome closes the claim for good.
            if any(o.get("status") == "confirmed" and o.get("outcome") in TERMINAL_OUTCOMES
                   for o in existing):
                stats["skipped_closed"] += 1
                continue

            decision = decide_outcome(pred, _subject_signals(pred), today)
            if decision is None:
                stats["still_open"] += 1
                continue
            outcome, settling_doc, settling_published_on = decision

            # Don't re-propose the same outcome the job already proposed.
            if any(o.get("outcome") == outcome for o in existing):
                stats["skipped_existing"] += 1
                continue

            payload = {
                "prediction_id": pred["id"],
                "outcome": outcome,
                "settling_document_id": settling_doc,
                # Freeze the settling event date at proposal so lead-time cannot
                # move if the source document is later edited.
                "settling_published_on": settling_published_on,
                "resolved_on": today.isoformat(),
                "status": "proposed",
                "proposed_by": STAMP,
            }
            if dry_run:
                log.info("[dry-run] would PROPOSE %s for prediction %s%s",
                         outcome, pred["id"],
                         f" (settled by doc {settling_doc})" if settling_doc else "")
            else:
                supabase_client.insert_row("prediction_outcomes", payload)
            stats["proposed_correct" if outcome == "correct" else "proposed_expired"] += 1
        except Exception:   # noqa: BLE001 - one bad prediction must not kill the run
            log.exception("Error reconciling prediction %s", pred.get("id"))
            stats["errors"] += 1

    log.info("Reconcile%s: %s", " (DRY RUN)" if dry_run else "", stats)
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prediction reconciliation (propose-only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="decide and log proposals, write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(dry_run=args.dry_run))
