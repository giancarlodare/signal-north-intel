"""ARC DIAGNOSTICS: four read-only questions in one run (operator 2026-07-29).

Writes nothing, calls no LLM. Answers, in order:

  S1  TORONTO CORPUS READ. Does the Toronto CKAN (tobids) corpus carry
      Toronto Police Service procurement, or is it city-wide purchasing that
      never touches a police arc? Decides the $163 Toronto drain slice.
      Also reports which hosts actually feed the census TPS/TPSB arc cells,
      since those may be an entirely different corpus (board minutes,
      bids&tenders) from the one the drain would pay to extract.

  S2  FUTURE-DATED published_on. The Halton 2026-08-27 instance, swept as a
      class: every document dated ahead of today, by host / source /
      doc_type, with the collector that wrote it named. Report only.

  S3  RECOVERABLE-MATERIAL ESTIMATES for the three arc constraints:
        (a) buyer resolution  -- unresolved-org signals, and how many carry
            a documents.buyer_name we could resolve from
        (b) board/service merge -- which buyer pairs are the board and the
            service of one body, and the SIMULATED before/after arc-cell and
            precedent-bar counts (the merge can drop thin categories below
            the two-buyer bar; this measures that rather than assuming)
        (c) categorization    -- uncategorized signals that are otherwise
            arc-grade (rung 2/3, dated, deep-linked, buyer-resolved)

  S4  REAL PRECEDENT COMPARABLES for the marketing sample arc. For the
      candidate categories, every other buyer carrying a dated outcome, with
      its earliest dated deep-linked precursor, the measured interval between
      them in months, and both URLs. A5 ships from this table or not at all.

Shares its arc definitions with scripts/arc_census.py by import, so the two
reports cannot drift apart.
"""
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
from src import supabase_client as sc  # noqa: E402
from arc_census import (  # noqa: E402
    MIN_PRECEDENT_BUYERS, OUTCOME_RUNGS, PRECURSOR_RUNGS, _d, _one,
    is_deep_linkable,
)

# Toronto's two hosts: the CKAN API host the collector actually reads, and
# the human-facing catalogue used as the publisher-artifact URL.
TORONTO_HOSTS = ("ckan0.cf.opendata.inter.prod-toronto.ca", "open.toronto.ca")
# Deliberately broad: a false positive here is cheap (I read the sample), a
# false negative would wrongly exclude Toronto from the drain.
POLICE_TERMS = ("police", "constable", "tps ", "cruiser", "body-worn",
                "body worn", "in-car camera", "firearm", "taser", "cew ",
                "forensic", "911", "emergency communication", "detention",
                "public safety", "law enforcement")

# Board/service pairs to test in the merge simulation. Each tuple is
# (canonical target, aliases folded into it). These are proposed, not
# applied: S3b measures what folding them would do.
MERGE_GROUPS = {
    "Toronto Police Service": ("Toronto Police Service Board",
                               "Toronto Police Services Board"),
    "Peel Regional Police": ("Peel Police Service Board",
                             "Peel Police Services Board"),
    "Greater Sudbury Police Service": ("Greater Sudbury Police Services",
                                       "Greater Sudbury Police Services Board"),
    "Halton Regional Police Service": ("Halton Police Board",
                                       "Halton Regional Police Services Board"),
    "York Regional Police": ("York Regional Police Services Board",),
    "Durham Regional Police Service": ("Durham Regional Police Services Board",),
    "Waterloo Regional Police Service": ("Waterloo Regional Police Services Board",),
}
# The marketing sample arc is a camera-fleet/evidence-renewal story.
A5_CATEGORIES = ("body-worn-cameras", "digital-evidence", "surveillance",
                 "radios-comms", "records-cad", "facilities")

RULE = "=" * 100


def host(url: str) -> str:
    return urlparse(url or "").netloc or "(no host)"


def police_hit(*fields: str) -> bool:
    blob = " ".join((f or "") for f in fields).lower()
    return any(t in blob for t in POLICE_TERMS)


