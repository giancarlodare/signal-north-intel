"""Stage the pilot proposer batch (Toronto + Peel) for the operator's
confirm pass. READ-ONLY: clusters exactly as src/procurement_proposer.py
would, writes nothing, and prints every proposal in adjudicable form:
the signal(s), the procurement they would link to, the linking evidence
(the shared hard-key reference or the buyer+scope pair), and a confidence
tier derived from the linking basis.

Tiering, so the operator's judgment goes where it matters:
  TIER A (adjudicate individually): clusters spanning 2+ distinct grades
     (a real arc claim: an upstream signal linked to downstream activity)
     and any multi-signal cluster on the buyer+scope fallback basis.
  TIER B (mechanical): single-signal hard-key clusters (one award or one
     tender becoming its own procurement; identity is the source's own
     reference number). Counted and sampled, proposed for batch approval.

Confidence tiers:
  HIGH   hard key from the source's structured reference_number
  MEDIUM hard key parsed from labelled text (conservative regex)
  LOW    buyer+scope fallback (no reference anywhere in the group)

    python scripts/stage_proposer_pilot.py
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import procurement_proposer as pp
from src import procurements, supabase_client

PILOT_ORG_MARKERS = ("toronto", "peel")
TIER_A_PRINT_CAP = int(os.environ.get("TIER_A_PRINT_CAP", "60"))
TIER_B_SAMPLE = 10


def _one(embedded):
    if isinstance(embedded, list):
        return embedded[0] if embedded else None
    return embedded


def pilot_org(signal) -> bool:
    org = _one(signal.get("organizations")) or {}
    name = (org.get("canonical_name") or "").lower()
    return any(m in name for m in PILOT_ORG_MARKERS)


def linking_basis(cand, signals_by_id) -> tuple:
    """(basis, confidence, evidence_text) for a candidate cluster."""
    if cand["key"][0] == "ref":
        ref = cand["reference_number"]
        structured = any(
            (_one(signals_by_id[sid].get("documents")) or {}).get("reference_number")
            for sid in cand["signal_ids"] if sid in signals_by_id)
        if structured:
            return ("hard-key", "HIGH",
                    f"shared structured reference '{ref}' carried by the source itself")
        return ("hard-key-parsed", "MEDIUM",
                f"reference '{ref}' parsed from an explicit label in title/url text")
    scope = cand["scope"] or "(uncategorized)"
    return ("buyer+scope", "LOW",
            f"same buyer + same scope category '{scope}'; no reference number "
            f"anywhere in the group, so this is the coarse human-reviewed basis")


def fmt_signal(s) -> str:
    doc = _one(s.get("documents")) or {}
    grade = s.get("evidence_grade")
    label = procurements.stage_label(grade) if isinstance(grade, int) else "?"
    date = doc.get("published_on") or "date unknown"
    title = (s.get("title") or "(untitled)")[:110]
    url = (doc.get("url") or "")[:120]
    ref = doc.get("reference_number")
    ref_part = f" ref={ref}" if ref else ""
    return f"      [{grade}:{label}] {date}{ref_part} :: {title}\n        src: {url}"


def main() -> int:
    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,organization_id,category_id,evidence_grade,title,"
        "organizations(canonical_name),categories(slug,name),"
        "documents(url,title,published_on,reference_number)",
        {"organization_id": "not.is.null", "evidence_grade": "not.is.null",
         "suppressed": "is.false"})
    pilot = [s for s in signals if pilot_org(s)]
    signals_by_id = {s["id"]: s for s in pilot}
    print(f"PILOT SCOPE: {len(pilot)} signals across Toronto+Peel orgs "
          f"(of {len(signals)} corpus-wide)")

    candidates = [c for c in pp.cluster(pilot) if pp.should_propose(c)]

    procs = supabase_client.fetch_all_rows_where(
        "procurements",
        "id,title,buyer_organization_id,scope,reference_number,status,current_stage",
        {})
    index = pp._existing_index(procs)
    links = supabase_client.fetch_all_rows_where(
        "procurement_signals", "procurement_id,signal_id", {})
    linked_sids = {l["signal_id"] for l in links}

    tier_a, tier_b = [], []
    for cand in candidates:
        grades = set(cand["grades"])
        new_sids = [sid for sid in cand["signal_ids"] if sid not in linked_sids]
        if not new_sids:
            continue                      # fully linked already; nothing to adjudicate
        cand["new_signal_ids"] = new_sids
        cand["existing"] = index.get(cand["key"])
        if len(grades) >= 2 or (cand["key"][0] == "buyer_scope" and cand["size"] >= 2):
            tier_a.append(cand)
        else:
            tier_b.append(cand)

    tier_a.sort(key=lambda c: (-len(set(c["grades"])), -c["size"]))

    print(f"\nPROPOSAL TIERS: tier_a={len(tier_a)} (individual adjudication) "
          f"tier_b={len(tier_b)} (mechanical single-signal hard-key)")

    print("\n" + "=" * 76)
    print("TIER A: ARC-CLAIM PROPOSALS (adjudicate each)")
    print("=" * 76)
    for i, cand in enumerate(tier_a[:TIER_A_PRINT_CAP], 1):
        basis, conf, evidence = linking_basis(cand, signals_by_id)
        existing = cand["existing"]
        target = (f"EXISTING procurement '{(existing.get('title') or '')[:80]}' "
                  f"(status={existing.get('status')}, stage={existing.get('current_stage')})"
                  if existing else f"NEW procurement '{cand['title'][:80]}'")
        print(f"\n[A{i}] CONFIDENCE={conf} basis={basis} "
              f"grades={sorted(set(cand['grades']))} signals={cand['size']} "
              f"(new links: {len(cand['new_signal_ids'])})")
        print(f"    LINK TO: {target}")
        print(f"    EVIDENCE: {evidence}")
        print("    SIGNALS:")
        for sid in cand["signal_ids"]:
            s = signals_by_id.get(sid)
            if s:
                already = "" if sid in cand["new_signal_ids"] else "  (already linked)"
                print(fmt_signal(s) + already)
    if len(tier_a) > TIER_A_PRINT_CAP:
        print(f"\n  ... {len(tier_a) - TIER_A_PRINT_CAP} further tier-A proposals "
              f"beyond the print cap (raise TIER_A_PRINT_CAP to see all)")

    print("\n" + "=" * 76)
    print("TIER B: MECHANICAL SINGLE-SIGNAL HARD-KEY PROPOSALS (batch approval)")
    print("=" * 76)
    by_conf = Counter()
    for cand in tier_b:
        _, conf, _ = linking_basis(cand, signals_by_id)
        by_conf[conf] += 1
    print(f"  count={len(tier_b)} by confidence: {dict(by_conf)}")
    print(f"  sample ({min(TIER_B_SAMPLE, len(tier_b))}):")
    for cand in tier_b[:TIER_B_SAMPLE]:
        _, conf, _ = linking_basis(cand, signals_by_id)
        s = signals_by_id.get(cand["signal_ids"][0])
        if s:
            print(f"    [{conf}] ref={cand['reference_number']} "
                  f":: {(s.get('title') or '')[:90]}")

    print("\nSTAGING SUMMARY (read-only, nothing written):")
    print(f"  pilot signals: {len(pilot)}; proposable clusters: {len(candidates)}")
    print(f"  tier A (arc claims, individual confirm): {len(tier_a)}")
    print(f"  tier B (mechanical, batch confirm): {len(tier_b)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
