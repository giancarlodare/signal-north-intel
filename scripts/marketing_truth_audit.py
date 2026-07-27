"""Marketing-site truth audit (operator 2026-07-27).

Computes every live-data claim on the marketing site from the actual
database, using EXACTLY the definitions the marketing_* functions in
migrations/2026-07-27_marketing_public_data.sql use, so the operator can
confirm the site is truthful today and see what each wired section will
show. Also probes contract_awards.created_at (the recently-added ordering
question) and prints the enabled-source list for the coverage commitments.

Read-only; prints a report, writes nothing.

    python scripts/marketing_truth_audit.py
"""
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, ".")

from src import supabase_client


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def main():
    today = date.today()

    orgs = supabase_client.fetch_all_rows_where(
        "organizations", "id,canonical_name,org_type", {})
    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,organization_id,suppressed,title,evidence_grade,"
        "documents!inner(id,doc_type,published_on)",
        {"suppressed": "is.false"})
    awards = supabase_client.fetch_all_rows_where(
        "contract_awards",
        "id,vendor_name,description,value_cad,awarded_on,end_on,final_end_on", {})
    # sources has no enabled flag: a row existing IS registration (seeds are
    # only inserted for enabled feeds; parked collectors gate in code).
    sources = supabase_client.fetch_all_rows_where(
        "sources", "id,name,source_type,jurisdiction", {})

    org_by_id = {o["id"]: o for o in orgs}
    orgs_with_signal = {s["organization_id"] for s in signals
                        if s.get("organization_id")}

    def on_record(types):
        return sorted(
            o["canonical_name"] for o in orgs
            if o["org_type"] in types and o["id"] in orgs_with_signal)

    services = on_record({"police_service"})
    boards = on_record({"police_board"})
    councils = on_record({"municipality"})
    ministries = on_record({"provincial_ministry", "federal_department"})

    print("=== STAT: police services and oversight boards (stated 44) ===")
    print(f"    REAL: {len(services) + len(boards)} "
          f"({len(services)} services + {len(boards)} boards)")
    print("=== STAT: councils, ministries and departments (stated 112) ===")
    print(f"    REAL: {len(councils) + len(ministries)} "
          f"({len(councils)} councils + {len(ministries)} ministries/departments)")

    def end_date(a):
        raw = a.get("final_end_on") or a.get("end_on")
        try:
            return date.fromisoformat((raw or "")[:10])
        except ValueError:
            return None

    live = [a for a in awards if (end_date(a) or date.min) >= today]
    live_value = sum(float(a["value_cad"]) for a in live if a.get("value_cad"))
    awarded_dates = sorted(a["awarded_on"] for a in awards if a.get("awarded_on"))
    years = 0
    if awarded_dates:
        first = date.fromisoformat(awarded_dates[0][:10])
        years = (today - first).days // 365

    print("=== STAT: contracts held with end dates, live (stated 2,900+) ===")
    print(f"    REAL: {len(live)} live of {len(awards)} total awards "
          f"({sum(1 for a in awards if end_date(a))} carry any end date)")
    print("=== STAT: live contract value on record (stated $4.1B) ===")
    print(f"    REAL: ${live_value:,.0f} over live agreements; "
          f"all-awards disclosed total ${sum(float(a['value_cad']) for a in awards if a.get('value_cad')):,.0f}")
    print("=== STAT: years of disclosed award history (stated 14) ===")
    print(f"    REAL: {years} (earliest awarded_on "
          f"{awarded_dates[0][:10] if awarded_dates else 'none'})")

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    docs_wk = supabase_client.fetch_all_rows_where(
        "documents", "id", {"created_at": f"gte.{week_ago}"})
    print("=== STAT: public documents read each week (stated 1,200+) ===")
    print(f"    REAL: {len(docs_wk)} documents captured in the last 7 days")

    # Closing soon: mirrors marketing_closing_soon() including public_safety
    # when the column exists; falls back to reporting both with and without.
    try:
        ps_rows = supabase_client.fetch_all_rows_where(
            "signals", "id,public_safety", {"suppressed": "is.false"})
        ps_by_id = {r["id"]: bool(r.get("public_safety")) for r in ps_rows}
        ps_col = True
    except Exception:
        ps_by_id = {}
        ps_col = False

    open_by_doc = {}
    for s in signals:
        d = _one(s.get("documents")) or {}
        if d.get("doc_type") not in ("tender_notice", "grant_program", "grant_award"):
            continue
        try:
            p = date.fromisoformat((d.get("published_on") or "")[:10])
        except ValueError:
            continue
        if not (today < p <= today + timedelta(days=90)):
            continue
        doc_id = d.get("id")
        prev = open_by_doc.get(doc_id)
        if prev is None or (s.get("evidence_grade") or 0) > (prev[0].get("evidence_grade") or 0):
            open_by_doc[doc_id] = (s, d, p)

    rows = sorted(open_by_doc.values(), key=lambda t: t[2])
    ps_open = [t for t in rows if ps_by_id.get(t[0]["id"], False)]
    print("=== CLOSING SOON (homepage panel; public-safety, next 90 days) ===")
    print(f"    public_safety column present: {ps_col}")
    print(f"    total open in-market docs: {len(rows)}; public-safety slice: {len(ps_open)}")
    show = ps_open if ps_col and ps_open else rows
    for s, d, p in show[:8]:
        org = org_by_id.get(s.get("organization_id")) or {}
        days = (p - today).days
        kind = "Tender" if d["doc_type"] == "tender_notice" else "Grant"
        flag = "" if ps_by_id.get(s["id"], False) else " [NOT public-safety]"
        print(f"    {kind:<7} {days:>3}d  {(org.get('canonical_name') or '-')[:30]:<30} "
              f"{(s.get('title') or '')[:55]}{flag}")

    # Recently added awards (capability 01): awarded_on ordering + created_at probe.
    print("=== RECENTLY ADDED CONTRACTS (capability 01; stated Axon/Ford/Motorola) ===")
    try:
        supabase_client.fetch_rows_where("contract_awards", "id,created_at", {}, limit=1)
        print("    contract_awards.created_at EXISTS (can order by record-added time)")
    except Exception:
        print("    contract_awards.created_at ABSENT (order by awarded_on)")
    with_end = [a for a in awards if end_date(a)]
    with_end.sort(key=lambda a: a.get("awarded_on") or "", reverse=True)
    for a in with_end[:3]:
        ed = end_date(a)
        print(f"    {(a.get('description') or 'Contract award')[:60]:<60} "
              f"{(a.get('vendor_name') or 'no vendor')[:26]:<26} ends {ed.year if ed else '-'}")

    print("=== COVERAGE REGISTER (on-the-record orgs; site tabs) ===")
    print(f"    Police services ({len(services)}): {', '.join(services)}")
    print(f"    Boards+councils ({len(boards) + len(councils)}): "
          f"{', '.join(boards + councils)}")
    print(f"    Ministries/departments ({len(ministries)}): {', '.join(ministries)}")

    names = sorted((s.get("name") or "?") for s in sources)
    print(f"=== REGISTERED SOURCES ({len(names)}) ===")
    for n in names:
        print(f"    {n}")

    doc_types = Counter((_one(s.get("documents")) or {}).get("doc_type") for s in signals)
    print(f"=== CORPUS SHAPE === live signals {len(signals)}; by doc_type {dict(doc_types)}")


if __name__ == "__main__":
    main()