# --------------------------------------------------------------------------
def s1_toronto(docs: list) -> None:
    print(RULE)
    print("S1  TORONTO CORPUS READ -- does the drain slice touch a police arc?")
    print(RULE)

    tor = [d for d in docs if host(d.get("url")) in TORONTO_HOSTS]
    captured = [d for d in tor if d.get("status") == "captured"]
    print(f"Toronto documents in the corpus: {len(tor)}")
    print(f"  of which CAPTURED (the drain-eligible slice): {len(captured)}")

    by_type = Counter(d.get("doc_type") or "(none)" for d in captured)
    print("\n  captured by doc_type:")
    for t, n in by_type.most_common():
        print(f"    {t:22s} {n:6d}")

    by_buyer = Counter(d.get("buyer_name") or "(none)" for d in tor)
    print("\n  buyer_name as stamped by the collector (all Toronto docs):")
    for b, n in by_buyer.most_common(10):
        print(f"    {str(b)[:44]:44s} {n:6d}")

    hits = [d for d in captured if police_hit(d.get("title"), d.get("content"))]
    pct = 100 * len(hits) / (len(captured) or 1)
    print(f"\n  POLICE-RELATED (title or content matches any of "
          f"{len(POLICE_TERMS)} terms): {len(hits)} / {len(captured)} "
          f"({pct:.1f}%)")
    print("\n  sample of matches (up to 15):")
    for d in hits[:15]:
        print(f"    {str(d.get('published_on'))[:10]}  "
              f"{(d.get('title') or '')[:88]}")
    if not hits:
        print("    (none)")

    print("\n  --- where the census TPS/TPSB arc cells actually come from ---")
    print("  (if these hosts are disjoint from Toronto CKAN, the drain slice")
    print("   buys no police arc material at all)")


def s1b_police_signal_hosts(sigs: list) -> None:
    per_buyer = defaultdict(Counter)
    for r in sigs:
        if "toronto police" not in (r["buyer"] or "").lower():
            continue
        per_buyer[r["buyer"]][r["host"]] += 1
    for buyer in sorted(per_buyer):
        print(f"\n  {buyer}: {sum(per_buyer[buyer].values())} signals")
        for h, n in per_buyer[buyer].most_common(8):
            mark = "   <-- TORONTO CKAN" if h in TORONTO_HOSTS else ""
            print(f"    {h:52s} {n:5d}{mark}")
    if not per_buyer:
        print("    (no Toronto Police signals found)")


# --------------------------------------------------------------------------
def s2_future_dates(docs: list, sources: dict) -> None:
    print("\n" + RULE)
    print("S2  FUTURE-DATED published_on (report only, nothing fixed)")
    print(RULE)
    today = date.today()
    future = []
    for d in docs:
        pd = _d(d.get("published_on"))
        if pd and pd > today:
            future.append((pd, d))
    future.sort(key=lambda t: t[0], reverse=True)
    print(f"today (UTC date): {today}")
    print(f"documents with published_on in the FUTURE: {len(future)} "
          f"of {len(docs)} ({100 * len(future) / (len(docs) or 1):.2f}%)")
    if not future:
        return

    print("\n  by host:")
    for h, n in Counter(host(d.get("url")) for _, d in future).most_common(20):
        print(f"    {h:52s} {n:6d}")
    print("\n  by doc_type:")
    for t, n in Counter(d.get("doc_type") or "(none)" for _, d in future).most_common():
        print(f"    {t:22s} {n:6d}")
    print("\n  by source (names the collector that wrote it):")
    for s, n in Counter(sources.get(d.get("source_id"), "(unknown source)")
                        for _, d in future).most_common(20):
        print(f"    {str(s)[:52]:52s} {n:6d}")
    print("\n  by date_precision:")
    for p, n in Counter(d.get("date_precision") or "(none)" for _, d in future).most_common():
        print(f"    {str(p):22s} {n:6d}")

    print("\n  how far ahead:")
    buckets = Counter()
    for pd, _ in future:
        days = (pd - today).days
        buckets["<= 30d" if days <= 30 else
                "31-90d" if days <= 90 else
                "91-365d" if days <= 365 else "> 1 year"] += 1
    for b in ("<= 30d", "31-90d", "91-365d", "> 1 year"):
        if buckets[b]:
            print(f"    {b:10s} {buckets[b]:6d}")

    print("\n  the 25 furthest-ahead rows (published_on | doc_type | title | url):")
    for pd, d in future[:25]:
        print(f"    {pd}  {(d.get('doc_type') or '')[:14]:14s} "
              f"{(d.get('title') or '')[:52]:52s} {(d.get('url') or '')[:60]}")


