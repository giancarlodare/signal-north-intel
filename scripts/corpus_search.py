"""Generic read-only corpus term search, for "do we have any of X?" questions
asked from chat (Sarnia OPP-transition arc, West Grey headquarters, ...).

Each argv is one search term; "+" inside a term stands for a space, since
workflow args arrive space-separated ("sarnia west+grey" is two terms).
Matches against documents.title OR documents.content, printing metadata only.
Commas cannot appear in terms (they would break the PostgREST or= filter).

Read-only by construction: SELECTs only, no LLM.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from src import supabase_client as sc  # noqa: E402

COLS = "id,title,doc_type,published_on,buyer_name,url"
LIMIT = 100


def search(term: str) -> None:
    pat = f"*{term}*"
    print(f'TERM "{term}"')
    try:
        rows = sc.fetch_rows_where(
            "documents", COLS,
            {"or": f"(title.ilike.{pat},content.ilike.{pat})"},
            limit=LIMIT)
    except Exception as e:  # noqa: BLE001 -- content scan can hit statement timeout
        print(f"  full-text scan failed ({e}); falling back to title-only")
        rows = sc.fetch_rows_where("documents", COLS,
                                   {"title": f"ilike.{pat}"}, limit=LIMIT)
    if not rows:
        print("  0 matches\n")
        return
    cap = "" if len(rows) < LIMIT else f" (capped at {LIMIT})"
    print(f"  {len(rows)} matches{cap}")
    for r in sorted(rows, key=lambda r: r.get("published_on") or "",
                    reverse=True)[:40]:
        print(f"  {r.get('published_on') or '????-??-??'}  "
              f"[{r.get('doc_type')}] {(r.get('buyer_name') or '-')[:30]:30s} "
              f"{(r.get('title') or '')[:80]}")
        print(f"      {r.get('url')}")
    print()


def main() -> int:
    terms = [a.replace("+", " ") for a in sys.argv[1:]]
    if not terms:
        print("usage: corpus_search.py term [term ...]  (+ = space in a term)")
        return 2
    print("CORPUS SEARCH -- read-only")
    for t in terms:
        search(t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
