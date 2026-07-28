"""Impact diff for matcher and keyword-list changes (operator program
2026-07-28): evidence BEFORE anything applies, same discipline as the
defence re-tag. Read-only everywhere.

Modes:
  --plural-only          current keywords.txt, plural-tolerant matcher vs
                         the strict whole-word matcher it replaces.
  --proposed <file>      proposed list vs current list, BOTH under the
                         plural matcher, with per-added-term attribution.
                         Also shows the UNSPSC {46}+{92} keep delta.

Surfaces measured:
  A. documents: rows currently defence_relevant=false whose stored
     title+content would newly match the DEFENCE list (would newly tag).
  B. signals member gate: rows currently public_safety=false that
     is_public_safety() would newly admit (keyword path only).
  C. today's full open-tenders CSV: notices the keep-filter would newly
     KEEP (recall bought), listed so noise is judgeable.

    python scripts/diff_keywords.py --plural-only
    python scripts/diff_keywords.py --proposed config/keywords_proposed.txt
"""
import argparse
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import config, public_safety, supabase_client
from src.filters import Keywords, _word_pattern, load_keywords, unspsc_segment
from src.main import fetch_csv_rows, parse_tender_row


def strict_pattern(kw: str) -> re.Pattern:
    """The pre-plural whole-word matcher, for the --plural-only baseline."""
    pre = r"(?<!\w)" if re.match(r"\w", kw[:1]) else ""
    post = r"(?!\w)" if re.match(r"\w", kw[-1:]) else ""
    return re.compile(pre + re.escape(kw) + post, re.IGNORECASE)


def first_hit(text: str, kws, pat) -> str | None:
    for kw in kws:
        if pat(kw).search(text):
            return kw
    return None


def diff(old_kws: Keywords, old_pat, new_kws: Keywords, new_pat) -> None:
    print("\n--- A. documents: would newly defence-tag ---")
    docs = supabase_client.fetch_all_rows_where(
        "documents", "id,doc_type,title,content",
        {"defence_relevant": "is.false"})
    newly, per_kw = [], Counter()
    for d in docs:
        text = f"{d.get('title') or ''} {d.get('content') or ''}"
        if first_hit(text, old_kws.defence, old_pat):
            continue
        kw = first_hit(text, new_kws.defence, new_pat)
        if kw:
            newly.append((d, kw))
            per_kw[kw] += 1
    print(f"  {len(docs)} untagged docs scanned; would newly tag: {len(newly)}")
    for kw, n in per_kw.most_common():
        print(f"    {kw:<28} {n}")
    for d, kw in newly[:15]:
        print(f"    + [{d.get('doc_type')}] {(d.get('title') or '')[:70]}  ({kw})")

    print("\n--- B. signals member gate: would newly admit (keyword path) ---")
    sigs = supabase_client.fetch_all_rows_where(
        "signals", "id,title,public_safety,organizations(org_type)",
        {"suppressed": "is.false", "public_safety": "is.false"})
    admitted = []
    for s in sigs:
        org = s.get("organizations") or {}
        org = org[0] if isinstance(org, list) and org else org
        ot = (org or {}).get("org_type")
        if ot in public_safety.PUBLIC_SAFETY_ORG_TYPES:
            continue  # org-typed, not a keyword question
        title = s.get("title") or ""
        old = (first_hit(title, (*old_kws.general, *old_kws.defence), old_pat)
               or public_safety._facility_hit(title))
        if old:
            continue
        kw = first_hit(title, (*new_kws.general, *new_kws.defence), new_pat)
        if kw:
            admitted.append((s, kw))
    print(f"  {len(sigs)} member-hidden signals scanned; would newly admit: "
          f"{len(admitted)}")
    for s, kw in admitted[:15]:
        print(f"    + {(s.get('title') or '')[:74]}  ({kw})")

    print("\n--- C. open-tenders CSV: keep-filter delta ---")
    rows = fetch_csv_rows(config.OPEN_TENDER_NOTICES_URL)
    fields = list(rows[0].keys()) if rows else []
    def kept_by(t, kws, pat, segs):
        seg = unspsc_segment(t["unspsc_raw"])
        if seg in segs:
            return f"unspsc {seg}"
        return first_hit(f"{t['title']} {t['description']}",
                         (*kws.general, *kws.defence), pat)
    new_keeps, per_kw2 = [], Counter()
    n_old = 0
    for row in rows:
        t = parse_tender_row(row, fields)
        if kept_by(t, old_kws, old_pat, {"46"}):
            n_old += 1
            continue
        why = kept_by(t, new_kws, new_pat, {"46", "92"})
        if why:
            new_keeps.append((t, why))
            per_kw2[why] += 1
    print(f"  {len(rows)} open notices; kept before: {n_old}; "
          f"NEWLY kept: {len(new_keeps)}")
    for kw, n in per_kw2.most_common():
        print(f"    {kw:<28} {n}")
    for t, why in new_keeps[:25]:
        print(f"    + {(t['title'] or '')[:64]} | {(t['buyer_name'] or '?')[:32]} ({why})")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plural-only", action="store_true")
    g.add_argument("--proposed")
    args = ap.parse_args()

    current = load_keywords()
    if args.plural_only:
        print("DIFF: plural-tolerant matcher vs strict whole-word "
              "(current keyword list on both sides)")
        diff(current, strict_pattern, current, _word_pattern)
    else:
        proposed = load_keywords(args.proposed)
        print(f"DIFF: proposed list ({args.proposed}) vs current keywords.txt "
              "(plural matcher on both sides; UNSPSC 46 -> 46+92)")
        diff(current, _word_pattern, proposed, _word_pattern)
    return 0


if __name__ == "__main__":
    sys.exit(main())
