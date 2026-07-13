"""Procurement proposer (Phase A2, propose-only).

Clusters graded signals into candidate procurements and writes them as
`proposed` for human confirmation on the Procurements page. Never confirms,
never merges, never deletes. Same discipline as the discovery engine: the
weekly job's write surface is exactly `procurements` and `procurement_signals`,
and every row it touches stays `proposed` until a human acts.

Clustering (operator-approved 2026-07-13):
  1. HARD KEY: a reference number parsed from a signal's document (an explicit
     "Solicitation/Tender/RFP No. ..." label) is the identity. One procurement
     per reference (the DB enforces it with a partial unique index). Reference
     extraction is deliberately conservative: a wrong reference would merge
     unrelated signals under a false hard key, which is worse than none, so a
     reference is taken only from an explicit label with a real token.
  2. FALLBACK: buyer (resolved organization) plus scope (the signal's category)
     is the human-reviewed basis when no reference is present. No DB uniqueness.
  3. Fuzzy title similarity is NOT used to merge. It only informs the reviewer
     on the page. This module never merges on lookalike titles.

Propose thresholds (kept deliberately low but non-noisy): a candidate is
proposed when its group has at least 2 signals, OR a single signal has already
reached commitment (grade 3) or higher. A lone budget line, board approval,
posted tender, or award is a real opportunity worth tracking on its own.

Idempotent and re-runnable weekly: an existing procurement matched by identity
gets the new signals linked and its stage refreshed; a rejected match is left
alone (the reviewer said no, so the job never re-proposes it); a merged match
redirects links to the survivor. The proposer never changes a procurement's
status, title, or scope: those belong to the reviewer.

    python -m src.procurement_proposer --dry-run
    python -m src.procurement_proposer --limit 50
"""
import argparse
import logging
import re
import sys
from datetime import date

from . import procurements, supabase_client

log = logging.getLogger(__name__)

STAMP = "procurement-proposer@v1"
DEFAULT_LIMIT = 100                 # max NEW procurements proposed per run
MIN_GROUP_SIZE = 2                  # propose a multi-signal group...
LONE_SIGNAL_MIN_GRADE = 3          # ...or a lone signal at commitment or above

# A reference is taken only after an explicit label, and only when the captured
# token carries a digit and is long enough to be a real identifier. Conservative
# by design: a false reference is worse than none (it hard-keys unrelated
# signals together).
_REFERENCE_RE = re.compile(
    r"(?:solicitation|reference|tender|competition|rf[pqs]o?|rfq)\s*"
    r"(?:no\.?|number|#|:)\s*([A-Za-z0-9][A-Za-z0-9\-/]{4,})",
    re.IGNORECASE)


def _one(embedded):
    """PostgREST embeds a to-one relationship as an object or a 1-element list."""
    if isinstance(embedded, list):
        return embedded[0] if embedded else None
    return embedded


def parse_reference(*texts: str) -> str | None:
    """A solicitation/tender reference from labelled text, or None. Requires a
    digit in the token so prose like 'reference: attached' is rejected."""
    for text in texts:
        if not text:
            continue
        m = _REFERENCE_RE.search(text)
        if m:
            token = m.group(1)
            if any(ch.isdigit() for ch in token):
                return token
    return None


def signal_scope(signal: dict) -> tuple:
    """(scope_text, category_id) for a signal. Scope is the category name, the
    coarse buyer+scope grouping key the reviewer refines. Uncategorized signals
    group under an empty scope for their buyer (a coarse but safe proposal)."""
    cat = _one(signal.get("categories"))
    scope_text = (cat or {}).get("name") or ""
    return scope_text, signal.get("category_id")


def cluster(signals: list) -> list:
    """Group graded, buyer-resolved signals into candidate procurements.

    Pure: no I/O. Returns a list of candidate dicts, one per identity key.
    """
    groups: dict = {}
    for s in signals:
        buyer = s.get("organization_id")
        if not buyer:
            continue                       # Q5: resolved buyer required
        grade = s.get("evidence_grade")
        if not isinstance(grade, int):
            continue
        doc = _one(s.get("documents")) or {}
        # The structured documents.reference_number (a contract's procurement_id,
        # a tender's solicitation number) is authoritative when a source
        # provides it: that is what lets an award and its tender hard-key to the
        # same procurement. Fall back to the conservative text parse only when
        # the source carried no structured reference.
        reference = (doc.get("reference_number")
                     or parse_reference(s.get("title"), doc.get("title"), doc.get("url")))
        scope_text, category_id = signal_scope(s)
        key = procurements.procurement_identity(buyer, scope_text, reference)

        g = groups.get(key)
        if g is None:
            org = _one(s.get("organizations")) or {}
            buyer_name = org.get("canonical_name") or "Unknown buyer"
            label = scope_text or "unspecified scope"
            g = groups[key] = {
                "key": key,
                "buyer_organization_id": buyer,
                "reference_number": reference,
                "scope": scope_text or None,
                "category_id": category_id,
                "title": f"{buyer_name}: {label}"[:500],
                "signal_ids": [],
                "grades": [],
            }
        g["signal_ids"].append(s["id"])
        g["grades"].append(grade)

    for g in groups.values():
        g["size"] = len(g["signal_ids"])
        g["max_grade"] = max(g["grades"])
        g["stage"] = procurements.derive_stage(g["grades"])
    return list(groups.values())


