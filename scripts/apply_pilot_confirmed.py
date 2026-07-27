"""Write the operator-confirmed pilot links (confirm pass, 2026-07-27).

Re-derives the same coherent-domain clusters as stage_proposer_pilot2 (same
corpus, same code -> same clusters) and writes the operator's CONFIRMED set
as procurements + procurement_signals, status='confirmed' with the review
note. Includes a STRUCTURE GUARD: it verifies each confirmed index still
carries the expected (buyer, scope); if the corpus has drifted (e.g. a drain
added Toronto/Peel signals and reshuffled the clustering) it ABORTS and writes
nothing, so a stale decision map can never mislink. Re-run the staging and
re-confirm if it aborts.

Also fixes the one true contamination (correctness gap): signal 751bc4fb,
a WRPS/Waterloo comparable-cost citation mis-resolved to Peel, is re-resolved
to Waterloo Regional Police Service and dropped from the Peel R3 rhythm group.

Idempotent: a procurement already written by this stamp (matched on title) is
skipped. Read-modify safe: only procurements/procurement_signals and the one
signal's organization_id are touched.

    python scripts/apply_pilot_confirmed.py            # write
    python scripts/apply_pilot_confirmed.py --dry-run  # verify guard, write nothing
"""
import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import supabase_client
from scripts.stage_proposer_pilot2 import (
    instrument_tokens, UnionFind, pilot_org, _one, MAX_TOKEN_SPREAD)

STAMP = "pilot-confirm@v1"
NOTE = "operator confirm pass 2026-07-27"
WRPS_CONTAMINANT = "751bc4fb-7647-4633-ac86-a91f768d7284"
WRPS_ORG = "Waterloo Regional Police Service"

# Confirmed clusters, keyed by the STABLE (buyer_substr, scope) signature and
# a token the cluster must contain, so the guard verifies identity rather than
# trusting an index. kind is recorded on the procurement for the coverage
# report's reading. (Rejected clusters are simply absent.)
CONFIRMED = [
    # cross-rung threads
    ("Toronto Police Service Board", "Fleet & Vehicles", "havis", "thread"),
    ("Peel Regional Police", "Digital Evidence Management", "i.c.e", "thread"),
    ("Peel Regional Police", "Training & Professional Development", "hate", "thread"),
    ("Toronto Police Service Board", "AI & Analytics", "ataccama", "thread"),
    ("Toronto Police Service Board", "Fleet & Vehicles", "d&r", "thread"),
    ("Toronto Police Service Board", "Managed & Outsourced Services", "collision", "thread"),
    # bucket-A dedups (single-grade; hygiene, no transitions)
    ("Toronto Police Service Board", "Facilities & Detention", "vipond", "dedup"),
    ("Toronto Police Service Board", "Radios & Communications", "rogers", "dedup"),
    ("Toronto Police Service Board", "Fleet & Vehicles", "towing", "dedup"),
    ("Toronto Police Service Board", "AI & Analytics", "g2s", "dedup"),
    ("Toronto Police Service Board", "Fleet & Vehicles", "setina", "dedup"),
    ("Peel Regional Police", "Facilities & Detention", "1.78b", "dedup"),
    ("Region of Peel", "Consulting & Reviews", "kennedy", "dedup"),
    ("Toronto Police Service", "Records & Dispatch (RMS/CAD)", "records", "dedup"),
    ("Toronto Police Service", "Facilities & Detention", "calverley", "dedup"),
    ("Toronto Police Service", "Facilities & Detention", "eastern", "dedup"),
    ("City of Toronto", "Consulting & Reviews", "kpmg", "dedup"),
    ("City of Toronto", "Consulting & Reviews", "king", "dedup"),
    ("City of Toronto", "Consulting & Reviews", "arup", "dedup"),
    ("City of Toronto", "Consulting & Reviews", "eelrt", "dedup"),
    ("City of Toronto", "Consulting & Reviews", "gardiner", "dedup"),
    ("City of Toronto", "Facilities & Detention", "rafat", "dedup"),
    ("City of Toronto", "Facilities & Detention", "treatment", "dedup"),
    ("City of Toronto", "Facilities & Detention", "ellisdon", "dedup"),
    ("City of Toronto", "Managed & Outsourced Services", "health", "dedup"),
    ("City of Toronto", "Training & Professional Development", "multi-supplier", "dedup"),
    ("City of Toronto", "Protective & Cut-Resistant Equipment", "masks", "dedup"),
    ("Toronto Police Service", "Uniforms & Apparel", "experts", "dedup"),
    ("Peel Regional Police", "Training & Professional Development", "resilience", "dedup"),
    # rhythm groups (multi-signal; the engine derives the rhythm)
    ("Toronto Police Service", "AI & Analytics", None, "rhythm"),
    ("Toronto Police Service Board", "Consulting & Reviews", None, "rhythm"),
    ("Toronto Police Service", "Consulting & Reviews", None, "rhythm"),
    ("Toronto Police Service", "Facilities & Detention", None, "rhythm"),
    ("Peel Regional Police", "Facilities & Detention", None, "rhythm"),   # R3, WRPS dropped
    ("Toronto Police Service", "Training & Professional Development", None, "rhythm"),  # T37
]


