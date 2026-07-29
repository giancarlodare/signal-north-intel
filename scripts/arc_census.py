"""ARC CENSUS: the editorial supply inventory (operator 2026-07-29).

Answers one question: how many sourced demand arcs can the brief actually
carry today, and at what rate does new arc material accrue? This is a
REPORT, not a pipeline. It writes nothing.

"Complete enough" is operationalized against the existing rung taxonomy
(src/taxonomy.py), so the census measures the corpus we really have:

  PRECURSOR   a signal at rung 2 (intent) or 3 (commitment) -- the board
              approval / capital line / business case / staff report class --
              that is BOTH dated (documents.published_on present) and
              deep-linkable (a record-level publisher URL, not a portal
              landing page or a listing anchor). Rung 3 is the strong form.
  SURROUNDING enough other record for the same buyer+category to tell a
              story: at least one further signal of any rung.
  OUTCOME     rung 4 (in market) or rung 5 (awarded). The award is the
              preferred anchor: awards persist in CanadaBuys while tender
              postings vanish from portals.
  ARC-READY   >= 1 dated deep-linked precursor AND >= 1 surrounding signal.
  PRECEDENT   for the arc's CATEGORY, >= 2 OTHER buyers carrying a dated
              outcome. Below 2 the item is a record item, never an arc
              (operator: thin arcs are worse than no arcs).

Accrual is measured on the document's own event date over the trailing 12
months, so it reflects when the public record was made, not when we
collected it.
"""
import os
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import supabase_client as sc  # noqa: E402

PRECURSOR_RUNGS = (2, 3)
OUTCOME_RUNGS = (4, 5)
MIN_PRECEDENT_BUYERS = 2

# Portal landing shapes: a URL that lands on a search page, not the record.
PORTAL_SUFFIXES = ("/module/tenders/en", "/module/tenders/en/")