def should_propose(candidate: dict) -> bool:
    return (candidate["size"] >= MIN_GROUP_SIZE
            or candidate["max_grade"] >= LONE_SIGNAL_MIN_GRADE)


def _existing_index(procs: list) -> dict:
    """Map identity key -> existing procurement row, so a candidate resolves to
    the procurement it already is."""
    index: dict = {}
    for p in procs:
        key = procurements.procurement_identity(
            p.get("buyer_organization_id"), p.get("scope"), p.get("reference_number"))
        index[key] = p
    return index


def run(dry_run: bool = False, limit: int = DEFAULT_LIMIT) -> int:
    stats = {"candidates": 0, "proposed": 0, "linked_existing": 0,
             "skipped_rejected": 0, "signals_linked": 0, "errors": 0}

    # Read the live corpus: every graded, org-resolved signal that has not been
    # suppressed. Under the editorial model (docs/editorial-model-redesign.md)
    # there is no approval gate; a signal is corpus-live on insert, and the only
    # exclusion is `suppressed` (an editorial override, or AR1 machine noise).
    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,organization_id,category_id,evidence_grade,title,"
        "organizations(canonical_name),categories(slug,name),"
        "documents(url,title,published_on,reference_number)",
        {"organization_id": "not.is.null", "evidence_grade": "not.is.null",
         "suppressed": "is.false"})

    candidates = [c for c in cluster(signals) if should_propose(c)]
    stats["candidates"] = len(candidates)

    procs = supabase_client.fetch_all_rows_where(
        "procurements",
        "id,buyer_organization_id,scope,reference_number,status,current_stage,merged_into_id",
        {})
    index = _existing_index(procs)
    by_id = {p["id"]: p for p in procs}

    links = supabase_client.fetch_all_rows_where(
        "procurement_signals", "procurement_id,signal_id", {})
    existing_links = {(l["procurement_id"], l["signal_id"]) for l in links}

    today = date.today().isoformat()

    for cand in candidates:
        try:
            match = index.get(cand["key"])
            if match and match.get("status") == "rejected":
                stats["skipped_rejected"] += 1
                continue

            target_id = None
            if match:
                # Follow a merge to the survivor so links land on the live row.
                target_id = match["id"]
                while by_id.get(target_id, {}).get("status") == "merged" \
                        and by_id[target_id].get("merged_into_id"):
                    target_id = by_id[target_id]["merged_into_id"]

            if target_id is None:
                if stats["proposed"] >= limit:
                    log.info("Per-run cap (%d new procurements) reached", limit)
                    break
                if dry_run:
                    log.info("[dry-run] would PROPOSE %r (%s, stage=%d [%s], %d signals)",
                             cand["title"], cand["key"], cand["stage"],
                             procurements.stage_label(cand["stage"]), cand["size"])
                    stats["proposed"] += 1
                    stats["signals_linked"] += cand["size"]
                    continue
                row = supabase_client.insert_row("procurements", {
                    "buyer_organization_id": cand["buyer_organization_id"],
                    "title": cand["title"],
                    "scope": cand["scope"],
                    "reference_number": cand["reference_number"],
                    "category_id": cand["category_id"],
                    "current_stage": cand["stage"],
                    "status": "proposed",
                    "proposed_by": STAMP,
                    "last_seen_on": today,
                })
                target_id = row["id"]
                stats["proposed"] += 1
            else:
                stats["linked_existing"] += 1

            # Link any signals not already linked to the target.
            new_signal_ids = [sid for sid in cand["signal_ids"]
                              if (target_id, sid) not in existing_links]
            for sid in new_signal_ids:
                if not dry_run:
                    supabase_client.insert_row("procurement_signals", {
                        "procurement_id": target_id, "signal_id": sid,
                        "linked_by": STAMP})
                existing_links.add((target_id, sid))
                stats["signals_linked"] += 1

            # Refresh stage (never downgrade a reviewer-advanced stage) and
            # last_seen. Only when there is a live target and real work.
            if not dry_run and target_id in by_id and new_signal_ids:
                current = by_id[target_id].get("current_stage") or 1
                supabase_client.update_row("procurements", target_id, {
                    "current_stage": max(current, cand["stage"]),
                    "last_seen_on": today})
        except Exception:   # noqa: BLE001 - one bad candidate must not kill the run
            log.exception("Error proposing %r", cand.get("title"))
            stats["errors"] += 1

    log.info("Procurement proposer%s: %s", " (DRY RUN)" if dry_run else "", stats)
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Procurement proposer (propose-only)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"max NEW procurements proposed per run (default {DEFAULT_LIMIT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="cluster and log proposals, write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(dry_run=args.dry_run, limit=args.limit))
