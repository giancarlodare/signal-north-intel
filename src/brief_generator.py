"""Weekly Signal brief generator (editorial model Phase 3).

Selects the week's timing-relevant, strong-grade, high-materiality signals,
clusters them (procurement -> organization -> standalone), ranks them, and (in
--apply) writes a `draft` brief the operator edits at /brief. Propose-only: it
writes ONLY briefs/brief_items, never a prediction, procurement, or suppression.

Selection (docs/editorial-model-redesign.md 7.1), keyed on the event date
documents.published_on (which is a past date for awards/news/board minutes and a
future DEADLINE for grants):
  * Path A, recent event: published_on in [today-7, today].
  * Path B, imminent event: published_on in (today, today+lead], lead PER
    doc_type -- default 30 days, 45 for grants (prep runway). Grant deadlines,
    being future published_on, land here.
  * No created_at path (backfill-safe); expected_timing is context-only.
The materiality/grade bar is PATH-SPECIFIC: Path A (recent, retrospective) uses
the full bar (materiality>=3 AND grade>=3, so only past events strong enough to
matter appear); Path B (imminent, prospective) uses a relaxed floor
(materiality>=2 AND grade>=2), because a closing-soon opportunity is actionable
by timing and grade is secondary. suppressed=false always.

    python -m src.brief_generator --dry-run   # select/cluster/report, write nothing
    python -m src.brief_generator --apply      # write the week's draft brief
"""
import argparse
import logging
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

from . import brief_copy, supabase_client

log = logging.getLogger(__name__)

RECENT_BACK_DAYS = 7
DEFAULT_LEAD_DAYS = 30
LEAD_DAYS_BY_DOCTYPE = {"grant_program": 45, "grant_award": 45}
MAX_LEAD_DAYS = max([DEFAULT_LEAD_DAYS, *LEAD_DAYS_BY_DOCTYPE.values()])
# Path-specific bar. Path A (recent) is RETROSPECTIVE: a past event earns a place
# only if it was strong enough to matter, so materiality gates it (full bar).
# Path B (imminent) is PROSPECTIVE: a closing-soon opportunity is actionable by
# virtue of timing, so timing gates it and grade is secondary (relaxed floor,
# kept above pure noise).
RECENT_MIN_MATERIALITY = 3
RECENT_MIN_GRADE = 3
IMMINENT_MIN_MATERIALITY = 2
IMMINENT_MIN_GRADE = 2


def bar_for(path) -> tuple:
    """(min_materiality, min_grade) for a timing path."""
    if path == "imminent":
        return IMMINENT_MIN_MATERIALITY, IMMINENT_MIN_GRADE
    return RECENT_MIN_MATERIALITY, RECENT_MIN_GRADE


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def lead_days_for(doc_type) -> int:
    return LEAD_DAYS_BY_DOCTYPE.get(doc_type, DEFAULT_LEAD_DAYS)


def _parse_date(s):
    try:
        return date.fromisoformat((s or "")[:10])
    except (TypeError, ValueError):
        return None


def timing_path(published_on, today: date, doc_type) -> str | None:
    """'recent' (Path A) | 'imminent' (Path B) | None (out of the window)."""
    p = _parse_date(published_on)
    if p is None:
        return None
    if today - timedelta(days=RECENT_BACK_DAYS) <= p <= today:
        return "recent"
    if today < p <= today + timedelta(days=lead_days_for(doc_type)):
        return "imminent"
    return None


def _lead_key(sig):
    """Salience of a single signal within a cluster: grade, then materiality,
    then amount. Higher is stronger."""
    return (sig.get("evidence_grade") or 0,
            sig.get("materiality") or 0,
            float(sig.get("amount_max_cad") or 0))


