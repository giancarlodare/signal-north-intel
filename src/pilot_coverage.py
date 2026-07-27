"""Pilot coverage report (operator 2026-07-27): the artifact the fleet-drain
decision rests on.

Implements doctrine 0g (docs/demand-arc-backtest-design.md): every transition
observation is classified CONFIRMATION (same-document or 0-day agenda->minutes
pair; arc-validating, no predictive lead time) or LONG-LAG (cross-document,
real calendar span; the sellable signal). A cell's n is split into
(confirmation_n, longlag_n), and the significance gate runs on LONG-LAG only,
so confirmation-pair volume never dresses a cell as predictive.

Then it classifies each cell for the fleet decision, the operator's specific
question ("one deep-drain from n=8 vs structurally thin"):
  PUBLISHED  longlag_n >= MIN_N and the CI is tight
  CLOSE      1 <= longlag_n < MIN_N: real forward observations exist, so more
             history plausibly reaches significance (a drain likely buys it)
  THIN       longlag_n == 0: no forward long-lag arc exists in linkable form
             (all confirmation pairs or backwards-ordered), so a drain adds
             volume with NO evidence the sellable arc is reachable (high risk
             it lands thin per cell)

Read-only, no LLM. This does NOT decide the drain; it gives the operator the
numbers to decide.

    python -m src.pilot_coverage
"""
import logging
import sys
from collections import defaultdict

from . import demand_arc as da
from . import supabase_client

log = logging.getLogger(__name__)

PILOT_MARKERS = ("toronto", "peel")


def _one(embedded):
    if isinstance(embedded, list):
        return embedded[0] if embedded else None
    return embedded


def load_pilot_spine() -> tuple:
    """(buyer, links) restricted to Toronto+Peel procurements, each signal
    carrying its document id and date so we can classify same-document pairs."""
    procs = supabase_client.fetch_all_rows_where(
        "procurements", "id,buyer_organization_id,status",
        {"status": "neq.merged"})
    buyer = {p["id"]: p.get("buyer_organization_id") for p in procs}
    links = supabase_client.fetch_all_rows_where(
        "procurement_signals",
        "procurement_id,active,"
        "signals(evidence_grade,organization_id,document_id,"
        "organizations(canonical_name),documents(published_on))",
        {"active": "is.true"})
    return buyer, links


def is_pilot(sig: dict) -> bool:
    org = (_one(sig.get("organizations")) or {}).get("canonical_name") or ""
    return any(m in org.lower() for m in PILOT_MARKERS)


def earliest_with_doc(signals: list) -> dict:
    """{grade: (iso_day, document_id)} earliest per rung, keeping the document
    the earliest date came from so a same-document transition is detectable."""
    out: dict = {}
    for s in signals:
        g = s.get("evidence_grade")
        d = da._iso_day(s.get("published_on"))
        if g is None or d is None:
            continue
        if g not in out or d < out[g][0]:
            out[g] = (d, s.get("document_id"))
    return out


def classify_transitions(earliest: dict) -> list:
    """(from, to, lag, kind) per transition. kind='confirmation' when the two
    rungs share a document OR lag==0 (0-day board pair); else 'longlag'."""
    dates = {g: v[0] for g, v in earliest.items()}
    docs = {g: v[1] for g, v in earliest.items()}
    out = []
    for g, h, lag in da.transitions(dates):
        same_doc = docs.get(g) is not None and docs.get(g) == docs.get(h)
        kind = "confirmation" if (same_doc or lag == 0) else "longlag"
        out.append((g, h, lag, kind))
    return out


