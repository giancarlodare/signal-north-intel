"""CIVIL-WORKS FALSE-POSITIVE COUNT (operator 2026-08-02). Read-only,
applies nothing.

The instance: a Region of Durham sewer rehabilitation tender ("CIPP lining
and CCTV inspection") flagged public safety, because CCTV there is a
pipe-inspection camera. Third civil-works surfacing (Toronto and Ottawa
watermain items dominate the brief lens ranking). The ruling that frames
this: capture wide, gate narrow, the narrow gate lives DOWNSTREAM --
nothing here narrows the keep-filter.

This measures, without changing anything, how many currently-flagged
public-safety signals would fail the operator's three proposed mechanisms:

  R1  exclusion terms (sewer, watermain, CIPP, pavement...)
  R2  context pairs: an ambiguous head (cctv / camera / inspection /
      monitoring) beside a civil companion (pipe, lining, sewer...) with NO
      safety companion (police, security, surveillance, fire...) excludes
  R3  buyer-type discrimination -- approximated here from buyer_name text
      (public works / engineering / infrastructure vs police / fire /
      paramedic), because real buyer-type lives behind the resolution work.
      The approximation is labelled as such in the output.

A large failure count says something about the lens; a small one says the
ranking problem is elsewhere. Either answer is the point.
"""
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
from src import supabase_client as sc  # noqa: E402

R1_EXCLUDE = (
    "sewer", "sanitary", "storm sewer", "watermain", "water main", "culvert",
    "cipp", "cured-in-place", "cured in place", "manhole", "catch basin",
    "road resurfacing", "sidewalk", "bridge rehabilitation", "pavement",
)
AMBIGUOUS_HEADS = ("cctv", "camera", "inspection", "monitoring")
CIVIL_COMPANIONS = ("pipe", "lining", "sewer", "watermain", "water main",
                    "culvert", "drainage", "wastewater")
SAFETY_COMPANIONS = ("police", "security", "surveillance", "enforcement",
                     "fire", "paramedic", "body-worn", "body worn")
# R3 approximation from buyer_name strings only.
R3_CIVIL = ("public works", "engineering", "infrastructure", "transportation",
            "water", "wastewater", "roads")
R3_SAFETY = ("police", "fire", "paramedic", "ems", "emergency")


def main() -> None:
    print("CIVIL-WORKS FALSE-POSITIVE COUNT -- report only, nothing applied")

    raw = sc.fetch_all_rows_where(
        "signals",
        "id,public_safety,documents!inner(id,title,content,buyer_name,url)",
        {"public_safety": "is.true", "suppressed": "is.false"})
    print(f"public_safety signals scanned: {len(raw)}")

    r1, r2, r3 = [], [], []
    for s in raw:
        d = s.get("documents") or {}
        if isinstance(d, list):
            d = d[0] if d else {}
        text = f"{d.get('title') or ''} {d.get('content') or ''}".lower()
        buyer = (d.get("buyer_name") or "").lower()

        if any(t in text for t in R1_EXCLUDE):
            r1.append((s, d))
        else:
            heads = [h for h in AMBIGUOUS_HEADS if h in text]
            if heads and any(c in text for c in CIVIL_COMPANIONS) \
                    and not any(k in text for k in SAFETY_COMPANIONS):
                r2.append((s, d))
        if buyer and any(c in buyer for c in R3_CIVIL) \
                and not any(k in buyer for k in R3_SAFETY):
            r3.append((s, d))

    union = {s["id"] for s, _ in r1} | {s["id"] for s, _ in r2}
    n = len(raw) or 1
    print(f"\nR1 exclusion terms:        {len(r1):5d} ({100*len(r1)/n:.1f}%)")
    print(f"R2 context pairs (new):    {len(r2):5d} ({100*len(r2)/n:.1f}%)")
    print(f"R1|R2 union:               {len(union):5d} ({100*len(union)/n:.1f}%)")
    print(f"R3 buyer-name approx:      {len(r3):5d} ({100*len(r3)/n:.1f}%)"
          f"   (string-match proxy; real buyer-type needs resolution work)")

    for label, rows in (("R1", r1), ("R2", r2), ("R3", r3)):
        print(f"\n  {label} sample (up to 10):")
        for s, d in rows[:10]:
            print(f"    {d.get('buyer_name') or '(no buyer)'} :: {d.get('title')!r}")
        buyers = Counter((d.get("buyer_name") or "(none)") for _, d in rows)
        top = ", ".join(f"{b} ({c})" for b, c in buyers.most_common(5))
        if rows:
            print(f"  {label} top buyers: {top}")

    print("\nprobe complete (read-only; nothing written)")


if __name__ == "__main__":
    main()
