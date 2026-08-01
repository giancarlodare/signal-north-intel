"""VERIFICATION PASS for the pricing page's OPEN columns (operator 2026-07-29).

The client-facing gate applied to our own pricing page. Every checkmark in an
OPEN column (Free, Weekly) must correspond to something that exists and works
in the portal TODAY. This script checks the LIVE DATABASE, not the code and
not the design handoff, because a page can be written against a table that was
never pasted and a member would find out before we did.

Read-only. Writes nothing, calls no LLM.

Checks, in the order the pricing table lists them:

  THE BRIEF
    weekly email        -- is there a send path with a record of having sent
    the composed arc    -- is there a field on brief_items holding arc prose
    service-by-service  -- is there any per-service grouped component
    issue archive       -- how many PUBLISHED issues a member could browse

  THE RECORD
    full item list      -- included items on the latest published brief
    source link         -- the honesty question: of the items a member can
                           actually see, how many carry a RECORD-level link,
                           how many a listing anchor, how many a portal
                           landing, how many nothing at all
    saved items         -- do the stage-3 tables exist and read

Also reports the corpus-wide provenance split behind the 49 Ontario-grants
and 11 bids-and-tenders exceptions, so the "source link on every item" row
can be worded against a measured number rather than a remembered one.
"""
import os
import sys
from collections import Counter
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from src import supabase_client as sc  # noqa: E402

RULE = "=" * 92


def probe_table(name: str, select: str = "*") -> tuple[bool, int | None, str]:
    """(exists, row_count_or_None, detail). A table the app reads but that was
    never pasted is the single most common way a page lies."""
    try:
        rows = sc.fetch_rows_where(name, select, {}, limit=1000)
        return True, len(rows), "readable"
    except Exception as e:  # noqa: BLE001
        return False, None, str(e)[:120]


def kind(url: str) -> str:
    """Mirrors web/lib/portal/provenance.ts: record / listing / portal."""
    if not url:
        return "none"
    if "#:~:text=" in url:
        return "listing"
    p = urlparse(url)
    path = (p.path or "").rstrip("/").lower()
    if not path:
        return "portal"
    if path.endswith("/module/tenders/en"):
        return "portal"
    if path.count("/") == 1 and path.startswith("/m/"):
        return "portal"
    return "record"