def compute_coverage(buyer: dict, links: list) -> list:
    per_proc = defaultdict(list)
    per_proc_org = defaultdict(lambda: defaultdict(int))
    for l in links:
        sig = _one(l.get("signals"))
        pid = l.get("procurement_id")
        if not sig or not pid or not is_pilot(sig):
            continue
        doc = _one(sig.get("documents")) or {}
        per_proc[pid].append({
            "evidence_grade": sig.get("evidence_grade"),
            "published_on": doc.get("published_on"),
            "document_id": sig.get("document_id"),
        })
        if sig.get("organization_id"):
            per_proc_org[pid][sig["organization_id"]] += 1

    cells = defaultdict(lambda: {"confirmation": [], "longlag": []})
    for pid, signals in per_proc.items():
        e = earliest_with_doc(signals)
        org_id = buyer.get(pid) or (
            max(per_proc_org[pid].items(), key=lambda kv: kv[1])[0]
            if per_proc_org[pid] else None)
        for g, h, lag, kind in classify_transitions(e):
            cells[(org_id, g, h)][kind].append(lag)

    rows = []
    for (org_id, g, h), obs in cells.items():
        ll = sorted(obs["longlag"])
        cn = len(obs["confirmation"])
        ln = len(ll)
        med = da._percentile(ll, 0.5) if ll else 0
        ci_low, ci_high = da.bootstrap_median_ci(ll)
        sig = da.significance(ln, med, ci_low, ci_high)
        if sig == "published":
            klass = "PUBLISHED"
        elif ln == 0:
            klass = "THIN"          # no forward long-lag arc exists
        else:
            klass = "CLOSE"         # real forward obs, needs more history
        rows.append({
            "organization_id": org_id, "from_grade": g, "to_grade": h,
            "confirmation_n": cn, "longlag_n": ln,
            "longlag_median_days": med, "ci_low": ci_low, "ci_high": ci_high,
            "significance": sig, "fleet_class": klass,
            "gap_to_min_n": max(0, da.MIN_N - ln),
        })
    return rows


def _org_names(ids: set) -> dict:
    if not ids:
        return {}
    rows = supabase_client.fetch_rows("organizations", "id,canonical_name")
    return {r["id"]: r.get("canonical_name") for r in rows if r["id"] in ids}


def report(rows: list) -> None:
    names = _org_names({r["organization_id"] for r in rows if r["organization_id"]})
    klass_count = defaultdict(int)
    for r in rows:
        klass_count[r["fleet_class"]] += 1

    log.info("=" * 70)
    log.info("PILOT COVERAGE REPORT (Toronto + Peel), doctrine 0g split")
    log.info("=" * 70)
    log.info("cells: %d total | PUBLISHED %d | CLOSE (1<=longlag_n<%d, a drain "
             "plausibly reaches significance) %d | THIN (longlag_n=0, no "
             "forward arc, drain risks landing thin) %d",
             len(rows), klass_count["PUBLISHED"], da.MIN_N,
             klass_count["CLOSE"], klass_count["THIN"])
    log.info("")
    for r in sorted(rows, key=lambda r: (r["fleet_class"] != "CLOSE",
                                         -r["longlag_n"], -r["confirmation_n"])):
        label = names.get(r["organization_id"]) or (r["organization_id"] or "(unattributed)")
        tr = f"{da.GRADE_LABEL.get(r['from_grade'])}->{da.GRADE_LABEL.get(r['to_grade'])}"
        verdict = (f"median={r['longlag_median_days']}d CI[{r['ci_low']},{r['ci_high']}]"
                   if r["longlag_n"] else "no long-lag obs")
        log.info("  [%-6s] %-32s %-20s confirm_n=%-3d longlag_n=%-3d "
                 "(need +%d for n=%d) %s",
                 r["fleet_class"], label[:32], tr, r["confirmation_n"],
                 r["longlag_n"], r["gap_to_min_n"], da.MIN_N, verdict)

    close = [r for r in rows if r["fleet_class"] == "CLOSE"]
    log.info("")
    log.info("FLEET-DECISION SUMMARY:")
    log.info("  %d cells are CLOSE (one deep-drain plausibly reaches n=%d): "
             "these are where drain spend buys significance.", len(close), da.MIN_N)
    log.info("  %d cells are THIN (longlag_n=0): a drain adds history but no "
             "forward arc is present, so significance is NOT assured.",
             klass_count["THIN"])
    if close:
        avg_gap = sum(r["gap_to_min_n"] for r in close) / len(close)
        log.info("  Average additional long-lag observations the CLOSE cells "
                 "need: %.1f each.", avg_gap)


def run() -> dict:
    buyer, links = load_pilot_spine()
    rows = compute_coverage(buyer, links)
    report(rows)
    return {"cells": len(rows),
            "close": sum(1 for r in rows if r["fleet_class"] == "CLOSE"),
            "thin": sum(1 for r in rows if r["fleet_class"] == "THIN"),
            "published": sum(1 for r in rows if r["fleet_class"] == "PUBLISHED")}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run()
    logging.getLogger(__name__).info("coverage: %s", result)
    sys.exit(0)
