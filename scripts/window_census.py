"""Window census: what the timing window actually discards. Read-only.

Operator questions (2026-08-02, before the lens side-by-side is built):
  1. Of the ~11.7k out-of-window signals, what share are public-safety-
     relevant items failing ONLY on the window vs items that would fail
     anyway? (Tag-proxy here: defence_relevant OR public_safety keyword
     verdict, plus the path bar. The TRUE relevance share comes from the
     calibration batch, which samples this discard; this census is the
     denominator and the honest first cut.)
  2. What does widening +30 -> +35 admit (the scorer curve's peak band)?
  3. What would a +60 or +90 GRANT window admit beyond +45? Grants are a
     different action with a different lead time.

Mirrors brief_generator's data access exactly: same select, same
suppressed=false, same published_on semantics (past event date; future
deadline for grants).
"""
import os
import sys
from collections import Counter
from datetime import date, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from src import supabase_client as sc          # noqa: E402
from src import public_safety                  # noqa: E402
from src.brief_generator import _one, _parse_date  # noqa: E402
from src.filters import load_keywords          # noqa: E402

GRANT_TYPES = {"grant_program", "grant_award"}
KW = load_keywords()


def bucket_of(delta_days: int) -> str:
    if delta_days < -7:
        return "past(<-7d)"
    if delta_days <= 0:
        return "recent(-7..0)"
    if delta_days <= 30:
        return "+1..30"
    if delta_days <= 35:
        return "+31..35"
    if delta_days <= 45:
        return "+36..45"
    if delta_days <= 60:
        return "+46..60"
    if delta_days <= 90:
        return "+61..90"
    return ">+90"


def main() -> int:
    today = date.today()
    signals = sc.fetch_all_rows_where(
        "signals",
        "id,materiality,evidence_grade,title,signal_type,"
        "organizations(canonical_name,org_type),"
        "documents!inner(doc_type,published_on,defence_relevant)",
        {"suppressed": "is.false"})
    print(f"WINDOW CENSUS -- {len(signals)} live signals, today={today}\n")

    buckets: Counter = Counter()
    only_window_fail = 0          # tag-relevant + bar-passing, out of window
    would_fail_anyway = 0
    out_of_window = 0
    band_3135: Counter = Counter()          # doc_type mix of the widening band
    band_3135_relevant = 0
    grant_4660: list = []
    grant_6190: list = []

    undated_doctype: Counter = Counter()
    undated_sigtype: Counter = Counter()
    undated_relevant = 0
    undated_relevant_titles: list = []
    for s in signals:
        doc = _one(s.get("documents")) or {}
        p = _parse_date(doc.get("published_on"))
        if p is None:
            buckets["undated"] += 1
            # Undated signals fail BOTH paths by construction (deliberately
            # undated beats wrongly dated, but 284 permanently invisible
            # items deserve a composition answer, operator 2026-08-02).
            undated_doctype[doc.get("doc_type") or "unknown"] += 1
            undated_sigtype[s.get("signal_type") or "unknown"] += 1
            if public_safety.cluster_is_public_safety(
                    [{"title": s.get("title"),
                      "defence_relevant": bool(doc.get("defence_relevant")),
                      "org_type": (_one(s.get("organizations")) or {}).get("org_type")}],
                    KW) and (s.get("materiality") or 0) >= 2:
                undated_relevant += 1
                if len(undated_relevant_titles) < 12:
                    undated_relevant_titles.append(
                        ((_one(s.get("organizations")) or {}).get("canonical_name")
                         or "-", (s.get("title") or "")[:70]))
            continue
        dd = (p - today).days
        b = bucket_of(dd)
        buckets[b] += 1

        in_window = (-7 <= dd <= 0) or \
            (0 < dd <= (45 if doc.get("doc_type") in GRANT_TYPES else 30))
        mat = s.get("materiality") or 0
        grade = s.get("evidence_grade") or 0
        # Tag-proxy relevance: the document is defence-tagged, or the
        # public-safety keyword verdict fires on the same inputs the lens
        # uses. Pending true relevance scores from the calibration batch.
        relevant = public_safety.cluster_is_public_safety(
            [{"title": s.get("title"),
              "defence_relevant": bool(doc.get("defence_relevant")),
              "org_type": (_one(s.get("organizations")) or {}).get("org_type")}],
            KW)
        bar = (mat >= 2 and grade >= 2) if dd > 0 else (mat >= 3 and grade >= 3)

        if not in_window:
            out_of_window += 1
            if relevant and bar:
                only_window_fail += 1
            else:
                would_fail_anyway += 1
        if b == "+31..35":
            band_3135[doc.get("doc_type") or "unknown"] += 1
            if relevant and bar:
                band_3135_relevant += 1
        if doc.get("doc_type") in GRANT_TYPES:
            org = (_one(s.get("organizations")) or {}).get("canonical_name")
            row = (str(p), org or "-", (s.get("title") or "")[:70])
            if 45 < dd <= 60:
                grant_4660.append(row)
            elif 60 < dd <= 90:
                grant_6190.append(row)

    print("DISTRIBUTION (days from today, event/deadline date):")
    order = ["past(<-7d)", "recent(-7..0)", "+1..30", "+31..35", "+36..45",
             "+46..60", "+61..90", ">+90", "undated"]
    for b in order:
        print(f"  {b:14s} {buckets.get(b, 0):6d}")

    print(f"\nDISCARD DECOMPOSITION ({out_of_window} out-of-window, dated):")
    pct = (100 * only_window_fail / out_of_window) if out_of_window else 0
    print(f"  fail ONLY on the window (tag-relevant + bar-passing): "
          f"{only_window_fail} ({pct:.1f}%)")
    print(f"  would fail anyway (tag-irrelevant or below bar):       "
          f"{would_fail_anyway}")
    print("  NOTE: tag-proxy relevance; the calibration batch samples this "
          "discard for the true share.")

    print(f"\nWIDENING BAND +31..35 (what +35 admits): "
          f"{sum(band_3135.values())} signals, "
          f"{band_3135_relevant} tag-relevant+bar-passing")
    for dt, n in band_3135.most_common():
        print(f"    {dt:24s} {n}")

    print(f"\nUNDATED ({buckets.get('undated', 0)} signals, invisible to both "
          f"paths by construction):")
    print("  by doc_type:  ",
          dict(undated_doctype.most_common(8)))
    print("  by signal_type:",
          dict(undated_sigtype.most_common(8)))
    print(f"  tag-relevant at materiality>=2: {undated_relevant}")
    for org, t in undated_relevant_titles:
        print(f"    {org[:30]:30s} {t}")

    print(f"\nGRANT HORIZON (deadline-dated grant signals beyond +45):")
    print(f"  +46..60 would admit {len(grant_4660)} signals:")
    for d, org, t in sorted(grant_4660)[:15]:
        print(f"    {d}  {org[:28]:28s} {t}")
    print(f"  +61..90 would admit {len(grant_6190)} more:")
    for d, org, t in sorted(grant_6190)[:15]:
        print(f"    {d}  {org[:28]:28s} {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
