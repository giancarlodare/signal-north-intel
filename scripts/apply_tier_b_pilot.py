"""Apply the operator-approved tier-B pilot batch (2026-07-26).

Scope, exactly as batch-confirmed: MECHANICAL single-signal HARD-KEY
clusters for Toronto+Peel where the hard key is the source's own
STRUCTURED reference_number (an identity fact: one award or tender is its
own procurement). The staging run counted 829 tier-B clusters of which
819 were structured-reference HIGH confidence; the ~10 singles whose key
was only parsed from text or whose basis was buyer+scope are NOT identity
facts and are deliberately HELD for the cleaned tier-A pass.

Writes exactly what the proposer would, plus the operator's confirmation:
procurements rows with status='confirmed', review_note recording the
batch approval, reviewed_at stamped; procurement_signals links. Follows
proposer semantics for existing rows: an existing identity match is
linked (never duplicated), a rejected match is skipped, a merge is
followed to its survivor.
"""
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import procurement_proposer as pp
from src import supabase_client

STAMP = "pilot-tierb-batch@v1"
REVIEW_NOTE = ("operator batch-confirmed 2026-07-26: tier-B mechanical "
               "hard-key (structured reference; one award/tender = its own "
               "procurement)")
PILOT_ORG_MARKERS = ("toronto", "peel")


def _one(embedded):
    if isinstance(embedded, list):
        return embedded[0] if embedded else None
    return embedded


def pilot_org(signal) -> bool:
    org = _one(signal.get("organizations")) or {}
    return any(m in (org.get("canonical_name") or "").lower()
               for m in PILOT_ORG_MARKERS)


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

    candidates = [c for c in pp.cluster(pilot) if pp.should_propose(c)]

    procs = supabase_client.fetch_all_rows_where(
        "procurements",
        "id,buyer_organization_id,scope,reference_number,status,current_stage,merged_into_id",
        {})
    index = pp._existing_index(procs)
    by_id = {p["id"]: p for p in procs}
    links = supabase_client.fetch_all_rows_where(
        "procurement_signals", "procurement_id,signal_id", {})
    existing_links = {(l["procurement_id"], l["signal_id"]) for l in links}
    linked_sids = {sid for _, sid in existing_links}

    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    stats = {"tier_b_high": 0, "created": 0, "linked_existing": 0,
             "skipped_rejected": 0, "held_not_structured": 0, "errors": 0}

    for cand in candidates:
        grades = set(cand["grades"])
        # tier-B: single-signal hard-key cluster, not already linked
        if len(grades) >= 2 or (cand["key"][0] == "buyer_scope" and cand["size"] >= 2):
            continue
        sid = cand["signal_ids"][0]
        if cand["size"] != 1 or sid in linked_sids:
            continue
        if cand["key"][0] != "ref":
            stats["held_not_structured"] += 1
            continue
        doc = _one(signals_by_id[sid].get("documents")) or {}
        if not doc.get("reference_number"):
            stats["held_not_structured"] += 1     # text-parsed key: held
            continue
        stats["tier_b_high"] += 1
        try:
            match = index.get(cand["key"])
            if match and match.get("status") == "rejected":
                stats["skipped_rejected"] += 1
                continue
            if match:
                target_id = match["id"]
                while by_id.get(target_id, {}).get("status") == "merged" \
                        and by_id[target_id].get("merged_into_id"):
                    target_id = by_id[target_id]["merged_into_id"]
                stats["linked_existing"] += 1
            else:
                row = supabase_client.insert_row("procurements", {
                    "buyer_organization_id": cand["buyer_organization_id"],
                    "title": cand["title"],
                    "scope": cand["scope"],
                    "reference_number": cand["reference_number"],
                    "category_id": cand["category_id"],
                    "current_stage": cand["stage"],
                    "status": "confirmed",
                    "proposed_by": STAMP,
                    "review_note": REVIEW_NOTE,
                    "reviewed_at": now,
                    "last_seen_on": today,
                })
                target_id = row["id"]
                by_id[target_id] = row
                index[cand["key"]] = row
                stats["created"] += 1
            if (target_id, sid) not in existing_links:
                supabase_client.insert_row("procurement_signals", {
                    "procurement_id": target_id, "signal_id": sid,
                    "linked_by": STAMP})
                existing_links.add((target_id, sid))
        except Exception as exc:   # noqa: BLE001 - one bad row must not kill the batch
            print(f"ERROR on ref={cand['reference_number']}: {exc}")
            stats["errors"] += 1

    print(f"TIER-B APPLY: {stats}")
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
