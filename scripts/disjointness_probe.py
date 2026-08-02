"""DISJOINTNESS PROBE: york / peel / london / durham (operator 2026-07-29,
run 2026-08-02). Read-only, writes nothing, calls no LLM.

THE QUESTION THAT DECIDES THE ~$118: do the four region/city tender portals
carry their police service's procurement, or is police buying disjoint --
living on police-dedicated hosts we already collect (yrp.bidsandtenders,
Biddingo/DRPS, the police boards)? If disjoint, an unscoped drain over the
region portals pays to extract documents that can never touch a police arc,
which is exactly what the Toronto read found for open.toronto.ca.

Same discipline as that read: STRICT police terms only (the "911" lesson --
a term that can match a reference number is not a topic match), scanned over
real bodies, not just titles.

Output per region: portal doc count, police-term docs (n, %), the matching
titles (all of them if few -- the decision needs the actual documents, not a
rate alone), and, on the police side, which hosts actually feed that
service's signals today.
"""
import os
import sys
from collections import Counter
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
from src import supabase_client as sc  # noqa: E402

# Strict: terms that cannot appear except in police-related text. Mirrors the
# Toronto read (arc_diagnostics.POLICE_TERMS) plus each service's own name.
POLICE_TERMS = (
    "police", "constable", "body-worn camera", "body worn camera",
    "law enforcement", "taser", "conducted energy weapon", "in-car camera",
    "prisoner transport",
)

# region label -> (regional/city portal host, [police-side host substrings])
REGIONS = {
    "York":   ("york.bidsandtenders.ca",       ["yrp.bidsandtenders.ca", "yrpsb.ca"]),
    "Peel":   ("peelregion.bidsandtenders.ca", ["peelpoliceboard.ca"]),
    "London": ("london.bidsandtenders.ca",     []),   # no police-dedicated source running
    "Durham": ("durham.bidsandtenders.ca",     ["biddingo.com", "durhampoliceboard.ca"]),
}


def _hit(text: str) -> str | None:
    low = text.lower()
    for t in POLICE_TERMS:
        if t in low:
            return t
    return None


def main() -> None:
    print("DISJOINTNESS PROBE -- do region portals carry police procurement?")

    for region, (portal, police_hosts) in REGIONS.items():
        docs = sc.fetch_all_rows_where(
            "documents", "id,url,title,content,doc_type,published_on,buyer_name",
            {"url": f"ilike.*{portal}*"})
        hits = []
        for d in docs:
            t = _hit(f"{d.get('title') or ''} {d.get('content') or ''}")
            if t:
                hits.append((t, d))
        n = len(docs)
        print("\n" + "=" * 78)
        print(f"{region}: {portal}")
        print("=" * 78)
        if not n:
            print("  NO DOCUMENTS at this host -- portal collected nothing yet;")
            print("  disjointness cannot be judged from an empty corpus.")
        else:
            pct = 100 * len(hits) / n
            print(f"  portal docs: {n}   police-term docs: {len(hits)} ({pct:.1f}%)")
            for t, d in hits[:15]:
                print(f"    [{t}] {d.get('published_on')} {d.get('title')!r}")
                print(f"      {d.get('url')}")
            if len(hits) > 15:
                print(f"    ... and {len(hits) - 15} more")

        for ph in police_hosts:
            pdocs = sc.fetch_all_rows_where(
                "documents", "id", {"url": f"ilike.*{ph}*"})
            print(f"  police-side host {ph}: {len(pdocs)} docs")

    # Which hosts feed each service's SIGNALS today: if the arcs draw entirely
    # from police-side hosts, the portals' contribution to arcs is zero even
    # where a stray keyword hit exists above.
    print("\n" + "=" * 78)
    print("WHERE THE FOUR SERVICES' SIGNALS ACTUALLY COME FROM")
    print("=" * 78)
    raw = sc.fetch_all_rows_where(
        "signals",
        "id,organizations(canonical_name),documents!inner(url)",
        {"suppressed": "is.false"})
    WANT = ("york regional police", "peel regional police",
            "london police", "durham regional police")
    per_org: dict[str, Counter] = {}
    for s in raw:
        org = s.get("organizations") or {}
        if isinstance(org, list):
            org = org[0] if org else {}
        name = (org.get("canonical_name") or "").lower()
        if any(w in name for w in WANT):
            host = urlparse((s.get("documents") or {}).get("url") or "").netloc
            per_org.setdefault(org.get("canonical_name"), Counter())[host] += 1
    if not per_org:
        print("  no signals resolved to these four services")
    for org, hosts in sorted(per_org.items()):
        total = sum(hosts.values())
        parts = ", ".join(f"{h} ({c})" for h, c in hosts.most_common())
        print(f"  {org}: {total} signals <- {parts}")

    print("\nprobe complete (read-only; nothing written)")


if __name__ == "__main__":
    main()