# --------------------------------------------------------------------------
def s3_constraints(sigs: list) -> None:
    print("\n" + RULE)
    print("S3  RECOVERABLE-MATERIAL ESTIMATES (the three constraints)")
    print(RULE)

    ps = [r for r in sigs if r["public_safety"]]

    # --- (a) buyer resolution --------------------------------------------
    print("\n(a) BUYER RESOLUTION")
    unres = [r for r in ps if not r["resolved"]]
    print(f"    public-safety signals with NO resolved organization: {len(unres)}")
    arcgrade = [r for r in unres
                if r["grade"] in PRECURSOR_RUNGS and r["date"] and r["deep"]]
    print(f"      of which otherwise ARC-GRADE (rung 2/3, dated, deep-linked):"
          f" {len(arcgrade)}   <-- the recoverable precursor material")
    withname = [r for r in arcgrade if r["doc_buyer"]]
    print(f"      of those, documents.buyer_name already present: "
          f"{len(withname)}   <-- recoverable by mapping, no re-read")
    print("\n    arc-grade unresolved, by documents.buyer_name (top 20):")
    for b, n in Counter(r["doc_buyer"] or "(no buyer_name)"
                        for r in arcgrade).most_common(20):
        print(f"      {str(b)[:52]:52s} {n:5d}")
    print("\n    arc-grade unresolved, by host (top 15):")
    for h, n in Counter(r["host"] for r in arcgrade).most_common(15):
        print(f"      {h:52s} {n:5d}")

    # --- (b) board/service merge simulation -------------------------------
    print("\n(b) BOARD/SERVICE MERGE -- simulated before/after")
    present = Counter(r["buyer"] for r in ps)
    alias_to_target = {}
    for target, aliases in MERGE_GROUPS.items():
        for a in aliases:
            alias_to_target[a] = target
    print("    pairs found in the corpus (signal counts):")
    for target, aliases in MERGE_GROUPS.items():
        live = [(a, present[a]) for a in aliases if present.get(a)]
        if present.get(target) or live:
            parts = ", ".join(f"{a}={n}" for a, n in live) or "no alias present"
            print(f"      {target} = {present.get(target, 0)}  <- {parts}")

    before = _cells(ps, lambda b: b)
    after = _cells(ps, lambda b: alias_to_target.get(b, b))
    print(f"\n    {'':28s} {'BEFORE':>10s} {'AFTER':>10s} {'delta':>8s}")
    for label, key in (("arc-ready cells", "ready"),
                       ("...with precedent set", "with_prec"),
                       ("...that LOSE precedent", "lost_prec"),
                       ("distinct buyers", "buyers"),
                       ("mean precursors per cell", "mean_pre")):
        b_, a_ = before[key], after[key]
        if isinstance(b_, float):
            print(f"    {label:28s} {b_:10.1f} {a_:10.1f} {a_ - b_:+8.1f}")
        else:
            print(f"    {label:28s} {b_:10d} {a_:10d} {a_ - b_:+8d}")
    print("\n    categories that DROP below the "
          f"{MIN_PRECEDENT_BUYERS}-buyer precedent bar because of the merge:")
    dropped = sorted(set(before["prec_ok_cats"]) - set(after["prec_ok_cats"]))
    for c in dropped:
        print(f"      {c}")
    if not dropped:
        print("      (none)")

    # --- (c) categorization ----------------------------------------------
    print("\n(c) CATEGORIZATION")
    uncat = [r for r in ps if r["category"] == "(uncategorized)"]
    print(f"    public-safety signals with no category: {len(uncat)} "
          f"({100 * len(uncat) / (len(ps) or 1):.0f}% of public-safety)")
    uncat_arc = [r for r in uncat if r["grade"] in PRECURSOR_RUNGS
                 and r["date"] and r["deep"] and r["resolved"]]
    print(f"      of which ARC-GRADE precursors: {len(uncat_arc)}"
          f"   <-- recoverable arc material stuck in the bucket")
    print("\n    uncategorized arc-grade, by buyer (top 15):")
    for b, n in Counter(r["buyer"] for r in uncat_arc).most_common(15):
        print(f"      {str(b)[:52]:52s} {n:5d}")
    print("\n    uncategorized arc-grade, by doc_type:")
    for t, n in Counter(r["doc_type"] or "(none)" for r in uncat_arc).most_common():
        print(f"      {str(t):22s} {n:5d}")


def _cells(ps: list, keyfn) -> dict:
    """Arc-cell counts under a buyer-naming function, for the merge sim."""
    cell_pre = defaultdict(list)
    cell_all = Counter()
    outcome_buyers = defaultdict(set)
    for r in ps:
        b = keyfn(r["buyer"])
        cell_all[(b, r["category"])] += 1
        if (r["grade"] in PRECURSOR_RUNGS and r["date"] and r["deep"]
                and r["resolved"]):
            cell_pre[(b, r["category"])].append(r)
        if r["grade"] in OUTCOME_RUNGS and r["date"] and r["resolved"]:
            outcome_buyers[r["category"]].add(b)
    ready = with_prec = lost = 0
    pre_counts = []
    prec_ok_cats = set()
    for (b, cat), pres in cell_pre.items():
        if cell_all[(b, cat)] - len(pres) < 1:
            continue
        ready += 1
        pre_counts.append(len(pres))
        others = outcome_buyers.get(cat, set()) - {b}
        if len(others) >= MIN_PRECEDENT_BUYERS:
            with_prec += 1
            prec_ok_cats.add(cat)
        else:
            lost += 1
    return {"ready": ready, "with_prec": with_prec, "lost_prec": lost,
            "buyers": len({keyfn(r["buyer"]) for r in ps}),
            "mean_pre": (sum(pre_counts) / len(pre_counts)) if pre_counts else 0.0,
            "prec_ok_cats": prec_ok_cats}