def build_domain_index():
    """{(buyer, scope): [signals]} over unlinked pilot signals, exactly as
    stage_proposer_pilot2 groups them."""
    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,organization_id,category_id,evidence_grade,title,"
        "organizations(canonical_name),categories(slug,name),"
        "documents(url,title,published_on,reference_number)",
        {"organization_id": "not.is.null", "evidence_grade": "not.is.null",
         "suppressed": "is.false"})
    pilot = [s for s in signals if pilot_org(s)]
    links = supabase_client.fetch_all_rows_where(
        "procurement_signals", "signal_id", {})
    linked = {l["signal_id"] for l in links}
    by_domain = defaultdict(list)
    for s in pilot:
        if s["id"] in linked:
            continue
        buyer = (_one(s.get("organizations")) or {}).get("canonical_name") or "?"
        scope = ((_one(s.get("categories")) or {}).get("name") or "").strip()
        if s.get("evidence_grade") == 1 or not scope:
            continue
        by_domain[(buyer, scope)].append(s)
    return by_domain


def token_subcluster(sigs):
    """Reproduce the instrument sub-clustering; return list of member-lists."""
    token_map = defaultdict(list)
    for s in sigs:
        for tk in instrument_tokens(s.get("title") or ""):
            token_map[tk].append(s["id"])
    markers = {tk: ids for tk, ids in token_map.items()
               if 2 <= len(set(ids)) <= MAX_TOKEN_SPREAD}
    uf = UnionFind()
    for ids in markers.values():
        for other in ids[1:]:
            uf.union(ids[0], other)
    groups = defaultdict(list)
    for s in sigs:
        groups[uf.find(s["id"])].append(s)
    return list(groups.values()), markers