def select(signals, today: date):
    """Partition the live corpus into included (in-window AND above the bar),
    the excluded-below-threshold tally, and the out-of-window drop. Returns
    (included_with_path, excluded_count, exclusion_breakdown)."""
    included = []              # list of (signal, path)
    excluded = 0
    breakdown = Counter()
    for s in signals:
        doc = _one(s.get("documents")) or {}
        path = timing_path(doc.get("published_on"), today, doc.get("doc_type"))
        if path is None:
            continue           # out of the timing window entirely
        min_mat, min_grade = bar_for(path)
        mat = s.get("materiality") or 0
        grade = s.get("evidence_grade") or 0
        if mat >= min_mat and grade >= min_grade:
            included.append((s, path))
        else:
            excluded += 1
            if mat < min_mat:
                breakdown["below_materiality"] += 1
            if grade < min_grade:
                breakdown["below_grade"] += 1
    return included, excluded, dict(breakdown)


def cluster(included, proc_by_signal):
    """Group included (signal, path) pairs into clusters:
      procurement (if the signal links an active non-rejected procurement),
      else organization, else standalone signal.
    Returns a list of cluster dicts, ranked (imminent first, then salience)."""
    groups = defaultdict(list)   # (kind, ref) -> [(signal, path)]
    for s, path in included:
        pid = proc_by_signal.get(s["id"])
        if pid:
            key = ("procurement", pid)
        elif s.get("organization_id"):
            key = ("organization", s["organization_id"])
        else:
            key = ("signal", s["id"])
        groups[key].append((s, path))

    clusters = []
    for (kind, ref), members in groups.items():
        sigs = [m[0] for m in members]
        paths = [m[1] for m in members]
        lead = max(sigs, key=_lead_key)
        is_imminent = "imminent" in paths
        # soonest date drives ranking + the "why included": for imminent, the
        # nearest future deadline; for recent, the most recent event.
        imminent_dates = [_parse_date(_one(m[0].get("documents")).get("published_on"))
                          for m in members if m[1] == "imminent"]
        imminent_dates = [d for d in imminent_dates if d]
        if is_imminent and imminent_dates:
            soonest = min(imminent_dates)
        else:
            recent_dates = [_parse_date(_one(s.get("documents")).get("published_on"))
                            for s in sigs]
            recent_dates = [d for d in recent_dates if d]
            soonest = max(recent_dates) if recent_dates else None
        clusters.append({
            "cluster_kind": kind, "cluster_ref": ref,
            "lead_signal_id": lead["id"], "lead_title": lead.get("title"),
            "timing_path": "imminent" if is_imminent else "recent",
            "soonest_date": soonest, "members": len(sigs),
            "grade": lead.get("evidence_grade") or 0,
            "materiality": lead.get("materiality") or 0,
            "amount": float(lead.get("amount_max_cad") or 0),
            "org": (_one(lead.get("organizations")) or {}).get("canonical_name"),
            "doc_type": (_one(lead.get("documents")) or {}).get("doc_type"),
        })

    # Rank: imminent clusters first, by soonest date; then by salience.
    def rank_key(c):
        imminent_first = 0 if c["timing_path"] == "imminent" else 1
        soon = c["soonest_date"] or date.max
        return (imminent_first, soon, -c["grade"], -c["materiality"], -c["amount"])

    clusters.sort(key=rank_key)
    for i, c in enumerate(clusters, 1):
        c["rank"] = i
    return clusters


def _procurement_by_signal():
    """signal_id -> procurement_id for active links whose procurement is live
    (proposed or confirmed, not rejected/merged)."""
    links = supabase_client.fetch_all_rows_where(
        "procurement_signals", "procurement_id,signal_id,active,procurements(status)",
        {"active": "is.true"})
    out = {}
    for l in links:
        proc = _one(l.get("procurements")) or {}
        if proc.get("status") in ("proposed", "confirmed"):
            out[l["signal_id"]] = l["procurement_id"]
    return out


