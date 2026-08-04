"""DOC TEXT: read-only content grep with a context window, for verifying what a
source document ACTUALLY says before anything built on it is published.

Given search terms, it finds documents whose title or content matches, and for
each it prints the metadata plus a context window (+/- ~700 chars) around every
occurrence of each term in the body. The point is to read the source sentence
itself, not the one-line summary -- e.g. confirming whether an "Auditor General
review of 9-1-1" was of a named police service, of a city's 911 service, or
province-wide, before a node that reads as an audit finding is published.

Read-only by construction: SELECTs only, no LLM, writes nothing.

Usage:  doc_text.py <term> [term ...]     ("+" stands for a space in a term)
        e.g.  doc_text.py Auditor+General priority+response 9-1-1
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import supabase_client as sc  # noqa: E402

WINDOW = 700          # chars of context each side of a hit
MAX_HITS_PER_TERM = 4  # per document, to keep output bounded
COLS = "id,title,doc_type,published_on,buyer_name,url,content"


def windows_for(content: str, term: str):
    if not content:
        return []
    out = []
    low = content.lower()
    t = term.lower()
    start = 0
    while len(out) < MAX_HITS_PER_TERM:
        i = low.find(t, start)
        if i < 0:
            break
        a = max(0, i - WINDOW)
        b = min(len(content), i + len(term) + WINDOW)
        snippet = content[a:b]
        out.append((i, " ".join(snippet.split())))
        start = i + len(term)
    return out


def main() -> int:
    terms = [a.replace("+", " ") for a in sys.argv[1:]]
    if not terms:
        print("usage: doc_text.py <term> [term ...]   (+ = space in a term)")
        return 2
    print("DOC TEXT -- read-only content grep\n")

    # One OR filter over all terms, on title and content, so a document
    # matching ANY term is returned once.
    ors = []
    for t in terms:
        pat = f"*{t}*"
        ors.append(f"title.ilike.{pat}")
        ors.append(f"content.ilike.{pat}")
    try:
        rows = sc.fetch_rows_where(
            "documents", COLS, {"or": f"({','.join(ors)})"}, limit=60)
    except Exception as e:  # noqa: BLE001 -- content scan can time out
        print(f"content scan failed ({e}); retrying title-only")
        tors = [f"title.ilike.*{t}*" for t in terms]
        rows = sc.fetch_rows_where(
            "documents", COLS, {"or": f"({','.join(tors)})"}, limit=60)

    rows.sort(key=lambda r: r.get("published_on") or "")
    print(f"{len(rows)} documents match at least one term\n")
    print("=" * 100)
    for r in rows:
        content = r.get("content") or ""
        hits = {t: windows_for(content, t) for t in terms}
        total = sum(len(v) for v in hits.values())
        print(f'{r.get("published_on") or "????-??-??"}  [{r.get("doc_type")}]  '
              f'{(r.get("buyer_name") or "-")[:40]}')
        print(f'  title: {(r.get("title") or "")[:140]}')
        print(f'  url  : {r.get("url")}')
        print(f'  content: {len(content)} chars, {total} term-hit windows'
              f'{"  (title match only)" if total == 0 else ""}')
        for t, wins in hits.items():
            for (pos, w) in wins:
                print(f'    -- "{t}" @ {pos}:')
                print(f'       ...{w}...')
        print("-" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
