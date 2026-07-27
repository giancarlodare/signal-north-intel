"""Stage-3 watch matcher: the deterministic (no-LLM) daily writer behind the
member "we flagged this for you" log (decisions A-D, operator 2026-07-27).

Universe (decision A, gate-cleared only): signals a MEMBER session can read,
i.e. lead signals of included items of PUBLISHED briefs that are
public-safety-relevant. A watch can never fire on a row the RLS would refuse
the member, so the trust log's source is clean by construction.

Match semantics (D3): keyword watches match WHOLE-WORD, case-insensitive
against the signal title (the pilot's "contracting" false-positive lesson;
a bad match here becomes a wrong told-you-first entry). Buyer watches match
the signal's resolved organization.

Forward vs backfill (B/D4): the brief's week_start is the deterministic
proxy for when a signal entered the member-readable universe. A signal whose
brief week is on/after the watch's creation date is a forward 'match' (the
trust log); an earlier one within 30 days is labelled 'backfill' ("recent
matches in your area"); older ones are ignored.

Idempotent: existing (watch, signal) events are skipped, so reruns are
no-ops. Guarded like apply_public_safety: if member_watches does not exist
yet (stage-3 DDL not pasted), it logs and exits 0 so the daily pipeline
stays green pre-paste. Loud on real errors.

    python -m src.watch_matcher --dry-run   # compute + report, write nothing
    python -m src.watch_matcher --apply      # write match/backfill events
"""
import argparse
import logging
import re
import sys
from datetime import date, timedelta

from . import supabase_client

log = logging.getLogger(__name__)

BACKFILL_DAYS = 30


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def tables_present() -> bool:
    try:
        supabase_client.fetch_rows_where("member_watches", "id", {}, limit=1)
        return True
    except Exception as e:  # noqa: BLE001 - any read error means "not pasted"
        log.info("member_watches not present yet (%s); skipping. Paste "
                 "migrations/2026-07-27_wave3_stage3_watch_saved.sql to enable "
                 "the watch matcher.", type(e).__name__)
        return False


def keyword_matches(keyword: str, title: str) -> bool:
    """Whole-word, case-insensitive match of `keyword` (which may be a
    phrase) inside `title`. 'contract' does NOT match 'contracting'."""
    kw = (keyword or "").strip()
    if not kw or not title:
        return False
    pattern = r"\b" + re.escape(kw) + r"\b"
    return re.search(pattern, title, re.IGNORECASE) is not None


def classify(week_start: str, watch_created: str,
             today: date) -> str | None:
    """'match' | 'backfill' | None for a universe signal against a watch.
    week_start is the brief's week (the entered-universe proxy);
    watch_created is the watch's created_at ISO timestamp."""
    try:
        week = date.fromisoformat((week_start or "")[:10])
        created = date.fromisoformat((watch_created or "")[:10])
    except ValueError:
        return None
    if week >= created:
        return "match"
    if week >= created - timedelta(days=BACKFILL_DAYS):
        return "backfill"
    return None


def compute_events(watches: list, universe: list, existing: set,
                   today: date) -> list:
    """Pure: [(watch, signal, event_type, detail)] for every new event.
    `universe` rows carry signal_id, title, organization_id, org_name,
    week_start. `existing` is a set of (watch_id, signal_id)."""
    out = []
    for w in watches:
        for u in universe:
            if (w["id"], u["signal_id"]) in existing:
                continue
            if w["kind"] == "keyword":
                if not keyword_matches(w.get("keyword") or "", u.get("title") or ""):
                    continue
                detail = f"keyword: {w.get('keyword')}"
            else:
                if not u.get("organization_id") or \
                        u.get("organization_id") != w.get("organization_id"):
                    continue
                detail = f"buyer: {u.get('org_name') or 'followed buyer'}"
            kind = classify(u.get("week_start") or "", w.get("created_at") or "",
                            today)
            if kind is None:
                continue
            out.append((w, u, kind, detail))
    return out


def load_universe() -> list:
    """Gate-cleared signals: included items of published briefs whose lead
    signal is public-safety. One row per (brief item) lead signal."""
    rows = supabase_client.fetch_all_rows_where(
        "brief_items",
        "lead_signal_id,included,"
        "briefs!inner(status,week_start),"
        "signals:lead_signal_id(id,title,organization_id,public_safety,"
        "organizations(canonical_name))",
        {"included": "is.true", "briefs.status": "eq.published"})
    universe = []
    seen = set()
    for r in rows:
        s = _one(r.get("signals")) or {}
        b = _one(r.get("briefs")) or {}
        sid = s.get("id")
        if not sid or sid in seen or not s.get("public_safety"):
            continue
        seen.add(sid)
        org = _one(s.get("organizations")) or {}
        universe.append({
            "signal_id": sid,
            "title": s.get("title"),
            "organization_id": s.get("organization_id"),
            "org_name": org.get("canonical_name"),
            "week_start": b.get("week_start"),
        })
    return universe


def run(dry_run: bool = True, today: date | None = None) -> dict:
    today = today or date.today()
    if not tables_present():
        return {"skipped": True, "reason": "tables_absent"}

    watches = supabase_client.fetch_all_rows_where(
        "member_watches", "id,member_id,kind,keyword,organization_id,created_at",
        {})
    if not watches:
        log.info("watch_matcher: no watches yet; nothing to do.")
        return {"watches": 0, "universe": 0, "events": 0, "written": 0}

    universe = load_universe()
    existing_rows = supabase_client.fetch_all_rows_where(
        "watch_events", "watch_id,signal_id", {"signal_id": "not.is.null"})
    existing = {(r["watch_id"], r["signal_id"]) for r in existing_rows}

    events = compute_events(watches, universe, existing, today)
    n_match = sum(1 for e in events if e[2] == "match")
    n_backfill = sum(1 for e in events if e[2] == "backfill")
    log.info("watch_matcher %s: %d watches x %d gate-cleared signals -> "
             "%d new events (%d match, %d backfill)",
             "dry-run" if dry_run else "APPLY", len(watches), len(universe),
             len(events), n_match, n_backfill)

    written = 0
    if not dry_run:
        for w, u, kind, detail in events:
            supabase_client.insert_row("watch_events", {
                "member_id": w["member_id"],
                "watch_id": w["id"],
                "signal_id": u["signal_id"],
                "event_type": kind,
                "detail": detail,
            })
            written += 1
        log.info("  wrote %d watch events", written)

    return {"watches": len(watches), "universe": len(universe),
            "events": len(events), "match": n_match,
            "backfill": n_backfill, "written": written}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Member watch matcher")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    run(dry_run=not args.apply)
    sys.exit(0)
