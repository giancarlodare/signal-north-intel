"""ARC PULL: full read-only dump of one buyer x category arc, plus the
precedent set, as RAW MATERIAL for composing an arc by hand.

Prints, oldest first, every signal for the matched buyer+category with: date,
evidence-grade rung + role (precursor / surrounding / outcome), doc_type,
deep-linkable?, title, the one-line summary of what it says, the document
content length (STUB flagged), the source URL, and a body snippet.

Then the PRECEDENT SET: other buyers in the same category carrying a dated
outcome, each with its earliest dated deep-linked precursor, the interval in
months, and both URLs.

Read-only by construction: SELECTs only, no LLM, writes nothing.

Usage:  arc_pull.py <buyer-terms> <category-term>
        ("+" stands for a space, since workflow args arrive space-split)
        e.g.  arc_pull.py Toronto+Police+Service records
"""
import os
import sys
from collections import defaultdict
from datetime import date
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import supabase_client as sc  # noqa: E402

PRECURSOR_RUNGS = (2, 3)
OUTCOME_RUNGS = (4, 5)
PORTAL_SUFFIXES = ("/module/tenders/en",)
SNIPPET = 500


def is_deep_linkable(url: str) -> bool:
    if not url or "#:~:text=" in url:
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
    if path.count("/") == 1 and path.startswith("/m/"):
        return False
    return True


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def _d(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def months(a: date, b: date) -> float:
    return round((b - a).days / 30.44, 1)


def role(g: int) -> str:
    if g in PRECURSOR_RUNGS:
        return "PRECURSOR" + (" (strong)" if g == 3 else "")
    if g in OUTCOME_RUNGS:
        return "OUTCOME" + (" (award)" if g == 5 else "")
    return "surrounding"


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: arc_pull.py <buyer-terms> <category-term>  (+ = space)")
        return 2
    buyer_term = sys.argv[1].replace("+", " ").lower()
    cat_term = sys.argv[2].replace("+", " ").lower()

    rows = sc.fetch_all_rows_where(
        "signals",
        "id,signal_type,evidence_grade,title,summary,suppressed,"
        "organizations(canonical_name),categories(slug,name),"
        "documents!inner(id,doc_type,published_on,url,title)",
        {"suppressed": "is.false"})

    recs = []
    for s in rows:
        org = _one(s.get("organizations")) or {}
        cat = _one(s.get("categories")) or {}
        doc = _one(s.get("documents")) or {}
        recs.append({
            "buyer": org.get("canonical_name") or "",
            "cat_slug": (cat.get("slug") or "").lower(),
            "cat_name": (cat.get("name") or "").lower(),
            "grade": s.get("evidence_grade") or 0,
            "date": _d(doc.get("published_on")),
            "url": doc.get("url") or "",
            "deep": is_deep_linkable(doc.get("url") or ""),
            "doc_type": doc.get("doc_type"),
            "title": s.get("title") or doc.get("title") or "",
            "summary": s.get("summary") or "",
            "doc_id": doc.get("id"),
        })

    def cat_match(r):
        return cat_term in r["cat_name"] or cat_term in r["cat_slug"]

    def buyer_match(r):
        bn = r["buyer"].lower()
        if not bn or buyer_term not in bn:
            return False
        if "board" not in buyer_term and "board" in bn:
            return False  # the Service, not the Board, unless asked
        return True

    in_cat = [r for r in recs if cat_match(r)]
    arc = sorted([r for r in in_cat if buyer_match(r)],
                 key=lambda r: (r["date"] or date.min))

    # content for the arc documents only
    ids = [r["doc_id"] for r in arc if r["doc_id"]]
    content = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        drows = sc.fetch_rows_where(
            "documents", "id,content",
            {"id": f"in.({','.join(str(x) for x in chunk)})"}, limit=100)
        for d in drows:
            content[d["id"]] = d.get("content")

    cats_seen = sorted({r["cat_name"] for r in in_cat if r["cat_name"]})
    buyers_seen = sorted({r["buyer"] for r in arc})
    print(f'ARC PULL  buyer~"{buyer_term}"  category~"{cat_term}"')
    print(f"  category matched: {cats_seen[:4]}")
    print(f"  buyer matched: {buyers_seen}")
    print(f"  {len(arc)} signals in the arc "
          f"({sum(1 for r in arc if r['grade'] in PRECURSOR_RUNGS)} precursors, "
          f"{sum(1 for r in arc if r['grade'] in OUTCOME_RUNGS)} outcomes)\n")

    for r in arc:
        c = content.get(r["doc_id"])
        clen = len(c) if c else 0
        print(f'{r["date"] or "????-??-??"}  rung {r["grade"]} '
              f'{role(r["grade"]):18s} [{r["doc_type"]}] '
              f'{"deep-link" if r["deep"] else "PORTAL/anchor"}')
        print(f'  title: {r["title"][:120]}')
        print(f'  says : {r["summary"][:240]}')
        print(f'  body : {"STUB (no content)" if not clen else str(clen) + " chars"}'
              f'   {r["url"]}')
        if c:
            print(f'         "{" ".join(c[:SNIPPET].split())}..."')
        print()

    # ---- precedent set ---------------------------------------------------
    print("=== PRECEDENT SET (same category, buyers other than the arc buyer) ===")
    outcomes = defaultdict(list)
    precursors = defaultdict(list)
    for r in in_cat:
        if not r["buyer"] or buyer_match(r):
            continue
        if r["grade"] in OUTCOME_RUNGS and r["date"]:
            outcomes[r["buyer"]].append(r)
        if r["grade"] in PRECURSOR_RUNGS and r["date"] and r["deep"]:
            precursors[r["buyer"]].append(r)

    # buyers with BOTH a dated outcome and a dated deep precursor first (full arcs)
    def sort_key(b):
        return (0 if precursors.get(b) else 1,
                min(o["date"] for o in outcomes[b]))
    for buyer in sorted(outcomes, key=sort_key):
        out = min(outcomes[buyer], key=lambda r: r["date"])
        pres = precursors.get(buyer, [])
        pre = min(pres, key=lambda r: r["date"]) if pres else None
        print(buyer)
        if pre:
            print(f'  precursor {pre["date"]} rung {pre["grade"]} '
                  f'[{pre["doc_type"]}]  {pre["url"]}')
            print(f'  outcome   {out["date"]} rung {out["grade"]} '
                  f'[{out["doc_type"]}]  {out["url"]}')
            print(f'  interval  {months(pre["date"], out["date"])} months')
        else:
            print(f'  outcome   {out["date"]} rung {out["grade"]} '
                  f'[{out["doc_type"]}]  {out["url"]}')
            print("  precursor: none dated + deep-linked in corpus")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
