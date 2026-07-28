"""Coverage-and-flow audit (operator request 2026-07-28): real numbers on
(1) what is live vs gapped, (2) what the filters HOLD OUT, with samples to
eyeball for over-filtering, (3) what actually flowed in the last 7/14 days.

Read-only: DB reads plus one live re-read of the CanadaBuys new-tenders CSV
to show exactly which notices the keep-filter drops today. No writes, no LLM.
Run from CI (sandbox blocks the DB and canadabuys.ca):
    python scripts/audit_coverage_flow.py
"""
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import config, supabase_client
from src.filters import evaluate, load_keywords
from src.main import fetch_csv_rows, parse_tender_row


def section(title):
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def main() -> int:
    now = datetime.now(timezone.utc)
    d7 = (now - timedelta(days=7)).isoformat()
    d14 = (now - timedelta(days=14)).isoformat()

    section("A. SOURCES REGISTERED IN THE DB (presence = enabled)")
    sources = supabase_client.fetch_all_rows_where(
        "sources", "id,name,source_type,jurisdiction,cadence", {})
    by_jur = defaultdict(list)
    for s in sources:
        by_jur[s.get("jurisdiction") or "?"].append(s)
    for jur in sorted(by_jur):
        print(f"\n  [{jur}] {len(by_jur[jur])} sources")
        for s in sorted(by_jur[jur], key=lambda x: x["name"]):
            print(f"    - {s['name']}  ({s.get('cadence')})")
    src_name = {s["id"]: s["name"] for s in sources}

    section("B. DOCUMENT FLOW, LAST 7 / 14 DAYS (created_at)")
    docs14 = supabase_client.fetch_all_rows_where(
        "documents", "id,doc_type,title,published_on,created_at,source_id,"
        "defence_relevant", {"created_at": f"gte.{d14}"})
    docs7 = [d for d in docs14 if d["created_at"] >= d7]
    for label, docs in (("last 14 days", docs14), ("last 7 days", docs7)):
        c = Counter(d.get("doc_type") or "?" for d in docs)
        print(f"\n  NEW documents {label}: {len(docs)} total")
        for t, n in c.most_common():
            print(f"    {t:<20} {n}")
    print("\n  by source (14d):")
    cs = Counter(src_name.get(d.get("source_id"), "?") for d in docs14)
    for name, n in cs.most_common():
        print(f"    {name[:56]:<58} {n}")

    def sample(doc_type, k):
        rows = sorted((d for d in docs14 if d.get("doc_type") == doc_type),
                      key=lambda d: d["created_at"], reverse=True)[:k]
        print(f"\n  newest {doc_type} ({min(k, len(rows))} of {sum(1 for d in docs14 if d.get('doc_type') == doc_type)} in 14d):")
        for d in rows:
            print(f"    {str(d.get('published_on'))[:10]}  {(d.get('title') or '(no title)')[:88]}")

    for t, k in (("tender_notice", 15), ("award_notice", 8),
                 ("grant_program", 6), ("grant_award", 6),
                 ("board_minutes", 6), ("news_release", 6)):
        sample(t, k)

    section("C. HELD PILE 1: keep-filter drops on TODAY'S CanadaBuys feed")
    keywords = load_keywords()
    rows = fetch_csv_rows(config.NEW_TENDER_NOTICES_URL)
    kept, dropped = [], []
    if rows:
        fields = list(rows[0].keys())
        for row in rows:
            t = parse_tender_row(row, fields)
            r = evaluate(t["title"], t["description"], t["unspsc_raw"], keywords)
            (kept if r.kept else dropped).append((t, r))
    print(f"\n  today's feed: {len(rows)} notices; KEPT {len(kept)}, "
          f"DROPPED {len(dropped)}"
          + (f" ({100 * len(dropped) / len(rows):.0f}% dropped)" if rows else ""))
    print("\n  sample of DROPPED notices (eyeball for over-filtering):")
    for t, _ in dropped[:20]:
        print(f"    - {(t['title'] or '')[:76]}  | buyer: {(t['buyer_name'] or '?')[:40]}")
    print("\n  sample of KEPT (what cleared, and why):")
    for t, r in kept[:8]:
        why = r.matched_keyword or f"unspsc {r.matched_unspsc_segment}"
        print(f"    - {(t['title'] or '')[:66]}  | {why}")

    section("D. HELD PILE 2: member-hidden signals (public_safety = false)")
    sigs = supabase_client.fetch_all_rows_where(
        "signals", "id,title,public_safety,suppressed", {"suppressed": "is.false"})
    n_true = sum(1 for s in sigs if s.get("public_safety"))
    n_false = len(sigs) - n_true
    print(f"\n  live signals: {len(sigs)}; member-VISIBLE (public_safety) "
          f"{n_true}; member-HIDDEN {n_false}")
    print("\n  sample of member-HIDDEN signal titles (held from the portal):")
    for s in [s for s in sigs if not s.get("public_safety")][:20]:
        print(f"    - {(s.get('title') or '(untitled)')[:88]}")

    section("E. HELD PILE 3: defence tag after the re-tag")
    dts = supabase_client.fetch_all_rows_where(
        "documents", "id", {"defence_relevant": "is.true"})
    print(f"\n  documents currently defence-tagged: {len(dts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
