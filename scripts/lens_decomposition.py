"""LENS SCORE DECOMPOSITION (operator 2026-08-02). Report only, changes
nothing, writes nothing, calls no LLM.

The operator's question: expose the ranking factors as they exist, and show
for the current cycle's top 30 exactly which factor put each item where it
is -- specifically whether contract value is the dominant factor carrying
watermains over records-management procurements.

THE MECHANISM BEING EXPOSED (src/brief_generator.py, verified in source):
ranking is a LEXICOGRAPHIC sort, not a weighted sum. The tuple, in order:

  1. timing_path      imminent before recent (binary)
  2. soonest_date     ascending
  3. -grade           evidence grade of the LEAD signal, descending
  4. -materiality     LLM-assigned 1..5 on the lead, descending
  5. -amount          lead amount_max_cad, descending -- LAST tiebreaker

Inclusion (the lens) is separate from rank: defence_relevant OR
(public_safety AND max member materiality >= 4).

A later factor matters only when every earlier factor ties, so "which
factor decided" is a real question with a real answer per adjacent pair:
this prints, for each of the top 30 included clusters, the full tuple and
which position separated it from the cluster below it, plus a tally of
deciding positions. That tally IS the dominance measurement.

Reuses the generator's own select/cluster/apply_lens so this cannot drift
from what the brief actually does.
"""
import os
import sys
from collections import Counter
from datetime import date

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from src import supabase_client as sc  # noqa: E402
from src.brief_generator import (  # noqa: E402
    _one, _procurement_by_signal, apply_lens, cluster, select)


def main() -> None:
    today = date.today()
    print(f"LENS DECOMPOSITION -- current cycle, today={today} (report only)")

    signals = sc.fetch_all_rows_where(
        "signals",
        "id,signal_type,confidence,materiality,evidence_grade,amount_max_cad,"
        "expected_timing,organization_id,title,"
        "organizations(canonical_name,org_type),categories(slug),document_id,"
        "documents!inner(doc_type,published_on,date_precision,url,"
        "defence_relevant,buyer_name)",
        {"suppressed": "is.false"})
    included, excluded, breakdown = select(signals, today)
    clusters = cluster(included, _procurement_by_signal())
    held = apply_lens(clusters)
    print(f"live signals {len(signals)}; in-window+above-bar {len(included)}; "
          f"clusters {len(clusters)}; lens-held {held} "
          f"(excluded at bar: {excluded} {breakdown})")

    # Category + buyer for display, from the lead signal.
    by_id = {s["id"]: s for s in signals}
    def describe(c):
        lead = by_id.get(c["lead_signal_id"]) or {}
        cat = _one(lead.get("categories")) or {}
        doc = _one(lead.get("documents")) or {}
        return (cat.get("slug") or "(uncategorized)",
                c.get("org") or doc.get("buyer_name") or "(no buyer)")

    def tup(c):
        return (0 if c["timing_path"] == "imminent" else 1,
                c["soonest_date"] or date.max,
                -(c["grade"] or 0), -(c["materiality"] or 0),
                -(c["amount"] or 0.0))

    NAMES = ("timing_path", "soonest_date", "grade", "materiality", "amount")
    inc = [c for c in clusters if c.get("included")]
    top = inc[:30]
    deciders: Counter = Counter()

    print(f"\nTOP {len(top)} INCLUDED CLUSTERS (of {len(inc)}):")
    print(f"{'rank':>4} {'path':8} {'date':10} {'gr':>2} {'mat':>3} "
          f"{'amount':>12}  decided-by-next")
    for i, c in enumerate(top):
        cat, buyer = describe(c)
        decided = ""
        if i + 1 < len(top):
            a, b = tup(c), tup(top[i + 1])
            for pos, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    decided = NAMES[pos]
                    deciders[decided] += 1
                    break
            else:
                decided = "(full tie)"
        print(f"{c['rank']:>4} {c['timing_path']:8} "
              f"{str(c['soonest_date']):10} {c['grade']:>2} "
              f"{c['materiality']:>3} {c['amount']:>12,.0f}  {decided}")
        print(f"     {buyer} | {cat} | {c['doc_type']} | "
              f"ps={c['public_safety']} def={c['defence_relevant']} "
              f"max_mat={c['max_materiality']}")
        print(f"     {(c['lead_title'] or '')[:110]!r}")

    print("\nWHICH TUPLE POSITION SEPARATES ADJACENT PAIRS (top 30):")
    for name in NAMES:
        print(f"  {name:14s} {deciders.get(name, 0):3d}")
    n_amt = sum(1 for c in top if (c['amount'] or 0) > 0)
    print(f"\nclusters in top 30 carrying ANY dollar amount: {n_amt}")
    print("\nreport complete (read-only; nothing written)")


if __name__ == "__main__":
    main()
