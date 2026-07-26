"""Re-clustered pilot staging v2 (coherent domains, doctrine 0f).

READ-ONLY. Applies the operator's linking doctrine (2026-07-26) to the
tier-A material before adjudication:

  RULE 1: grade-1 signals (chatter / pressure) NEVER link. They are
     domain-pressure indicators; advocacy-to-award is a fabricated link at
     any granularity. Counted per (buyer, domain), not clustered.
  RULE 2: uncategorized-scope groups are incoherent by construction and
     are excluded until categorized (counted, not clustered).
  RULE 3: within (buyer, category), signals sub-cluster by INSTRUMENT via
     shared rare title tokens (vendor and product names). A token is an
     instrument marker when it appears in 2..MAX_TOKEN_SPREAD signals of
     the category (rarer = identifying; category-frequent = generic).
     Union-find joins signals sharing a marker.

Output, in adjudicable form:
  INSTRUMENT THREADS: multi-signal sub-clusters, strongest first. Each
     shows its signals (grade/date/title/source URL), the shared
     instrument tokens as evidence, and confidence MEDIUM (title-token
     identity; no structured reference exists for these).
  DOMAIN RHYTHM groups: per (buyer, category), the leftover grade 2/3
     commitment pool + the category's grade 4/5 activity. Confirmable
     only as a RHYTHM measurement (doctrine 0f), never as an arc.

    python scripts/stage_proposer_pilot2.py
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import procurements, supabase_client

PILOT_ORG_MARKERS = ("toronto", "peel")
MAX_TOKEN_SPREAD = 5     # a token in more signals than this is generic
STOPWORDS = {
    # procurement vocabulary and org words, lowercased
    "contract", "contracts", "award", "awards", "awarded", "tender",
    "tenders", "extension", "extended", "renewal", "renewals", "services",
    "service", "board", "police", "regional", "toronto", "peel", "york",
    "city", "region", "budget", "operating", "capital", "program", "unit",
    "request", "approved", "approval", "agenda", "minutes", "meeting",
    "public", "report", "purchase", "supply", "equipment", "vehicle",
    "vehicles", "provision", "agreement", "increase", "year", "years",
    "million", "the", "and", "for", "with", "from", "inc", "ltd", "corp",
    "chief", "member", "members", "new", "update", "expansion", "project",
    "phase", "annual", "quarterly", "fleet", "system", "systems",
    "tps", "prp", "yrp", "wrps", "gsps", "drps", "hrps", "tpsb", "ppsb",
    # civic/structure generics that falsely join distinct instruments (found
    # in the first staging: 'division' joined 11 Division EV charging to 23
    # Division construction)
    "division", "divisions", "council", "centre", "center", "station",
    "stations", "facility", "facilities", "building", "buildings", "street",
    "streets", "road", "roads", "avenue", "headquarters", "hall", "north",
    "south", "east", "west", "canada", "ontario", "america", "community",
    "general", "management", "team", "technology",
}


def _one(embedded):
    if isinstance(embedded, list):
        return embedded[0] if embedded else None
    return embedded


def pilot_org(signal) -> bool:
    org = _one(signal.get("organizations")) or {}
    return any(m in (org.get("canonical_name") or "").lower()
               for m in PILOT_ORG_MARKERS)


def instrument_tokens(title: str) -> set:
    """Candidate instrument/vendor tokens: capitalized or digit-bearing
    words of length >= 3, minus procurement vocabulary. 'D&R', 'Havis',
    'Setina', '911', 'ALPR' all survive; 'Contract Award to' does not."""
    out = set()
    for w in re.findall(r"[A-Za-z0-9&'’.-]{3,}", title or ""):
        bare = w.strip(".,'’-")
        if len(bare) < 3:
            continue
        if bare.lower() in STOPWORDS:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?[km]", bare.lower()):
            continue          # a bare dollar amount is not an instrument
        if re.fullmatch(r"(?:19|20)\d{2}(?:-(?:19|20)\d{2})?", bare):
            continue          # a year or year range is not an instrument
        if bare[0].isupper() or any(ch.isdigit() for ch in bare) or "&" in bare:
            out.add(bare.lower())
    return out


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def fmt_signal(s) -> str:
    doc = _one(s.get("documents")) or {}
    grade = s.get("evidence_grade")
    label = procurements.stage_label(grade) if isinstance(grade, int) else "?"
    return (f"      [{grade}:{label}] {doc.get('published_on') or 'date unknown'} "
            f":: {(s.get('title') or '(untitled)')[:110]}\n"
            f"        src: {(doc.get('url') or '')[:120]}")


def main() -> int:
    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,organization_id,category_id,evidence_grade,title,"
        "organizations(canonical_name),categories(slug,name),"
        "documents(url,title,published_on,reference_number)",
        {"organization_id": "not.is.null", "evidence_grade": "not.is.null",
         "suppressed": "is.false"})
    pilot = [s for s in signals if pilot_org(s)]

    links = supabase_client.fetch_all_rows_where(
        "procurement_signals", "procurement_id,signal_id", {})
    linked_sids = {l["signal_id"] for l in links}
    unlinked = [s for s in pilot if s["id"] not in linked_sids]

    pressure_held = Counter()
    uncategorized_held = Counter()
    by_domain = defaultdict(list)
    for s in unlinked:
        org = _one(s.get("organizations")) or {}
        buyer = org.get("canonical_name") or "?"
        cat = _one(s.get("categories")) or {}
        scope = (cat.get("name") or "").strip()
        if s.get("evidence_grade") == 1:
            pressure_held[(buyer, scope or "(uncategorized)")] += 1   # RULE 1
            continue
        if not scope:
            uncategorized_held[buyer] += 1                            # RULE 2
            continue
        by_domain[(buyer, scope)].append(s)

    threads = []
    rhythm_groups = []
    for (buyer, scope), sigs in by_domain.items():
        token_map = defaultdict(list)
        for s in sigs:
            for t in instrument_tokens(s.get("title") or ""):
                token_map[t].append(s["id"])
        markers = {t: ids for t, ids in token_map.items()
                   if 2 <= len(set(ids)) <= MAX_TOKEN_SPREAD}
        uf = UnionFind()
        for ids in markers.values():
            first = ids[0]
            for other in ids[1:]:
                uf.union(first, other)
        clusters = defaultdict(list)
        s_by_id = {s["id"]: s for s in sigs}
        for s in sigs:
            clusters[uf.find(s["id"])].append(s)

        leftover_commit, leftover_activity = [], []
        for members in clusters.values():
            if len(members) >= 2:
                mtokens = sorted(t for t, ids in markers.items()
                                 if set(ids) <= {m["id"] for m in members}
                                 or all(i in {m["id"] for m in members} for i in ids))
                threads.append({
                    "buyer": buyer, "scope": scope, "signals": members,
                    "tokens": mtokens,
                    "grades": sorted({m["evidence_grade"] for m in members}),
                })
            else:
                m = members[0]
                (leftover_commit if m["evidence_grade"] in (2, 3)
                 else leftover_activity).append(m)
        if leftover_commit and leftover_activity:
            rhythm_groups.append({
                "buyer": buyer, "scope": scope,
                "commitments": leftover_commit, "activity": leftover_activity})

    threads.sort(key=lambda t: (-len(t["grades"]), -len(t["signals"])))

    print(f"PILOT RE-CLUSTER v2: {len(pilot)} pilot signals, "
          f"{len(unlinked)} unlinked after tier-B apply")
    print(f"RULE 1 held (grade-1 pressure/chatter, never linked): "
          f"{sum(pressure_held.values())} across {len(pressure_held)} (buyer, domain) pairs")
    print(f"RULE 2 held (uncategorized scope): {dict(uncategorized_held)}")

    print("\n" + "=" * 76)
    print(f"INSTRUMENT THREADS ({len(threads)}) - confirm each; confidence "
          f"MEDIUM (shared instrument tokens)")
    print("=" * 76)
    for i, t in enumerate(threads, 1):
        cross = " CROSS-RUNG" if len(t["grades"]) >= 2 else ""
        print(f"\n[T{i}]{cross} {t['buyer']} :: {t['scope']} "
              f"grades={t['grades']} signals={len(t['signals'])}")
        print(f"    EVIDENCE: shared instrument tokens {t['tokens'][:6]}")
        for s in sorted(t["signals"],
                        key=lambda x: ((_one(x.get('documents')) or {}).get('published_on') or "")):
            print(fmt_signal(s))

    print("\n" + "=" * 76)
    print(f"DOMAIN RHYTHM GROUPS ({len(rhythm_groups)}) - confirmable as "
          f"rhythm measurements ONLY (doctrine 0f), never as arcs")
    print("=" * 76)
    for i, g in enumerate(rhythm_groups, 1):
        c_dates = sorted((_one(s.get('documents')) or {}).get('published_on') or "?"
                         for s in g["commitments"])
        a_dates = sorted((_one(s.get('documents')) or {}).get('published_on') or "?"
                         for s in g["activity"])
        print(f"\n[R{i}] {g['buyer']} :: {g['scope']}")
        print(f"    commitment pool: {len(g['commitments'])} "
              f"({c_dates[0]}..{c_dates[-1]})")
        print(f"    activity (grade 4/5): {len(g['activity'])} "
              f"({a_dates[0]}..{a_dates[-1]})")
        for s in g["commitments"][:3]:
            print(fmt_signal(s))
        if len(g["commitments"]) > 3:
            print(f"      ... {len(g['commitments']) - 3} more commitments")

    print(f"\nSUMMARY: instrument_threads={len(threads)} "
          f"(cross-rung: {sum(1 for t in threads if len(t['grades']) >= 2)}), "
          f"rhythm_groups={len(rhythm_groups)}, "
          f"pressure_held={sum(pressure_held.values())}, "
          f"uncategorized_held={sum(uncategorized_held.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