def is_deep_linkable(url: str) -> bool:
    """A record-level publisher URL. Listing anchors (#:~:text=) and portal
    landing pages cannot anchor an arc node the reader can verify."""
    if not url:
        return False
    if "#:~:text=" in url:
        return False
    try:
        p = urlparse(url)
    except ValueError:
        return False
    path = (p.path or "").rstrip("/").lower()
    if not path:
        return False
    if any(path.endswith(s.rstrip("/")) for s in PORTAL_SUFFIXES):
        return False
    if path.count("/") == 1 and path.startswith("/m/"):   # Biddingo buyer page
        return False
    return True


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def _d(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def main() -> int:
    today = date.today()
    year_ago = today - timedelta(days=365)

    rows = sc.fetch_all_rows_where(
        "signals",
        "id,signal_type,evidence_grade,public_safety,suppressed,"
        "organization_id,organizations(canonical_name),"
        "categories(slug),"
        "documents!inner(doc_type,published_on,url)",
        {"suppressed": "is.false"})
    print(f"signals scanned (unsuppressed): {len(rows)}")

    # ---- normalize -------------------------------------------------------
    recs = []
    unresolved_org = 0
    for s in rows:
        org = _one(s.get("organizations")) or {}
        cat = _one(s.get("categories")) or {}
        doc = _one(s.get("documents")) or {}
        buyer = org.get("canonical_name")
        if not buyer:
            unresolved_org += 1
        recs.append({
            "buyer": buyer or "(unresolved buyer)",
            "resolved": bool(buyer),
            "category": cat.get("slug") or "(uncategorized)",
            "grade": s.get("evidence_grade") or 0,
            "public_safety": bool(s.get("public_safety")),
            "date": _d(doc.get("published_on")),
            "deep": is_deep_linkable(doc.get("url") or ""),
            "doc_type": doc.get("doc_type"),
        })

    ps = [r for r in recs if r["public_safety"]]
    print(f"  public-safety in scope: {len(ps)}")
    print(f"  UNRESOLVED buyer (cannot anchor an arc): {unresolved_org} "
          f"({round(100 * unresolved_org / (len(rows) or 1))}% of all signals)")

    by_grade = Counter(r["grade"] for r in ps)
    print(f"  by rung: {dict(sorted(by_grade.items()))}")

    precursors = [r for r in ps if r["grade"] in PRECURSOR_RUNGS
                  and r["date"] and r["deep"] and r["resolved"]]
    print(f"\nDATED + DEEP-LINKED + BUYER-RESOLVED precursors "
          f"(rung 2-3): {len(precursors)}")
    lost = [r for r in ps if r["grade"] in PRECURSOR_RUNGS]
    print(f"  (of {len(lost)} rung-2/3 signals total; the gap is undated, "
          f"portal-linked, or unresolved-buyer)")

    # ---- precedent availability per category ----------------------------
    outcome_buyers = defaultdict(set)
    award_buyers = defaultdict(set)
    for r in ps:
        if r["grade"] in OUTCOME_RUNGS and r["date"] and r["resolved"]:
            outcome_buyers[r["category"]].add(r["buyer"])
            if r["grade"] == 5:
                award_buyers[r["category"]].add(r["buyer"])

    # ---- per buyer x category -------------------------------------------
    cell_pre = defaultdict(list)
    cell_all = Counter()
    for r in ps:
        key = (r["buyer"], r["category"])
        cell_all[key] += 1
        if r["grade"] in PRECURSOR_RUNGS and r["date"] and r["deep"] and r["resolved"]:
            cell_pre[key].append(r)

    print("\n" + "=" * 100)
    print("ARC-READY CELLS (>=1 dated deep-linked precursor + surrounding record)")
    print("=" * 100)
    print(f"{'buyer':32s} {'category':22s} {'pre':>4s} {'str':>4s} "
          f"{'rec':>4s} {'newest':>11s}  precedent buyers (dated outcome)")
    ready = 0
    arc_with_precedent = 0
    for key in sorted(cell_pre, key=lambda k: (-len(cell_pre[k]), k)):
        buyer, cat = key
        pres = cell_pre[key]
        surrounding = cell_all[key] - len(pres)
        if surrounding < 1:
            continue          # no surrounding record: cannot tell the story
        ready += 1
        strong = sum(1 for p in pres if p["grade"] == 3)
        newest = max(p["date"] for p in pres)
        others = outcome_buyers.get(cat, set()) - {buyer}
        awards = award_buyers.get(cat, set()) - {buyer}
        ok = len(others) >= MIN_PRECEDENT_BUYERS
        if ok:
            arc_with_precedent += 1
        flag = f"{len(others)} ({len(awards)} by award)" if ok else \
               f"{len(others)} INSUFFICIENT"
        print(f"{buyer[:32]:32s} {cat[:22]:22s} {len(pres):4d} {strong:4d} "
              f"{surrounding:4d} {str(newest):>11s}  {flag}")
    print(f"\nARC-READY cells: {ready}")
    print(f"ARC-READY *with* a genuine precedent set "
          f"(>= {MIN_PRECEDENT_BUYERS} other buyers): {arc_with_precedent}")
    print(f"  the difference is items that stay RECORD items, not arcs")

    # ---- accrual ---------------------------------------------------------
    print("\n" + "=" * 100)
    print("ACCRUAL: dated deep-linked precursors by event month (trailing 12)")
    print("=" * 100)
    months = Counter()
    for p in precursors:
        if p["date"] >= year_ago:
            months[p["date"].strftime("%Y-%m")] += 1
    recent_total = sum(months.values())
    for m in sorted(months):
        print(f"  {m}  {months[m]:4d}  {'#' * min(months[m], 60)}")
    print(f"\n  trailing-12 precursor total: {recent_total}")
    print(f"  mean per month: {recent_total / 12:.1f}")

    print("\n" + "=" * 100)
    print("EDITORIAL SUPPLY READ")
    print("=" * 100)
    print(f"  arcs composable today (cell has precursor + record + precedents): "
          f"{arc_with_precedent}")
    print(f"  new precursor material arriving: ~{recent_total / 12:.1f}/month "
          f"across the whole corpus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