def _peel_recent_award_count() -> int | None:
    """Sum of municipal (Region of Peel) award notices over the last four
    quarters, for the one honest scale fact The Read may cite. Returns None if
    the exhibit view is unavailable, so a missing number is never faked as zero."""
    try:
        rows = supabase_client.fetch_rows_where(
            "award_volume_by_quarter", "quarter_start,awards",
            {"jurisdiction": "eq.municipal", "order": "quarter_start.desc"},
            limit=4)
    except Exception as e:  # the view may be absent in a given environment
        log.warning("  peel award count unavailable: %s", e)
        return None
    if not rows:
        return None
    return sum(int(r.get("awards") or 0) for r in rows)


def run(dry_run: bool = True, today: date | None = None, force: bool = False) -> dict:
    today = today or date.today()
    week_start = monday_of(today)

    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,signal_type,confidence,materiality,evidence_grade,amount_max_cad,"
        "expected_timing,organization_id,title,organizations(canonical_name),"
        "documents!inner(doc_type,published_on,date_precision,url)",
        {"suppressed": "is.false"})

    included, excluded, breakdown = select(signals, today)
    proc_by_signal = _procurement_by_signal()
    clusters = cluster(included, proc_by_signal)

    # Out-of-window diagnostic: where the corpus falls relative to the window, so
    # a thin brief is explainable (backfilled awards have old event dates; grants
    # are often undated) and the window can be judged against reality.
    diag = Counter()
    in_window_doctypes = Counter()
    lo = today - timedelta(days=RECENT_BACK_DAYS)
    for s in signals:
        doc = _one(s.get("documents")) or {}
        p = _parse_date(doc.get("published_on"))
        path = timing_path(doc.get("published_on"), today, doc.get("doc_type"))
        if path:
            diag[path] += 1
            in_window_doctypes[doc.get("doc_type") or "unknown"] += 1
        elif p is None:
            diag["out_undated"] += 1
        elif p < lo:
            diag["out_past"] += 1
        else:
            diag["out_future_beyond_lead"] += 1

    log.info("Brief %s for week_start=%s (today=%s)",
             "dry-run" if dry_run else "APPLY", week_start, today)
    log.info("  window: recent %s .. %s, imminent to +%d/+%d days (grants %d)",
             lo, today, DEFAULT_LEAD_DAYS, DEFAULT_LEAD_DAYS,
             LEAD_DAYS_BY_DOCTYPE.get("grant_program", DEFAULT_LEAD_DAYS))
    log.info("  disposition of %d live signals: %s", len(signals), dict(diag))
    log.info("  in-window by doc_type: %s", dict(in_window_doctypes))
    log.info("  scanned %d live signals; %d in-window+above-bar, "
             "%d in-window-below-bar (%s); %d clusters",
             len(signals), len(included), excluded, breakdown or "{}", len(clusters))
    kinds = Counter(c["cluster_kind"] for c in clusters)
    log.info("  clusters by kind: %s", dict(kinds))
    log.info("  %-8s %-10s %-11s %-6s %5s  %s", "rank", "kind", "timing", "grade", "mat", "lead")
    for c in clusters[:25]:
        log.info("  #%-7d %-10s %-11s g%-5d %5d  %s [%s, soonest %s, %d sig]",
                 c["rank"], c["cluster_kind"], c["timing_path"], c["grade"],
                 c["materiality"], (c["lead_title"] or "")[:60],
                 c["org"] or "no-org", c["soonest_date"], c["members"])

    written = {"brief": 0, "items": 0}
    if not dry_run:
        written = _apply(week_start, clusters, excluded, breakdown, force)

    result = {"week_start": str(week_start), "scanned": len(signals),
              "included": len(included), "excluded_below_threshold": excluded,
              "exclusion_breakdown": breakdown, "clusters": len(clusters),
              "wrote_brief": written.get("brief", 0), "wrote_items": written.get("items", 0)}
    if written.get("refused_published"):
        result["refused_published"] = True
    return result


