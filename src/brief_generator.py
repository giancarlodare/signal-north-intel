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

Relevance lens (operator, 2026-07-20, DRAFT-ONLY): the draft defaults to
defence-relevant items plus non-defence items at materiality >= 4. Everything
else above the bar is still written to the draft but with included=false, and
the held count is stored beside the below-bar count, so the operator can pull
any held item back in the editor with one toggle. The corpus stays keep-all:
the lens never suppresses, deletes, or drops a signal; it only sets the draft's
starting selection.

    python -m src.brief_generator --dry-run   # select/cluster/report, write nothing
    python -m src.brief_generator --apply      # write the week's draft brief
"""
import argparse
import logging
import math
from . import public_safety
from .filters import load_keywords
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

from . import brief_copy, supabase_client

log = logging.getLogger(__name__)

RECENT_BACK_DAYS = 7   # FLOOR only: the recent window anchors to the last
                       # PUBLISHED issue (operator 2026-08-02), so a late or
                       # missed issue extends the window backward and no day
                       # of record is ever silently skipped. 7 days is the
                       # minimum (and the fallback before any issue exists).
# +35 aligns the imminent window with the approved scorer curve's 21-35-day
# peak (operator ruling 2026-08-02; the +30 edge was excluding days 31-35).
DEFAULT_LEAD_DAYS = 35
# Grants get the horizon a service actually needs to assemble an
# application (operator ruling 2026-08-02: 45 was tight, and today's one
# in-corpus item at +46..60 measures the young grants corpus, not the world).
LEAD_DAYS_BY_DOCTYPE = {"grant_program": 90, "grant_award": 90}
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
# Relevance lens: a non-defence cluster needs this relevance score (on its
# strongest member) to default into the draft. Defence-relevant always defaults
# in. Floor ruled 2026-08-06 from the 200-signal calibration batch.
LENS_MIN_RELEVANCE = 3

_KEYWORDS = None


def _kw():
    """Cached public-safety keyword set (config/keywords.txt)."""
    global _KEYWORDS
    if _KEYWORDS is None:
        _KEYWORDS = load_keywords()
    return _KEYWORDS


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


def recent_anchor_days(today: date) -> int:
    """How far back the recent window reaches: to the last PUBLISHED issue's
    week_start, floored at RECENT_BACK_DAYS. Continuous coverage regardless
    of cadence: compose a day late and the window stretches a day; miss a
    week and it stretches seven -- nothing skips, and the previously-featured
    dedupe absorbs any overlap. No cap by design (a cap would re-introduce
    silent loss); a stretched window is announced loudly instead."""
    rows = supabase_client.fetch_rows_where(
        "briefs", "week_start",
        {"status": "eq.published", "order": "week_start.desc"}, limit=1)
    if not rows:
        return RECENT_BACK_DAYS
    last_ws = _parse_date(rows[0].get("week_start"))
    if last_ws is None:
        return RECENT_BACK_DAYS
    back = max(RECENT_BACK_DAYS, (today - last_ws).days)
    if back > RECENT_BACK_DAYS:
        log.info("recent window anchored to last published issue "
                 "(week_start=%s): reaching back %d days", last_ws, back)
    return back


def timing_path(published_on, today: date, doc_type,
                recent_back: int = RECENT_BACK_DAYS) -> str | None:
    """'recent' (Path A) | 'imminent' (Path B) | None (out of the window)."""
    p = _parse_date(published_on)
    if p is None:
        return None
    if today - timedelta(days=recent_back) <= p <= today:
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


def select(signals, today: date, recent_back: int = RECENT_BACK_DAYS):
    """Partition the live corpus into included (in-window AND above the bar),
    the excluded-below-threshold tally, and the out-of-window drop. Returns
    (included_with_path, excluded_count, exclusion_breakdown)."""
    included = []              # list of (signal, path)
    excluded = 0
    breakdown = Counter()
    for s in signals:
        doc = _one(s.get("documents")) or {}
        path = timing_path(doc.get("published_on"), today, doc.get("doc_type"),
                           recent_back)
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


def cluster(included, proc_by_signal, today: date | None = None):
    """Group included (signal, path) pairs into clusters:
      procurement (if the signal links an active non-rejected procurement),
      else organization, else standalone signal.
    EXCEPT deadline-bearing action items, which never org-cluster: the close
    date IS the story, and collapsing a high-volume buyer's tenders (Peel posts
    15+ a week) into one item would show one headline and one date, hiding every
    other action window, which violates the timing-first principle. Org
    clustering is for UPSTREAM signal where the story is demand forming (board
    minutes, budget lines, news: intent/commitment rungs) and several same-org
    signals usually ARE one story. An action item that links a procurement still
    groups there.
    The grant nuance (operator, 2026-07-20): tenders are standalone PER SIGNAL
    because each tender is a separate bid, but grant_program signals from the
    SAME source document cluster as ONE item -- same document means same
    program, same deadline, same application; the extractor splits a program's
    eligibility streams into per-stream signals, and rendering those as
    separate brief items showed one program twice. The streams are enumerated
    inside the single item's note instead (stream_titles).
    Returns a list of cluster dicts, ranked (imminent first, then salience)."""
    groups = defaultdict(list)   # (kind, ref) -> [(signal, path)]
    for s, path in included:
        pid = proc_by_signal.get(s["id"])
        doc = _one(s.get("documents")) or {}
        doc_type = doc.get("doc_type")
        if pid:
            key = ("procurement", pid)
        elif doc_type == "grant_program":
            # One document = one program = one action. Falls back to the signal
            # id if document_id is somehow absent (degrades to standalone,
            # never to a wrong merge).
            key = ("document", s.get("document_id") or s["id"])
        elif s.get("organization_id") and doc_type != "tender_notice":
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
            # Lens inputs. max_materiality spans MEMBERS (the lead is picked
            # grade-first, so a non-lead member can carry the cluster's highest
            # materiality); defence_relevant is the document tag on any member.
            "max_materiality": max((s.get("materiality") or 0) for s in sigs),
            # max_relevance: strongest relevance score across cluster members
            # (floor-ruled 2026-08-06: threshold=3). None-safe: unscored
            # signals contribute 0 so the cluster is not promoted on their
            # behalf; backfill ensures coverage before the lens matters.
            "max_relevance": max((s.get("relevance") or 0) for s in sigs),
            "defence_relevant": any(
                bool((_one(s.get("documents")) or {}).get("defence_relevant"))
                for s in sigs),
            # Public-safety relevance (the vertical-depth truth-condition): a
            # cluster defaults into the MEMBER-FACING draft only when it is
            # public-safety-relevant, so a big general-municipal item from a
            # regional buyer no longer enters on materiality alone.
            "public_safety": public_safety.cluster_is_public_safety(
                [{"title": s.get("title"),
                  "defence_relevant": bool((_one(s.get("documents")) or {}).get("defence_relevant")),
                  "org_type": (_one(s.get("organizations")) or {}).get("org_type")}
                 for s in sigs], _kw()),
            "amount": float(lead.get("amount_max_cad") or 0),
            "org": (_one(lead.get("organizations")) or {}).get("canonical_name"),
            "org_type": (_one(lead.get("organizations")) or {}).get("org_type"),
            "doc_type": (_one(lead.get("documents")) or {}).get("doc_type"),
            # For a document cluster (grant program), the per-stream signal
            # titles: enumerated in the item note, since the streams share one
            # deadline and one application and are not separate items.
            "stream_titles": [s.get("title") for s in sigs if s.get("title")]
                             if kind == "document" and len(sigs) > 1 else None,
        })

    # Rank: weighted score (design doc: lens-redesign-design.md, approved
    # 2026-08-06). Timing paths are now an input to actionable_window, not
    # the outer sort partition. Determinism: ties break on (grade, soonest,
    # signal_id) so ordering is stable run-to-run.
    _ref = today or date.today()

    _BUYER_SCORE = {
        "police_board": 1.0, "federal_department": 1.0,
        "federal_agency": 1.0, "border_agency": 1.0,
        "municipality": 0.3,
    }

    def _weighted_score(c) -> float:
        # category_relevance: proxy via max_relevance/5 until per-category
        # coefficient table lands (design doc: uncategorized scores DEFAULT 0.5
        # once the table exists; for now the LLM score IS the per-item estimate).
        cat = (c.get("max_relevance") or 0) / 5.0
        # buyer_type: typed org_type -> scored buyer tier.
        bt = _BUYER_SCORE.get(c.get("org_type") or "", 0.0)
        # arc_connection: proxy via cluster member count (multiple signals in
        # the same cluster = precursor arc evidence). Default 0.5 for
        # single-member org clusters where arc status is ambiguous.
        m = c.get("members") or 1
        arc = 0.0 if m == 1 else (0.6 if m == 2 else 1.0)
        # actionable_window: curve peaking at 21-35 days out.
        # Recent (past-event) clusters score 0.5 -- actionable but no deadline.
        if c["timing_path"] == "recent":
            win = 0.5
        else:
            soonest = c.get("soonest_date")
            if soonest is None:
                win = 0.3
            else:
                days = (soonest - _ref).days
                if days <= 3:
                    win = 0.0
                elif 21 <= days <= 35:
                    win = 1.0
                elif days < 21:
                    win = (days - 3) / 18.0
                else:
                    # Exponential decay: 1.0 at 35 days, ~0.5 at 60, ~0.2 beyond
                    k = math.log(2) / 25
                    win = max(0.1, math.exp(-k * (days - 35)))
        mat = (c.get("max_materiality") or 0) / 5.0
        grade = (c.get("grade") or 0) / 5.0
        return (0.25 * cat + 0.15 * bt + 0.30 * arc
                + 0.15 * win + 0.10 * mat + 0.05 * grade)

    def rank_key(c):
        return (
            -_weighted_score(c),
            -c["grade"],
            c["soonest_date"] or date.max,
            c["lead_signal_id"],
        )

    clusters.sort(key=rank_key)
    for i, c in enumerate(clusters, 1):
        c["rank"] = i
    return clusters


def apply_lens(clusters) -> int:
    """The relevance lens over ranked clusters (draft-only; corpus keep-all).
    A cluster defaults into the draft when any member is defence_relevant or
    its highest relevance score >= LENS_MIN_RELEVANCE (floor=3, ruled
    2026-08-06 from calibration batch). Held clusters keep their rank and are
    written with included=false so the editor can pull them back with one
    toggle -- the lens sets the STARTING selection, nothing more.
    Pure: sets c["included"] on every cluster and returns the held count."""
    held = 0
    for c in clusters:
        keep = bool(c.get("defence_relevant")) \
            or (c.get("max_relevance") or 0) >= LENS_MIN_RELEVANCE
        c["included"] = keep
        if not keep:
            held += 1
    return held


def mark_previously_featured(clusters, prior_signal_ids, prior_cluster_keys) -> int:
    """Mark clusters whose story already appeared in a PRIOR PUBLISHED brief:
    same lead signal, or the same (cluster_kind, cluster_ref) carried across
    weeks (an org story that runs two weeks keeps its ref even if the lead
    signal changes). Display-only -- it never changes selection or rank; the
    editor shows a 'carried' tag so new vs carried is visible at a glance.
    Pure: sets c["previously_featured"]; returns how many were marked."""
    n = 0
    for c in clusters:
        carried = c["lead_signal_id"] in prior_signal_ids \
            or (c["cluster_kind"], str(c["cluster_ref"])) in prior_cluster_keys
        c["previously_featured"] = carried
        if carried:
            n += 1
    return n


def _prior_featured_keys(week_start) -> tuple:
    """(lead_signal_ids, (cluster_kind, cluster_ref) keys) of items INCLUDED in
    published briefs from earlier weeks. Draft-only history is not 'featured':
    only what a reader could actually have seen counts."""
    rows = supabase_client.fetch_all_rows_where(
        "brief_items",
        "lead_signal_id,cluster_kind,cluster_ref,briefs!inner(status,week_start)",
        {"included": "is.true",
         "briefs.status": "eq.published",
         "briefs.week_start": f"lt.{week_start}"})
    sig_ids = {r["lead_signal_id"] for r in rows if r.get("lead_signal_id")}
    keys = {(r["cluster_kind"], str(r["cluster_ref"])) for r in rows}
    return sig_ids, keys


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


def run(dry_run: bool = True, today: date | None = None, force: bool = False,
        preview_json: str | None = None) -> dict:
    today = today or date.today()
    week_start = monday_of(today)

    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,signal_type,confidence,materiality,evidence_grade,amount_max_cad,"
        "expected_timing,organization_id,title,relevance,"
        "organizations(canonical_name,org_type),"
        "document_id,"
        "documents!inner(doc_type,published_on,date_precision,url,defence_relevant)",
        {"suppressed": "is.false"})

    recent_back = recent_anchor_days(today)
    included, excluded, breakdown = select(signals, today, recent_back)
    proc_by_signal = _procurement_by_signal()
    clusters = cluster(included, proc_by_signal, today)
    lens_held = apply_lens(clusters)
    prior_sigs, prior_keys = _prior_featured_keys(week_start)
    carried = mark_previously_featured(clusters, prior_sigs, prior_keys)

    # Out-of-window diagnostic: where the corpus falls relative to the window, so
    # a thin brief is explainable (backfilled awards have old event dates; grants
    # are often undated) and the window can be judged against reality.
    diag = Counter()
    in_window_doctypes = Counter()
    lo = today - timedelta(days=recent_back)
    for s in signals:
        doc = _one(s.get("documents")) or {}
        p = _parse_date(doc.get("published_on"))
        path = timing_path(doc.get("published_on"), today, doc.get("doc_type"),
                           recent_back)
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
    log.info("  relevance lens: %d of %d clusters default in; %d held "
             "(non-defence, relevance < %d), written included=false for the "
             "editor to pull back", len(clusters) - lens_held, len(clusters),
             lens_held, LENS_MIN_RELEVANCE)
    log.info("  previously featured: %d of %d clusters appeared in a prior "
             "published brief (marked 'carried' in the editor)",
             carried, len(clusters))
    log.info("  %-8s %-10s %-11s %-6s %5s  %s", "rank", "kind", "timing", "grade", "mat", "lead")
    for c in clusters[:25]:
        log.info("  #%-7d %-10s %-11s g%-5d %5d  %s [%s, soonest %s, %d sig]",
                 c["rank"], c["cluster_kind"], c["timing_path"], c["grade"],
                 c["materiality"], (c["lead_title"] or "")[:60],
                 c["org"] or "no-org", c["soonest_date"], c["members"])

    if preview_json is not None:
        _build_preview_json(preview_json, week_start, clusters, signals, excluded)

    written = {"brief": 0, "items": 0}
    if not dry_run:
        written = _apply(week_start, clusters, excluded, breakdown, force)

    result = {"week_start": str(week_start), "scanned": len(signals),
              "included": len(included), "excluded_below_threshold": excluded,
              "exclusion_breakdown": breakdown, "clusters": len(clusters),
              "held_by_relevance_lens": lens_held,
              "previously_featured": carried,
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


def _build_preview_json(preview_json: str, week_start, clusters, signals, excluded: int) -> None:
    """Write brief preview data to a file without any DB writes.
    Consumed by web/scripts/send-brief-preview.mjs for the shadow-brief email."""
    import json as _json
    sig_by_id = {s["id"]: s for s in signals}
    intro = brief_copy.draft_the_read(
        [c for c in clusters if c.get("included", True)])
    items = []
    for c in clusters:
        if not c.get("included", True):
            continue
        sig = sig_by_id.get(c["lead_signal_id"]) or {}
        doc = _one(sig.get("documents")) or {}
        org = (_one(sig.get("organizations")) or {}).get("canonical_name")
        amount = float(c.get("amount") or 0)
        note = brief_copy.draft_item_note(
            doc_type=c.get("doc_type"), timing_path=c["timing_path"],
            buyer=org or c.get("org"), title=c.get("lead_title"),
            amount_cad=amount or None, streams=c.get("stream_titles"))
        items.append({
            "rank": c["rank"],
            "headline": c.get("lead_title") or "(untitled)",
            "timing_path": c["timing_path"],
            "vendorSoWhat": note or None,
            "buyer": org or c.get("org"),
            "amountCad": amount if amount > 0 else None,
            "doc_type": doc.get("doc_type") or c.get("doc_type"),
            "url": doc.get("url"),
            "published_on": doc.get("published_on"),
            "date_precision": doc.get("date_precision"),
        })
    out = {
        "week_start": str(week_start),
        "theRead": intro,
        "reviewedHeldCount": excluded,
        "items": items,
    }
    with open(preview_json, "w") as fh:
        _json.dump(out, fh, indent=2, default=str)
    log.info("Preview JSON -> %s (%d items)", preview_json, len(items))


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
    # The Read describes the draft's DEFAULT selection; lens-held items only
    # enter the story if the operator pulls them back in.
    intro = brief_copy.draft_the_read(
        [c for c in clusters if c.get("included", True)])
    # The lens-held count rides exclusion_breakdown (shown as a chip in the
    # editor header, same pattern as the below-bar counts); the held items
    # themselves are in the draft as included=false rows the editor can toggle.
    lens_held = sum(1 for c in clusters if not c.get("included", True))
    if lens_held:
        breakdown = {**breakdown, "relevance_lens": lens_held}
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
            buyer=c.get("org"), title=c.get("lead_title"), amount_cad=c.get("amount"),
            streams=c.get("stream_titles"))
        supabase_client.insert_row("brief_items", {
            "brief_id": bid,
            "cluster_kind": c["cluster_kind"],
            "cluster_ref": str(c["cluster_ref"]),
            "lead_signal_id": c["lead_signal_id"],
            "timing_path": c["timing_path"],
            "soonest_date": str(c["soonest_date"]) if c["soonest_date"] else None,
            "included": bool(c.get("included", True)),
            "rank": c["rank"],
            "editor_note": note,
            "previously_featured": bool(c.get("previously_featured", False)),
        })
        n += 1
    log.info("  wrote draft brief %s with %d items (%d held by the relevance "
             "lens as included=false)", bid, n, lens_held)
    return {"brief": 1, "items": n}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weekly Signal brief generator")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="select/cluster/report, write nothing")
    group.add_argument("--apply", action="store_true",
                       help="write the week's draft brief")
    group.add_argument("--preview-json", metavar="FILE",
                       help="write brief preview data to FILE without any DB writes; "
                            "consumed by web/scripts/send-brief-preview.mjs")
    parser.add_argument("--force", action="store_true",
                        help="regenerate a DRAFT brief (delete + rebuild); "
                             "refuses if the week's brief is published")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run(dry_run=not args.apply, force=args.force,
                 preview_json=args.preview_json)
    # Exit non-zero when a force run refused a published brief, so a manual
    # regenerate run goes RED in Actions instead of quietly doing nothing.
    sys.exit(2 if result.get("refused_published") else 0)