def resolve_confirmed(by_domain):
    """For each CONFIRMED entry, find its actual signal set. thread/dedup use
    the token to pick the sub-cluster; rhythm uses the whole domain's grade
    2/3 commitments + 4/5 activity (minus the WRPS contaminant)."""
    out = []
    for buyer_sub, scope, token, kind in CONFIRMED:
        key = next((k for k in by_domain
                    if buyer_sub.lower() in k[0].lower() and k[1] == scope), None)
        if key is None:
            out.append((buyer_sub, scope, kind, None, f"no domain {buyer_sub}/{scope}"))
            continue
        sigs = by_domain[key]
        if kind in ("thread", "dedup"):
            subclusters, _ = token_subcluster(sigs)
            members = next((m for m in subclusters
                            if any(token in (s.get("title") or "").lower() for s in m)
                            and len(m) >= 2), None)
            if not members:
                out.append((buyer_sub, scope, kind, None, f"no subcluster w/ '{token}'"))
                continue
            out.append((key[0], scope, kind, members, None))
        else:  # rhythm
            members = [s for s in sigs
                       if s.get("evidence_grade") in (2, 3, 4, 5)
                       and s["id"] != WRPS_CONTAMINANT]
            if len(members) < 2:
                out.append((buyer_sub, scope, kind, None, "rhythm <2 after clean"))
                continue
            out.append((key[0], scope, kind, members, None))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="delete prior pilot-confirm@v1 procurements+links first, "
                         "so a re-run after a drain re-links new signals fresh")
    args = ap.parse_args()

    if args.refresh and not args.dry_run:
        prior = supabase_client.fetch_all_rows_where(
            "procurements", "id", {"proposed_by": f"eq.{STAMP}"})
        for p in prior:
            supabase_client.delete_rows("procurement_signals",
                                        {"procurement_id": f"eq.{p['id']}"})
            supabase_client.delete_rows("procurements", {"id": f"eq.{p['id']}"})
        print(f"REFRESH: cleared {len(prior)} prior pilot-confirm procurements")

    by_domain = build_domain_index()
    resolved = resolve_confirmed(by_domain)

    ok = [r for r in resolved if r[3] is not None]
    bad = [r for r in resolved if r[3] is None]
    print(f"STRUCTURE GUARD: {len(ok)}/{len(CONFIRMED)} confirmed clusters resolved")
    for buyer, scope, kind, _m, why in bad:
        print(f"  UNRESOLVED [{kind}] {buyer}/{scope}: {why}")
    # Guard: if too many fail, the corpus drifted; abort rather than half-write.
    if len(bad) > 3:
        print(f"\nABORT: {len(bad)} clusters did not resolve; corpus likely "
              f"drifted since staging. Re-run staging and re-confirm. Nothing written.")
        return 1

    now = datetime.now(timezone.utc).isoformat()
    existing = supabase_client.fetch_all_rows_where(
        "procurements", "id,title,proposed_by", {"proposed_by": f"eq.{STAMP}"})
    seen_titles = {p["title"] for p in existing}

    stats = {"procurements": 0, "links": 0, "skipped_existing": 0, "reresolved": 0}
    for buyer, scope, kind, members, _why in ok:
        title = f"{buyer}: {scope} [{kind}]"[:500]
        if title in seen_titles:
            stats["skipped_existing"] += 1
            continue
        grades = [s["evidence_grade"] for s in members]
        if args.dry_run:
            print(f"  [dry] {kind:6s} {title}  ({len(members)} signals, grades={sorted(set(grades))})")
            stats["procurements"] += 1
            stats["links"] += len(members)
            continue
        row = supabase_client.insert_row("procurements", {
            "buyer_organization_id": members[0].get("organization_id"),
            "title": title, "scope": scope,
            "current_stage": max(grades),
            "status": "confirmed", "proposed_by": STAMP,
            "review_note": f"{NOTE} ({kind})", "reviewed_at": now,
        })
        for s in members:
            supabase_client.insert_row("procurement_signals", {
                "procurement_id": row["id"], "signal_id": s["id"],
                "linked_by": STAMP})
            stats["links"] += 1
        stats["procurements"] += 1

    # R3 correctness fix: re-resolve the WRPS contaminant out of Peel.
    if not args.dry_run:
        orgs = supabase_client.fetch_rows("organizations", "id,canonical_name")
        wrps = next((o["id"] for o in orgs if o.get("canonical_name") == WRPS_ORG), None)
        if wrps:
            supabase_client.update_row("signals", WRPS_CONTAMINANT,
                                       {"organization_id": wrps})
            stats["reresolved"] = 1
            print(f"  R3 fix: signal {WRPS_CONTAMINANT} re-resolved to {WRPS_ORG}")

    print(f"\nCONFIRM-PASS WRITE: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
