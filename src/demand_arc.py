"""Per-jurisdiction demand-arc backtest engine (docs/demand-arc-backtest-design.md).

Walks each procurement's linked signals up the demand-strength ladder
(evidence_grade 1..5 = chatter, intent, commitment, in_market, awarded) and
measures the lag in days between the earliest signal at each rung and the next.
Aggregated per service (organization), the lag distribution is that service's
measured demand rhythm; the intent->awarded and commitment->awarded spans are
its calibrated prediction horizons.

Read-only analysis, no LLM. It reads whatever award history is extracted so far
and calibrates continuously: as the Toronto/Peel/board award backlog drains and
the upstream intent layer lands, n grows and the bands tighten. Sample size is
reported per transition so a thin arc is never mistaken for a confident one;
below MIN_N a horizon is labeled insufficient, never a fabricated number.

    python -m src.demand_arc --dry-run   # compute + print, write nothing
    python -m src.demand_arc             # compute + upsert demand_arc_profiles
"""
import argparse
import logging
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional

from . import supabase_client

log = logging.getLogger(__name__)

GRADE_LABEL = {1: "chatter", 2: "intent", 3: "commitment", 4: "in_market",
               5: "awarded"}
MIN_N = 8   # below this a per-transition horizon is "insufficient", not reported as fact


def _iso_day(value) -> Optional[str]:
    if not value:
        return None
    try:
        return str(value)[:10]
    except Exception:
        return None


def _days_between(a: str, b: str) -> Optional[int]:
    try:
        da = date.fromisoformat(a)
        db = date.fromisoformat(b)
        return (db - da).days
    except Exception:
        return None


def earliest_by_grade(signals: list) -> dict:
    """{evidence_grade: earliest_iso_day} over a procurement's linked signals.
    A signal with no date is skipped for lag math (never fabricate a date)."""
    out: dict = {}
    for s in signals:
        g = s.get("evidence_grade")
        d = _iso_day(s.get("published_on"))
        if g is None or d is None:
            continue
        if g not in out or d < out[g]:
            out[g] = d
    return out


def transitions(earliest: dict) -> list:
    """(from_grade, to_grade, lag_days) for each step between consecutive
    PRESENT rungs, plus the headline intent->awarded (2->5) and
    commitment->awarded (3->5) spans when both ends exist. A gap (e.g. 2 then
    5, no 3/4) is recorded honestly as from=2,to=5, distinct from 4->5."""
    grades = sorted(earliest)
    out = []
    for i in range(len(grades) - 1):
        g, h = grades[i], grades[i + 1]
        lag = _days_between(earliest[g], earliest[h])
        if lag is not None and lag >= 0:
            out.append((g, h, lag))
    for lo, hi in ((2, 5), (3, 5)):
        if lo in earliest and hi in earliest and not (lo, hi) in [(a, b) for a, b, _ in out]:
            lag = _days_between(earliest[lo], earliest[hi])
            if lag is not None and lag >= 0:
                out.append((lo, hi, lag))
    return out


def _percentile(sorted_vals: list, p: float) -> int:
    if not sorted_vals:
        return 0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac)


def aggregate(per_org_transition: dict) -> list:
    """{(org_id, from, to): [lags]} -> profile rows with n + percentiles."""
    rows = []
    for (org_id, g, h), lags in per_org_transition.items():
        sv = sorted(lags)
        rows.append({
            "organization_id": org_id,
            "from_grade": g, "to_grade": h,
            "n": len(sv),
            "lag_median_days": _percentile(sv, 0.5),
            "lag_p25": _percentile(sv, 0.25),
            "lag_p75": _percentile(sv, 0.75),
            "lag_p90": _percentile(sv, 0.90),
        })
    return rows


def _load_spine() -> tuple:
    """(procurement_buyer: {proc_id: org_id}, links: [{procurement_id, signals}])."""
    procs = supabase_client.fetch_all_rows_where(
        "procurements", "id,buyer_organization_id,status",
        {"status": "neq.merged"})
    buyer = {p["id"]: p.get("buyer_organization_id") for p in procs}
    links = supabase_client.fetch_all_rows_where(
        "procurement_signals",
        "procurement_id,active,signals(evidence_grade,organization_id,documents(published_on))",
        {"active": "is.true"})
    return buyer, links


