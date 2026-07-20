"""Seed recurring buyers into the canonical organizations list and re-resolve
the signals that were flagged `needs_org_resolution` before those buyers existed.

The extractor resolves a raw buyer name to an organization_id by exact
(normalized) match on canonical_name + aliases; a buyer absent from the list
falls through as needs_org_resolution=true with the raw name preserved in
unresolved_org_name. That degrades more than the brief's "The buyer" phrasing:
the procurement spine and reconciliation key on organization_id, so an
unresolved buyer cannot be linked to its procurements or settle a prediction.

This seeds the highest-frequency unresolved buyers (an audit of the live corpus
picked these), then re-resolves the flagged backlog in place. Once seeded, future
extractions resolve these buyers automatically.

Idempotent: an org is inserted only if its canonical_name is absent (otherwise
its aliases are merged), and re-resolution only ever fills a null
organization_id. Safe to re-run.

    python -m src.resolve_orgs            # seed + re-resolve
    python -m src.resolve_orgs --dry-run  # report only, write nothing

Org seeding is DML the service role performs (not a schema change), so this
script IS the seed mechanism: run it once on a fresh database to reproduce the
canonical entries, rather than a SQL migration -- it also has to discover the
valid municipal org_type enum label at runtime and re-resolve existing rows.
"""
import argparse
import logging
from collections import Counter

from . import supabase_client
from .signal_extractor import build_resolver

log = logging.getLogger(__name__)

# (canonical_name, aliases, org_type candidates tried in order, jurisdiction, province)
# The audit of unresolved_org_name across the live corpus ranked these: every
# entry here appeared at least twice as a raw buyer name. org_type is metadata
# (the resolver keys on name + aliases), but the column is a NOT NULL enum;
# confirmed-accepted labels: municipality, federal_department, federal_agency,
# provincial_ministry, association, corrections, crown_corp, police_service,
# police_board, border_agency. Deliberately NOT seeded: "Government of Canada"
# (too generic to be a buyer), "CanadaBuys" (a portal, not a buyer), CORCAN and
# individual CSC institutions (operator call whether to alias them to CSC), and
# Alberta Health Services (no confidently-correct org_type label in use).
ORG_SEED = [
    ("Region of Peel",
     ["Peel Region", "Regional Municipality of Peel",
      "The Regional Municipality of Peel"],
     ["municipality"], "municipal", "ON"),
    # Big 12 tier 1 buyers (docs/big12-tier1-design.md): the bids&tenders
    # config rows write these exact names to documents.buyer_name, and the
    # extractor's raw org strings must resolve to them.
    ("York Region",
     ["Regional Municipality of York", "The Regional Municipality of York",
      "Region of York"],
     ["municipality"], "municipal", "ON"),
    ("City of London",
     ["London", "The Corporation of the City of London"],
     ["municipality"], "municipal", "ON"),
    ("Region of Durham",
     ["Durham Region", "Regional Municipality of Durham",
      "The Regional Municipality of Durham"],
     ["municipality"], "municipal", "ON"),
    ("York Regional Police",
     ["YRP", "York Regional Police Service"],
     ["police_service"], "municipal", "ON"),
    ("Department of Justice Canada",
     ["Department of Justice Canada", "Justice Canada", "Department of Justice"],
     ["federal_department"], "federal", None),
    ("Ministry of the Solicitor General",
     ["Ministry of the Solicitor General", "Ministry of Solicitor General",
      "Solicitor General of Ontario"],
     ["provincial_ministry"], "provincial", "ON"),
    ("Indigenous Services Canada",
     ["Indigenous Services Canada", "ISC"],
     ["federal_department"], "federal", None),
    ("Canadian Interagency Forest Fire Centre",
     ["Canadian Interagency Forest Fire Centre",
      "Canadian Interagency Forest Fire Centre (CIFFC)", "CIFFC"],
     ["association"], "federal", None),
    # Existing org; this entry only merges the "s" spelling variant as an alias.
    ("Correctional Service of Canada",
     ["Correctional Services Canada", "Correctional Service Canada", "CSC"],
     ["corrections"], "federal", None),
    ("Agriculture and Agri-Food Canada",
     ["Agriculture and Agri-Food", "AAFC", "Agriculture and Agri-Food Canada"],
     ["federal_department"], "federal", None),
    ("Ministry of Citizenship and Multiculturalism",
     ["Ministry of Citizenship and Multiculturalism"],
     ["provincial_ministry"], "provincial", "ON"),
    ("Ministry of Children, Community and Social Services",
     ["Ministry of Children, Community and Social Services", "MCCSS",
      "Ministry of Children, Community and Social Services - Office of Women Issues"],
     ["provincial_ministry"], "provincial", "ON"),
    ("Treasury Board of Canada Secretariat",
     ["Treasury Board Secretariat", "TBS", "Treasury Board of Canada Secretariat"],
     ["federal_agency"], "federal", None),
    ("Ministry of Transportation",
     ["Ministry of Transportation", "Ministry of Transportation (Ontario)", "MTO"],
     ["provincial_ministry"], "provincial", "ON"),
    ("Ministry of Natural Resources and Forestry",
     ["Ministry of Natural Resources and Forestry", "Ministry of Natural Resources",
      "MNRF"],
     ["provincial_ministry"], "provincial", "ON"),
    ("City of Ottawa",
     ["City of Ottawa"],
     ["municipality"], "municipal", "ON"),
    ("Parks Canada",
     ["Parks Canada", "Parks Canada Agency"],
     ["federal_agency"], "federal", None),
    ("Innovation, Science and Economic Development Canada",
     ["ISED", "Innovation, Science and Economic Development",
      "Innovation, Science and Economic Development Canada"],
     ["federal_department"], "federal", None),
]