def regen_decision(existing_status, force: bool) -> str:
    """What _apply does about an existing brief for the week. Pure, so the
    safety-critical invariant (force NEVER deletes a published brief) is
    unit-testable without a database:
      'create'  -- no brief exists, write a fresh draft
      'skip'    -- one exists and force is off: leave it (protect operator edits)
      'replace' -- a DRAFT exists and force is on: delete it and rebuild
      'refuse'  -- a PUBLISHED brief exists: frozen, force will not touch it
    """
    if existing_status is None:
        return "create"
    if not force:
        return "skip"
    return "replace" if existing_status == "draft" else "refuse"


def _apply(week_start, clusters, excluded, breakdown, force) -> dict:
    """Create the week's draft brief. Create-if-absent by default; with force,
    regenerate ONLY a draft (delete + rebuild). A published brief is frozen and
    is never deleted: force refuses it and asks the operator to unpublish first."""
    existing = supabase_client.fetch_rows_where(
        "briefs", "id,status", {"week_start": f"eq.{week_start}"}, limit=1)
    status = existing[0].get("status") if existing else None
    decision = regen_decision(status, force)

    if decision == "skip":
        log.info("  brief for %s already exists (status=%s); leaving it. "
                 "Pass --force to regenerate a draft.", week_start, status)
        return {"brief": 0, "items": 0}
    if decision == "refuse":
        log.error("  refusing to regenerate the %s brief for %s: --force only "
                  "replaces a DRAFT. Unpublish it at /brief first, then rerun.",
                  status, week_start)
        return {"brief": 0, "items": 0, "refused_published": True}
    if decision == "replace":
        bid = existing[0]["id"]
        log.warning("  --force: deleting existing DRAFT brief %s for %s and "
                    "regenerating.", bid, week_start)
        # status=eq.draft guard: if it was published between the read above and
        # this delete, the delete no-ops rather than destroying a published brief.
        supabase_client.delete_rows(
            "briefs", {"id": f"eq.{bid}", "status": "eq.draft"})

    # Draft copy the operator sharpens: The Read (one paragraph) as the brief
    # intro, and a per-item vendor read as each item's editor_note. Deterministic
    # from what we hold, never fabricated; the draft is the scaffold, the edits
    # are the value.
    peel_recent = _peel_recent_award_count()
    intro = brief_copy.draft_the_read(clusters, peel_recent)
    brief = supabase_client.insert_row("briefs", {
        "week_start": str(week_start),
        "status": "draft",
        "intro": intro,
        "excluded_below_threshold": excluded,
        "exclusion_breakdown": breakdown,
    })
    bid = brief["id"]
    n = 0
    for c in clusters:
        note = brief_copy.draft_item_note(
            doc_type=c.get("doc_type"), timing_path=c["timing_path"],
            buyer=c.get("org"), title=c.get("lead_title"), amount_cad=c.get("amount"))
        supabase_client.insert_row("brief_items", {
            "brief_id": bid,
            "cluster_kind": c["cluster_kind"],
            "cluster_ref": str(c["cluster_ref"]),
            "lead_signal_id": c["lead_signal_id"],
            "timing_path": c["timing_path"],
            "soonest_date": str(c["soonest_date"]) if c["soonest_date"] else None,
            "included": True,
            "rank": c["rank"],
            "editor_note": note,
        })
        n += 1
    log.info("  wrote draft brief %s with %d items", bid, n)
    return {"brief": 1, "items": n}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weekly Signal brief generator")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="select/cluster/report, write nothing")
    group.add_argument("--apply", action="store_true",
                       help="write the week's draft brief")
    parser.add_argument("--force", action="store_true",
                        help="regenerate a DRAFT brief (delete + rebuild); "
                             "refuses if the week's brief is published")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run(dry_run=not args.apply, force=args.force)
    # Exit non-zero when a force run refused a published brief, so a manual
    # regenerate run goes RED in Actions instead of quietly doing nothing.
    sys.exit(2 if result.get("refused_published") else 0)
