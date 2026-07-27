"""Before/after the public-safety relevance filter on the Region-of-Peel feed
(task #54, operator 2026-07-27).

The operator's diagnosis: the member view is 24 Region-of-Peel items because a
regional government publishes police/fire/EMS tenders in the SAME feed as
general municipal procurement (watermains, roads, LTC supplies), and today's
lens admits the big general ones on materiality alone. This report answers the
one question the operator asked: how many of those items survive as
public-safety-relevant once the filter is applied.

Read-only. Prints two splits, writes nothing:

  1. THE PUBLISHED-BRIEF SET (the exact items a member sees today): every
     included item of the current published brief, each judged by the new
     predicate, with the count that survives.
  2. THE PEEL SIGNAL CORPUS (broader): every in-corpus signal whose resolved
     org is a Region-of-Peel entity, split into the public-safety slice vs the
     general-municipal slice, so the isolation the filter performs is visible
     at feed scale, not just in one week's brief.

    python scripts/peel_public_safety_split.py
"""
import sys

sys.path.insert(0, ".")

from src import public_safety, supabase_client
from src.brief_generator import _kw


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def _sig_fields(s: dict) -> tuple:
    """(org_name, org_type, title, defence_relevant) from a joined signal row."""
    org = _one(s.get("organizations")) or {}
    doc = _one(s.get("documents")) or {}
    return (org.get("canonical_name"), org.get("org_type"),
            s.get("title"), bool(doc.get("defence_relevant")))


def _is_peel(org_name) -> bool:
    return bool(org_name) and "peel" in org_name.lower()


def _verdict(org_type, title, defence, kw) -> str:
    if defence:
        return "KEEP (defence)"
    if public_safety.is_public_safety(org_type, title, kw):
        # Distinguish the path so the operator sees WHY it kept.
        if org_type in public_safety.PUBLIC_SAFETY_ORG_TYPES:
            return "KEEP (org-type)"
        return "KEEP (text)"
    return "HELD (general)"


def published_brief_split(kw):
    """The exact set a member sees today: the current published brief's included
    items, each judged. Prints the per-item table and the survive count."""
    briefs = supabase_client.fetch_rows_where(
        "briefs", "id,week_start,status", {"status": "eq.published"},
        limit=1)
    if not briefs:
        print("No published brief exists; skipping the brief-set split.\n")
        return
    b = briefs[0]
    items = supabase_client.fetch_all_rows_where(
        "brief_items",
        "rank,included,lead_signal_id,"
        "signals:lead_signal_id(title,organizations(canonical_name,org_type),"
        "documents(defence_relevant))",
        {"brief_id": f"eq.{b['id']}", "included": "is.true"})
    items.sort(key=lambda it: it.get("rank") or 999)

    print(f"=== PUBLISHED-BRIEF SET (week_start {b['week_start']}) ===")
    print(f"    {len(items)} items a member sees today\n")
    print(f"    {'rank':<5} {'verdict':<16} {'org_type':<20} {'buyer':<22} title")
    kept = 0
    for it in items:
        s = _one(it.get("signals")) or {}
        org_name, org_type, title, defence = _sig_fields(s)
        v = _verdict(org_type, title, defence, kw)
        if v.startswith("KEEP"):
            kept += 1
        print(f"    #{(it.get('rank') or 0):<4} {v:<16} "
              f"{(org_type or '-'):<20} {(org_name or '-')[:22]:<22} "
              f"{(title or '')[:50]}")
    held = len(items) - kept
    print(f"\n    BEFORE filter: {len(items)} items shown to the member")
    print(f"    AFTER  filter: {kept} survive as public-safety-relevant, "
          f"{held} held as general municipal\n")


def peel_corpus_split(kw):
    """The broader feed: every in-corpus signal resolving to a Region-of-Peel
    entity, split public-safety vs general. Shows the isolation at feed scale."""
    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,title,organization_id,"
        "organizations(canonical_name,org_type),"
        "documents!inner(doc_type,defence_relevant)",
        {"suppressed": "is.false"})
    peel = [s for s in signals if _is_peel((_one(s.get("organizations")) or {})
                                           .get("canonical_name"))]
    keep, held = [], []
    by_type = {}
    for s in peel:
        org_name, org_type, title, defence = _sig_fields(s)
        if defence or public_safety.is_public_safety(org_type, title, kw):
            keep.append(s)
        else:
            held.append(s)
        by_type[org_type or "unresolved"] = by_type.get(org_type or "unresolved", 0) + 1

    print("=== PEEL SIGNAL CORPUS (all resolved-to-Peel signals) ===")
    print(f"    {len(peel)} Peel signals total\n")
    print("    resolved org_type distribution:")
    for t, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
        print(f"      {t:<24} {n}")
    print(f"\n    public-safety slice: {len(keep)}")
    print(f"    general slice:       {len(held)}")
    if held:
        print("\n    sample HELD (general municipal, correctly isolated out):")
        for s in held[:12]:
            org_name, org_type, title, _ = _sig_fields(s)
            print(f"      [{(org_type or '-'):<14}] {(title or '')[:70]}")
    if keep:
        print("\n    sample KEEP (public-safety, the vertical slice):")
        for s in keep[:12]:
            org_name, org_type, title, defence = _sig_fields(s)
            tag = "defence" if defence else ("org" if org_type in
                                             public_safety.PUBLIC_SAFETY_ORG_TYPES
                                             else "text")
            print(f"      [{tag:<7}] {(title or '')[:70]}")
    print()


def main():
    kw = _kw()
    published_brief_split(kw)
    peel_corpus_split(kw)


if __name__ == "__main__":
    main()