# --------------------------------------------------------------------------
def s4_precedents(sigs: list) -> None:
    print("\n" + RULE)
    print("S4  REAL PRECEDENT COMPARABLES (A5 ships from this or not at all)")
    print(RULE)
    ps = [r for r in sigs if r["public_safety"] and r["resolved"]]
    for cat in A5_CATEGORIES:
        rows = [r for r in ps if r["category"] == cat]
        outcomes = defaultdict(list)   # buyer -> outcome recs
        precs = defaultdict(list)      # buyer -> precursor recs
        for r in rows:
            if r["grade"] in OUTCOME_RUNGS and r["date"]:
                outcomes[r["buyer"]].append(r)
            if r["grade"] in PRECURSOR_RUNGS and r["date"] and r["deep"]:
                precs[r["buyer"]].append(r)
        print(f"\n  CATEGORY: {cat}   "
              f"buyers with a dated outcome: {len(outcomes)}")
        if not outcomes:
            print("    (no dated outcome in this category)")
            continue
        print(f"    {'buyer':34s} {'first precursor':>15s} "
              f"{'outcome':>11s} {'months':>7s}  deep-linked?")
        for buyer in sorted(outcomes):
            out = min(outcomes[buyer], key=lambda r: r["date"])
            pr = min(precs[buyer], key=lambda r: r["date"]) if precs.get(buyer) else None
            if pr and pr["date"] <= out["date"]:
                months = round((out["date"] - pr["date"]).days / 30.44, 1)
                span = f"{months:7.1f}"
                first = str(pr["date"])
            else:
                span = f"{'--':>7s}"
                first = "(none before)"
            print(f"    {buyer[:34]:34s} {first:>15s} "
                  f"{str(out['date']):>11s} {span}  "
                  f"pre={'Y' if pr and pr['deep'] else 'n'} "
                  f"out={'Y' if out['deep'] else 'n'}")
            if pr:
                print(f"        precursor: {pr['url'][:110]}")
            print(f"        outcome  : {out['url'][:110]}")


# --------------------------------------------------------------------------
def main() -> int:
    print("ARC DIAGNOSTICS -- read-only, writes nothing\n")

    # Corpus-wide pass deliberately omits `content`: the body column runs to
    # tens of thousands of characters per board-minutes row and pulling it for
    # every document would move hundreds of MB for two counts.
    docs = sc.fetch_all_rows_where(
        "documents",
        "id,source_id,doc_type,status,url,title,published_on,"
        "date_precision,buyer_name",
        {})
    print(f"documents scanned: {len(docs)}")
    # Toronto slice only, WITH bodies, so the police-term scan reads the real
    # text and not just the title.
    tor_docs = sc.fetch_all_rows_where(
        "documents",
        "id,source_id,doc_type,status,url,title,content,published_on,buyer_name",
        {"url": "ilike.*toronto*"})
    print(f"Toronto-host documents pulled with bodies: {len(tor_docs)}")
    sources = {s["id"]: s.get("name")
               for s in sc.fetch_rows("sources", "id,name")}

    raw = sc.fetch_all_rows_where(
        "signals",
        "id,evidence_grade,public_safety,suppressed,organization_id,"
        "organizations(canonical_name),categories(slug),"
        "documents!inner(id,doc_type,published_on,url,buyer_name)",
        {"suppressed": "is.false"})
    sigs = []
    for s in raw:
        org = _one(s.get("organizations")) or {}
        cat = _one(s.get("categories")) or {}
        doc = _one(s.get("documents")) or {}
        buyer = org.get("canonical_name")
        url = doc.get("url") or ""
        sigs.append({
            "buyer": buyer or "(unresolved buyer)",
            "resolved": bool(buyer),
            "category": cat.get("slug") or "(uncategorized)",
            "grade": s.get("evidence_grade") or 0,
            "public_safety": bool(s.get("public_safety")),
            "date": _d(doc.get("published_on")),
            "deep": is_deep_linkable(url),
            "url": url,
            "host": host(url),
            "doc_type": doc.get("doc_type"),
            "doc_buyer": doc.get("buyer_name"),
        })
    print(f"signals scanned (unsuppressed): {len(sigs)}\n")

    s1_toronto(tor_docs)
    s1b_police_signal_hosts(sigs)
    s2_future_dates(docs, sources)
    s3_constraints(sigs)
    s4_precedents(sigs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
