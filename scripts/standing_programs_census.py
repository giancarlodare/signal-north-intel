"""Standing-programs census. Read-only. Readies the standing-programs ruling.

The undated census (window_census) found 89 funding_program / 105
grant_program signals that are deliberately undated because they are
ROLLING or MULTI-YEAR standing programs -- deadline-shaped surfacing is the
wrong frame, and no window widening ever reaches them. They are chief-facing
money (the weakest segment) currently structurally invisible to the brief.

This census gives the ruling its inputs: the standing-program signals broken
out by FUNDER, with an OPEN/CLOSED/RENEWED hint parsed from the title (a
hint only -- never a fabricated status), materiality, and the relevance-tag
verdict. So the operator can rule on a "standing programs" surfacing path
(the brief's money section, listed as standing, entering when new and
resurfacing on material change) from real rows, not a description.
"""
import os
import re
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from src import supabase_client as sc          # noqa: E402
from src import public_safety                  # noqa: E402
from src.brief_generator import _one           # noqa: E402
from src.filters import load_keywords          # noqa: E402

KW = load_keywords()
GRANT_TYPES = {"grant_program", "grant_award"}
STATUS_HINTS = [
    ("CLOSED", re.compile(r"\bclosed\b|deadline passed|no longer", re.I)),
    ("RENEWED", re.compile(r"renew|extended|4-year|multi-year|20\d\d-20\d\d", re.I)),
    ("OPEN", re.compile(r"\bopen\b|now accepting|applications? (?:open|invited)"
                        r"|supports?|funds?|available", re.I)),
]


def status_hint(title: str) -> str:
    for label, pat in STATUS_HINTS:
        if pat.search(title or ""):
            return label
    return "UNSTATED"


def main() -> int:
    rows = sc.fetch_all_rows_where(
        "signals",
        "id,materiality,evidence_grade,title,signal_type,"
        "organizations(canonical_name,org_type),"
        "documents!inner(doc_type,published_on,defence_relevant)",
        {"suppressed": "is.false"})

    standing = []
    for s in rows:
        doc = _one(s.get("documents")) or {}
        if doc.get("published_on"):
            continue                      # dated -> not a standing-program row
        if doc.get("doc_type") not in GRANT_TYPES and \
           s.get("signal_type") not in ("funding_program", "pilot_program"):
            continue
        standing.append(s)

    print(f"STANDING-PROGRAMS CENSUS -- {len(standing)} undated program "
          f"signals (read-only)\n")

    by_funder: Counter = Counter()
    by_status: Counter = Counter()
    relevant = 0
    for s in standing:
        doc = _one(s.get("documents")) or {}
        org = (_one(s.get("organizations")) or {}).get("canonical_name") or "-"
        by_funder[org] += 1
        by_status[status_hint(s.get("title"))] += 1
        if public_safety.cluster_is_public_safety(
                [{"title": s.get("title"),
                  "defence_relevant": bool(doc.get("defence_relevant")),
                  "org_type": (_one(s.get("organizations")) or {}).get("org_type")}],
                KW) and (s.get("materiality") or 0) >= 2:
            relevant += 1

    print("BY FUNDER:")
    for org, n in by_funder.most_common(20):
        print(f"  {n:3d}  {org[:56]}")
    print(f"\nBY TITLE STATUS HINT (hint only, never a stored status):")
    for st, n in by_status.most_common():
        print(f"  {st:9s} {n}")
    print(f"\npublic-safety-relevant at materiality>=2: {relevant} of {len(standing)}")

    print("\nSAMPLE ROWS (funder | mat | status-hint | title):")
    for s in sorted(standing, key=lambda s: -(s.get("materiality") or 0))[:30]:
        org = (_one(s.get("organizations")) or {}).get("canonical_name") or "-"
        print(f"  {org[:26]:26s} m{s.get('materiality') or 0} "
              f"{status_hint(s.get('title')):9s} {(s.get('title') or '')[:62]}")

    print("\nRULING INPUT: a standing-programs surfacing path would list these "
          "in the brief's money section as STANDING (no fabricated dates), "
          "entering when new and resurfacing on material change (renewal, "
          "closure, funding change). None is reachable by any window widening.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
