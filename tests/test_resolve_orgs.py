"""Tests for the org seed data + re-resolution wiring. The DB writes are not
exercised here (they need Supabase); these lock the seed's shape and prove the
alias set actually resolves the raw buyer-name variants the model emits."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import resolve_orgs as ro
from src.signal_extractor import build_resolver, _normalize

VALID_JURISDICTIONS = {"federal", "provincial", "municipal"}


def test_seed_entries_are_well_formed():
    seen = set()
    for canonical, aliases, org_types, jurisdiction, province in ro.ORG_SEED:
        assert canonical and canonical.strip(), "canonical name must be non-empty"
        assert canonical not in seen, f"duplicate canonical {canonical!r}"
        seen.add(canonical)
        assert isinstance(aliases, list) and aliases, "aliases must be a non-empty list"
        assert isinstance(org_types, list) and org_types, "need at least one org_type candidate"
        assert jurisdiction in VALID_JURISDICTIONS, jurisdiction
        # aliases must be distinct after normalization (no dead duplicates)
        norms = [_normalize(a) for a in aliases]
        assert len(norms) == len(set(norms)), f"duplicate normalized alias in {canonical!r}"


def test_alias_set_resolves_the_real_buyer_variants():
    # Build a resolver from the seed as if these orgs existed, then confirm the
    # exact raw strings the extractor flagged all resolve to the right org.
    fake_orgs = [{"id": f"org-{i}", "canonical_name": c, "aliases": a}
                 for i, (c, a, *_rest) in enumerate(ro.ORG_SEED)]
    resolve = build_resolver(fake_orgs, key_fields=("canonical_name",), alias_field="aliases")

    # (raw name as emitted by the model) -> (expected canonical)
    cases = {
        "Region of Peel": "Region of Peel",
        "Peel Region": "Region of Peel",                       # the observed variant
        "Regional Municipality of Peel": "Region of Peel",
        "Department of Justice Canada": "Department of Justice Canada",
        "Ministry of the Solicitor General": "Ministry of the Solicitor General",
        "Ministry of Solicitor General": "Ministry of the Solicitor General",  # variant
        "Canadian Interagency Forest Fire Centre (CIFFC)": "Canadian Interagency Forest Fire Centre",
        "Correctional Services Canada": "Correctional Service of Canada",       # "s" variant
        "Agriculture and Agri-Food": "Agriculture and Agri-Food Canada",        # truncated form
        "Treasury Board Secretariat": "Treasury Board of Canada Secretariat",
        "Ministry of Natural Resources": "Ministry of Natural Resources and Forestry",
        "Ministry of Children, Community and Social Services - Office of Women Issues":
            "Ministry of Children, Community and Social Services",
        "ISED": "Innovation, Science and Economic Development Canada",
    }
    canonical_by_id = {o["id"]: o["canonical_name"] for o in fake_orgs}
    for raw, expected in cases.items():
        oid = resolve(raw)
        assert oid is not None, f"{raw!r} did not resolve"
        assert canonical_by_id[oid] == expected, (raw, canonical_by_id[oid], expected)