def _one(embedded):
    if isinstance(embedded, list):
        return embedded[0] if embedded else None
    return embedded


def compute(buyer: dict, links: list) -> tuple:
    """Group signals per procurement, walk the ladder, attribute to the org,
    and collect lags per (org, transition). Returns (profile_rows, coverage)."""
    per_proc = defaultdict(list)
    per_proc_org = defaultdict(lambda: defaultdict(int))
    for l in links:
        pid = l.get("procurement_id")
        sig = _one(l.get("signals"))
        if not pid or not sig:
            continue
        doc = _one(sig.get("documents")) or {}
        per_proc[pid].append({"evidence_grade": sig.get("evidence_grade"),
                              "published_on": doc.get("published_on")})
        if sig.get("organization_id"):
            per_proc_org[pid][sig["organization_id"]] += 1

    per_org_transition = defaultdict(list)
    coverage = {"procurements": 0, "with_transition": 0}
    for pid, signals in per_proc.items():
        coverage["procurements"] += 1
        earliest = earliest_by_grade(signals)
        trs = transitions(earliest)
        if not trs:
            continue
        coverage["with_transition"] += 1
        org_id = buyer.get(pid)
        if not org_id and per_proc_org[pid]:
            org_id = max(per_proc_org[pid].items(), key=lambda kv: kv[1])[0]
        for g, h, lag in trs:
            per_org_transition[(org_id, g, h)].append(lag)
    return aggregate(per_org_transition), coverage


def _org_names(org_ids: set) -> dict:
    if not org_ids:
        return {}
    rows = supabase_client.fetch_rows("organizations", "id,canonical_name")
    return {r["id"]: r.get("canonical_name") for r in rows if r["id"] in org_ids}


def _report(profiles: list, coverage: dict) -> None:
    names = _org_names({p["organization_id"] for p in profiles if p["organization_id"]})
    by_org = defaultdict(list)
    for p in profiles:
        by_org[p["organization_id"]].append(p)
    log.info("DEMAND-ARC: %d procurements, %d with a measurable transition; "
             "%d (org, transition) profiles",
             coverage["procurements"], coverage["with_transition"], len(profiles))
    for org_id, rows in sorted(by_org.items(),
                               key=lambda kv: -sum(r["n"] for r in kv[1])):
        label = names.get(org_id) or (org_id or "(unattributed)")
        log.info("  SERVICE: %s", label)
        for r in sorted(rows, key=lambda r: (r["from_grade"], r["to_grade"])):
            tr = f"{GRADE_LABEL.get(r['from_grade'], r['from_grade'])}->" \
                 f"{GRADE_LABEL.get(r['to_grade'], r['to_grade'])}"
            note = "" if r["n"] >= MIN_N else "  [INSUFFICIENT n<%d]" % MIN_N
            log.info("    %-22s n=%-4d median=%-5s p25=%-5s p75=%-5s p90=%-5s days%s",
                     tr, r["n"], r["lag_median_days"], r["lag_p25"], r["lag_p75"],
                     r["lag_p90"], note)


def run(dry_run: bool = True) -> dict:
    buyer, links = _load_spine()
    profiles, coverage = compute(buyer, links)
    _report(profiles, coverage)
    if not dry_run:
        now = datetime.now(timezone.utc).isoformat()
        for p in profiles:
            payload = dict(p, computed_at=now)
            supabase_client.insert_row("demand_arc_profiles", payload)
        log.info("demand-arc: wrote %d profile rows", len(profiles))
    else:
        log.info("demand-arc: %d profiles (DRY RUN, nothing written)", len(profiles))
    return {"profiles": len(profiles), **coverage}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Per-jurisdiction demand-arc backtest")
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and print, write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(dry_run=args.dry_run)
    sys.exit(0)