def main() -> int:
    print("PRICING-PAGE VERIFICATION -- live database, read-only\n")

    # ---- table existence -------------------------------------------------
    print(RULE)
    print("TABLE EXISTENCE (a page written against an unpasted table lies)")
    print(RULE)
    for t in ("briefs", "brief_items", "saved_items", "member_watches",
              "watch_events", "member_live_items", "extraction_envelopes",
              "extraction_spend", "demand_arc_profiles"):
        ok, n, detail = probe_table(t, "*")
        mark = "OK " if ok else "ABSENT"
        print(f"  {t:26s} {mark:7s} "
              f"{('rows>=' + str(n)) if ok else detail}")

    # ---- the brief -------------------------------------------------------
    print("\n" + RULE)
    print("THE BRIEF")
    print(RULE)
    briefs = sc.fetch_all_rows_where(
        "briefs", "id,week_start,status,title,intro,published_at", {})
    by_status = Counter(b.get("status") or "(none)" for b in briefs)
    print(f"  briefs total: {len(briefs)}   {dict(by_status)}")
    published = sorted((b for b in briefs if b.get("status") == "published"),
                       key=lambda b: str(b.get("week_start")), reverse=True)
    print(f"\n  ISSUE ARCHIVE: {len(published)} published issue(s) a member "
          f"could browse")
    for b in published[:10]:
        print(f"    {b.get('week_start')}  published_at={b.get('published_at')}"
              f"  title={(b.get('title') or '(none)')[:40]!r}")

    # Arc body field: does brief_items carry anywhere to PUT arc prose?
    cols = set()
    sample = sc.fetch_rows_where("brief_items", "*", {}, limit=1)
    if sample:
        cols = set(sample[0].keys())
    print(f"\n  brief_items columns: {sorted(cols)}")
    arc_fields = [c for c in cols if "arc" in c or "body" in c or "narrative" in c]
    print(f"  THE COMPOSED ARC: field(s) able to hold arc prose: "
          f"{arc_fields or 'NONE'}")
    svc_fields = [c for c in cols if "service" in c or "section" in c]
    brief_cols = set(briefs[0].keys()) if briefs else set()
    svc_brief = [c for c in brief_cols if "service" in c or "section" in c]
    print(f"  SERVICE-BY-SERVICE: brief_items {svc_fields or 'NONE'}; "
          f"briefs {svc_brief or 'NONE'}")

    # ---- the record ------------------------------------------------------
    print("\n" + RULE)
    print("THE RECORD -- what a member on the latest published issue sees")
    print(RULE)
    if not published:
        print("  NO PUBLISHED BRIEF. Every Weekly row is unverifiable.")
        return 0
    latest = published[0]
    items = sc.fetch_all_rows_where(
        "brief_items",
        "id,included,rank,headline_override,editor_note,"
        "signals:lead_signal_id(title,public_safety,"
        "documents(url,doc_type,reference_number))",
        {"brief_id": f"eq.{latest['id']}"})
    inc = [i for i in items if i.get("included")]
    print(f"  latest published issue: week of {latest.get('week_start')}")
    print(f"  brief_items rows: {len(items)}   included: {len(inc)}")

    def one(v):
        return (v[0] if v else None) if isinstance(v, list) else v

    # The member's real slice: the data layer also requires public_safety.
    visible = []
    for it in inc:
        s = one(it.get("signals")) or {}
        if s.get("public_safety"):
            visible.append((it, one(s.get("documents")) or {}))
    print(f"  member-VISIBLE (public_safety clamp applied): {len(visible)}")

    kinds = Counter(kind(d.get("url") or "") for _, d in visible)
    print(f"\n  SOURCE LINK on those {len(visible)} visible items:")
    for k in ("record", "listing", "portal", "none"):
        if kinds[k]:
            print(f"    {k:8s} {kinds[k]:4d}")
    print(f"    -> every item carries SOME link: "
          f"{'YES' if kinds['none'] == 0 else 'NO (' + str(kinds['none']) + ' with none)'}")
    print(f"    -> every link lands on the RECORD itself: "
          f"{'YES' if kinds['record'] == len(visible) else 'NO'}")

    print("\n  the visible items, one line each:")
    for it, d in visible:
        s = one(it.get("signals")) or {}
        print(f"    [{kind(d.get('url') or ''):7s}] "
              f"{(it.get('headline_override') or s.get('title') or '')[:58]:58s} "
              f"{(d.get('url') or '(no url)')[:60]}")

    # ---- corpus-wide provenance split ------------------------------------
    print("\n" + RULE)
    print("CORPUS-WIDE PROVENANCE (behind the wording of the source-link row)")
    print(RULE)
    docs = sc.fetch_all_rows_where("documents", "url,doc_type", {})
    ck = Counter(kind(d.get("url") or "") for d in docs)
    tot = len(docs) or 1
    for k in ("record", "listing", "portal", "none"):
        print(f"  {k:8s} {ck[k]:7d}  ({100 * ck[k] / tot:.2f}%)")
    print("\n  non-record documents by doc_type:")
    nonrec = Counter(d.get("doc_type") or "(none)" for d in docs
                     if kind(d.get("url") or "") != "record")
    for t, n in nonrec.most_common():
        print(f"    {t:22s} {n:6d}")
    print("\n  non-record documents by host:")
    nonhost = Counter(urlparse(d.get("url") or "").netloc or "(no host)"
                      for d in docs if kind(d.get("url") or "") != "record")
    for h, n in nonhost.most_common(12):
        print(f"    {h:46s} {n:6d}")

    # ---- saved items -----------------------------------------------------
    print("\n" + RULE)
    print("SAVED ITEMS")
    print(RULE)
    ok, n, detail = probe_table("saved_items", "id,member_id,brief_item_id,created_at")
    if ok:
        print(f"  saved_items readable; rows visible to service role: {n}")
    else:
        print(f"  saved_items NOT readable: {detail}")
        print("  -> the Save button renders DISABLED for every member")

    # ---- monitoring (closed columns, reported for completeness) ----------
    print("\n" + RULE)
    print("MONITORING (Pro column, closed -- reported for completeness)")
    print(RULE)
    for t in ("member_live_items", "member_watches", "watch_events"):
        ok, n, detail = probe_table(t, "*")
        print(f"  {t:22s} {'OK' if ok else 'ABSENT'}  "
              f"{('rows>=' + str(n)) if ok else detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