def _fetch_org(canonical) -> dict | None:
    """Exact-match lookup by canonical_name. eq (not a quoted ilike pattern):
    PostgREST treats a double-quoted like/ilike value literally, so the quoted
    form silently never matches and an existing row looks absent."""
    rows = supabase_client.fetch_rows_where(
        "organizations", "id,canonical_name,aliases",
        {"canonical_name": f"eq.{canonical}"}, limit=1)
    return rows[0] if rows else None


def _ensure_org(canonical, aliases, org_type_candidates, jurisdiction, province,
                dry_run=False) -> str | None:
    """Return the org id, inserting it if absent or merging aliases if present.
    A 23505 unique-key rejection on insert means the row exists after all (or a
    concurrent writer won); it is re-fetched and treated as existing, so the
    alias merge still lands."""
    existing = _fetch_org(canonical)
    if existing is None:
        if dry_run:
            log.info("  [dry-run] would insert org %r", canonical)
            return None
        for ot in org_type_candidates:
            payload = {"canonical_name": canonical, "aliases": sorted(set(aliases)),
                       "org_type": ot, "jurisdiction": jurisdiction, "province": province}
            try:
                row = supabase_client.insert_row("organizations", payload)
                log.info("  inserted org %r (org_type=%s)", canonical, ot)
                return row["id"]
            except supabase_client.SupabaseError as e:
                msg = str(e)
                if "23505" in msg:  # duplicate canonical_name: row exists, merge below
                    existing = _fetch_org(canonical)
                    break
                log.warning("  insert %r org_type=%s rejected: %s", canonical, ot, msg[:100])
        if existing is None:
            log.error("  could NOT insert org %r with any candidate org_type", canonical)
            return None

    merged = sorted(set((existing.get("aliases") or []) + aliases))
    if set(merged) != set(existing.get("aliases") or []):
        if dry_run:
            log.info("  [dry-run] would merge aliases into %r", canonical)
        else:
            supabase_client.update_row("organizations", existing["id"], {"aliases": merged})
            log.info("  merged aliases into existing org %r", canonical)
    return existing["id"]


def run(dry_run: bool = False) -> dict:
    log.info("Seeding %d recurring buyers%s", len(ORG_SEED), " (dry-run)" if dry_run else "")
    for entry in ORG_SEED:
        _ensure_org(*entry, dry_run=dry_run)

    orgs = supabase_client.fetch_rows("organizations", "id,canonical_name,aliases")
    resolve = build_resolver(orgs, key_fields=("canonical_name",), alias_field="aliases")

    flagged = supabase_client.fetch_all_rows_where(
        "signals", "id,unresolved_org_name", {"needs_org_resolution": "is.true"})
    log.info("Re-resolving %d flagged signals%s", len(flagged), " (dry-run)" if dry_run else "")

    resolved = 0
    still = Counter()
    for s in flagged:
        raw = s.get("unresolved_org_name")
        oid = resolve(raw) if raw else None
        if oid:
            if not dry_run:
                supabase_client.update_row("signals", s["id"], {
                    "organization_id": oid, "needs_org_resolution": False,
                    "unresolved_org_name": None})
            resolved += 1
        else:
            still[raw or "(null)"] += 1

    log.info("Resolved %d of %d flagged signals%s", resolved, len(flagged),
             " (dry-run, nothing written)" if dry_run else "")
    log.info("Still unresolved (top 10): %s", dict(still.most_common(10)))
    return {"flagged": len(flagged), "resolved": resolved,
            "still_unresolved": len(flagged) - resolved}


if __name__ == "__main__":
    import sys
    parser = argparse.ArgumentParser(description="Seed recurring buyers and re-resolve signals")
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(dry_run=args.dry_run)
    sys.exit(0)
