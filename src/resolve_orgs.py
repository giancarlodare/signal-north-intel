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
# The audit of unresolved_org_name across the live corpus ranked these highest.
# org_type is metadata (the resolver keys on name + aliases), but the column is a
# constrained enum: the confirmed-valid labels are federal_department,
# provincial_ministry, association, corrections, etc. There is no municipal
# government label in use, so Region of Peel tries "municipality" then falls back.
ORG_SEED = [
    ("Region of Peel",
     ["Peel Region", "Regional Municipality of Peel",
      "The Regional Municipality of Peel"],
     ["municipality", "municipal_government"], "municipal", "ON"),
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
]


def _ensure_org(canonical, aliases, org_type_candidates, jurisdiction, province,
                dry_run=False) -> str | None:
    """Return the org id, inserting it if absent or merging aliases if present.
    Insert tries each org_type candidate until the enum accepts one (then a NULL
    org_type), so an unknown municipal label can never block the seed."""
    quoted = canonical.replace('"', "")
    existing = supabase_client.fetch_rows_where(
        "organizations", "id,canonical_name,aliases",
        {"canonical_name": f'ilike."{quoted}"'}, limit=1)
    if existing:
        o = existing[0]
        merged = sorted(set((o.get("aliases") or []) + aliases))
        if set(merged) != set(o.get("aliases") or []):
            if dry_run:
                log.info("  [dry-run] would merge aliases into %r", canonical)
            else:
                supabase_client.update_row("organizations", o["id"], {"aliases": merged})
                log.info("  merged aliases into existing org %r", canonical)
        return o["id"]

    if dry_run:
        log.info("  [dry-run] would insert org %r", canonical)
        return None
    for ot in [*org_type_candidates, None]:
        payload = {"canonical_name": canonical, "aliases": sorted(set(aliases)),
                   "jurisdiction": jurisdiction, "province": province}
        if ot is not None:
            payload["org_type"] = ot
        try:
            row = supabase_client.insert_row("organizations", payload)
            log.info("  inserted org %r (org_type=%s)", canonical, ot)
            return row["id"]
        except supabase_client.SupabaseError as e:
            log.warning("  insert %r org_type=%s rejected: %s", canonical, ot, str(e)[:100])
    log.error("  could NOT insert org %r with any candidate org_type", canonical)
    return None


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
