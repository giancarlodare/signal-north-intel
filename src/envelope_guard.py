"""The pre-dispatch envelope guardrail (operator 2026-07-29).

Per-host token logging MEASURES spend. It does not BIND it. This module is
the binding half: before any extract-backfill batch runs, it compares
cumulative measured spend for that envelope against the declared number and,
if the batch would exceed it, the batch does not run.

    "The check is what makes an envelope an envelope."

THREE OUTCOMES, and the difference between the second and third is the whole
point:

  PROCEED     spend_to_date + this batch's projection fits inside declared.
  SKIP        it does not fit. Exit 0, print the arithmetic, set
              proceed=false. The workflow's extraction step is gated on that
              output, so the batch is skipped and surfaced, not run.
  UNMEASURABLE  the envelope is unknown, the ledger is unreadable, or the
              envelope's spend has never been measured. Raise, non-zero exit,
              red run. An envelope whose spend cannot be measured cannot be
              certified, and a guard that treats "I don't know" as zero is
              not a guard. This is why the Toronto envelope seeds as
              status='unmeasured' rather than as $0 spent: its batches ran
              before per-run token logging existed, and pretending that spend
              was zero would silently re-authorize the whole $63.

The per-doc rate is MEASURED from the envelope's own ledger rows (cumulative
cost / cumulative docs), not assumed. An envelope with no runs yet uses its
declared seed rate, which is itself a measured figure carried over from the
batch that established it.

    python -m src.envelope_guard --envelope tier3-awarded --planned-docs 200
    python -m src.envelope_guard --envelope tier3-awarded --planned-docs 200 --json
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

from . import supabase_client

log = logging.getLogger(__name__)

# Anthropic list prices, USD per million tokens. Mirrors the constants in
# scripts/compare_extraction_v3.py; kept literal here so a spend row can be
# recomputed from its own token counts years later.
RATES = {
    "claude-opus-4-8": {"input": 5.00, "output": 25.00,
                        "cache_write": 6.25, "cache_read": 0.50},
    "claude-opus-5": {"input": 5.00, "output": 25.00,
                      "cache_write": 6.25, "cache_read": 0.50},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00,
                        "cache_write": 3.75, "cache_read": 0.30},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00,
                         "cache_write": 1.25, "cache_read": 0.10},
}
DEFAULT_RATE_MODEL = "claude-opus-4-8"

ENVELOPES_TABLE = "extraction_envelopes"
SPEND_TABLE = "extraction_spend"


class EnvelopeUnmeasurable(RuntimeError):
    """The guard cannot certify this batch. Never downgraded to a warning."""


def cost_usd(usage: dict, model: str) -> float:
    """USD for one run's token counts at the model's list price."""
    r = RATES.get(model) or RATES[DEFAULT_RATE_MODEL]
    return (usage.get("input_tokens", 0) * r["input"]
            + usage.get("output_tokens", 0) * r["output"]
            + usage.get("cache_write_tokens", 0) * r["cache_write"]
            + usage.get("cache_read_tokens", 0) * r["cache_read"]) / 1e6


def _envelope(key: str) -> dict:
    try:
        rows = supabase_client.fetch_rows_where(
            ENVELOPES_TABLE,
            "key,label,declared_usd,seed_rate_usd_per_doc,status,approved_on",
            {"key": f"eq.{key}"}, limit=2)
    except Exception as e:  # noqa: BLE001 - a missing table must be loud
        raise EnvelopeUnmeasurable(
            f"cannot read {ENVELOPES_TABLE} ({e}); the guard cannot certify "
            f"this batch, so it does not run. Paste the "
            f"2026-07-29_extraction_envelopes migration.") from e
    if not rows:
        raise EnvelopeUnmeasurable(
            f"no envelope declared under key {key!r}. An undeclared envelope "
            f"is not an envelope; declare it with an operator-approved amount "
            f"before dispatching against it.")
    return rows[0]


def _spend_to_date(key: str) -> tuple[float, int, int]:
    """(usd, docs, runs) measured against this envelope."""
    try:
        rows = supabase_client.fetch_all_rows_where(
            SPEND_TABLE, "cost_usd,documents_processed", {"envelope": f"eq.{key}"})
    except Exception as e:  # noqa: BLE001
        raise EnvelopeUnmeasurable(
            f"cannot read {SPEND_TABLE} ({e}); spend to date is unknown and "
            f"unknown is not zero.") from e
    usd = sum(float(r.get("cost_usd") or 0) for r in rows)
    docs = sum(int(r.get("documents_processed") or 0) for r in rows)
    return usd, docs, len(rows)


def check(key: str, planned_docs: int) -> dict:
    """Decide whether a batch of `planned_docs` may run against `key`.

    Raises EnvelopeUnmeasurable when the answer cannot be measured. Returns a
    decision dict otherwise; callers gate on decision["proceed"].
    """
    env = _envelope(key)
    status = (env.get("status") or "").lower()
    declared = float(env.get("declared_usd") or 0)
    if declared <= 0:
        raise EnvelopeUnmeasurable(
            f"envelope {key!r} declares {declared}; a zero or absent ceiling "
            f"cannot bind anything.")
    if status == "closed":
        raise EnvelopeUnmeasurable(
            f"envelope {key!r} is CLOSED. Reopening it is an operator "
            f"decision, not a dispatch-time one.")

    spent, docs_done, runs = _spend_to_date(key)
    if status == "unmeasured":
        raise EnvelopeUnmeasurable(
            f"envelope {key!r} is marked UNMEASURED: batches ran against it "
            f"before per-run token logging existed, so ${spent:,.2f} over "
            f"{runs} logged run(s) is a floor, not the total. The guard will "
            f"not treat an unknown as zero. Re-declare this envelope with a "
            f"fresh operator-approved amount, or reconcile the missing runs "
            f"into {SPEND_TABLE} first.")

    seed_rate = float(env.get("seed_rate_usd_per_doc") or 0)
    if docs_done > 0:
        rate = spent / docs_done
        rate_basis = f"measured over {docs_done} docs in {runs} run(s)"
    elif seed_rate > 0:
        rate = seed_rate
        rate_basis = "declared seed rate (no runs logged yet)"
    else:
        raise EnvelopeUnmeasurable(
            f"envelope {key!r} has no logged runs and no seed rate, so this "
            f"batch cannot be priced before it runs.")

    projected = planned_docs * rate
    remaining = declared - spent
    proceed = (spent + projected) <= declared
    return {
        "envelope": key,
        "label": env.get("label"),
        "declared_usd": round(declared, 2),
        "spent_usd": round(spent, 2),
        "remaining_usd": round(remaining, 2),
        "rate_usd_per_doc": round(rate, 6),
        "rate_basis": rate_basis,
        "planned_docs": planned_docs,
        "projected_usd": round(projected, 2),
        "would_total_usd": round(spent + projected, 2),
        "proceed": proceed,
        "docs_affordable": int(remaining / rate) if rate > 0 else 0,
    }


def record_run(key: str, model: str, usage: dict, documents_processed: int,
               usage_by_host: dict | None = None,
               run_url: str | None = None) -> None:
    """Append this run's MEASURED spend to the ledger.

    Called at the end of a real (non-dry-run) extraction. A failure to record
    is raised, not swallowed: an unrecorded run is exactly the hole that made
    the Toronto envelope unmeasurable in the first place.
    """
    payload = {
        "envelope": key,
        "model": model,
        "documents_processed": documents_processed,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_write_tokens": usage.get("cache_write_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_tokens", 0),
        "cost_usd": round(cost_usd(usage, model), 4),
        "usage_by_host": usage_by_host or {},
        "run_url": run_url,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    supabase_client.insert_row(SPEND_TABLE, payload)
    log.info("Envelope %s: recorded $%.4f over %d docs",
             key, payload["cost_usd"], documents_processed)


def _emit_github_output(decision: dict) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"proceed={'true' if decision['proceed'] else 'false'}\n")
        fh.write(f"projected_usd={decision['projected_usd']}\n")
        fh.write(f"spent_usd={decision['spent_usd']}\n")
        fh.write(f"declared_usd={decision['declared_usd']}\n")
        fh.write(f"docs_affordable={decision['docs_affordable']}\n")


def main() -> int:
    p = argparse.ArgumentParser(description="Pre-dispatch envelope guardrail")
    p.add_argument("--envelope", required=True,
                   help="the declared envelope key this batch spends against")
    p.add_argument("--planned-docs", type=int, required=True,
                   help="the batch's document cap (its worst-case doc count)")
    p.add_argument("--json", action="store_true", help="emit the decision as JSON")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    decision = check(args.envelope, args.planned_docs)
    if args.json:
        print(json.dumps(decision, indent=2))
    else:
        d = decision
        print("=" * 72)
        print(f"ENVELOPE GUARD  {d['envelope']}  ({d['label']})")
        print("=" * 72)
        print(f"  declared          ${d['declared_usd']:>10,.2f}")
        print(f"  spent to date     ${d['spent_usd']:>10,.2f}")
        print(f"  remaining         ${d['remaining_usd']:>10,.2f}")
        print(f"  rate per doc      ${d['rate_usd_per_doc']:>10.4f}   "
              f"({d['rate_basis']})")
        print(f"  this batch        {d['planned_docs']:>11d} docs "
              f"-> ${d['projected_usd']:,.2f}")
        print(f"  would total       ${d['would_total_usd']:>10,.2f}")
        print("-" * 72)
        if d["proceed"]:
            print(f"  PROCEED. Fits with ${d['remaining_usd'] - d['projected_usd']:,.2f} "
                  f"left in the envelope.")
        else:
            print(f"  SKIP. This batch would exceed the declared envelope by "
                  f"${d['would_total_usd'] - d['declared_usd']:,.2f}.")
            print(f"  The envelope affords {d['docs_affordable']} more docs at "
                  f"the measured rate. Either lower the cap to that, or bring "
                  f"the operator a new envelope.")
    _emit_github_output(decision)
    # SKIP is a clean outcome, not a failure: exit 0 so the run is green and
    # the skip is surfaced, per the operator's "skip and surface rather than
    # run". Only UNMEASURABLE (raised above) turns the run red.
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EnvelopeUnmeasurable as e:
        print(f"\nENVELOPE GUARD: UNMEASURABLE -- batch not dispatched.\n  {e}",
              file=sys.stderr)
        raise SystemExit(2)
