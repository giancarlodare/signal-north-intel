"""Relevance calibration batch: score 200 signals and produce DECISION table.

Produces a side-by-side comparison of:
  - Current lens (materiality >= 4 AND public_safety, OR defence_relevant)
  - Relevance-gated lens at floor 3 and floor 4
  - Timing window +30 days vs +35 days (imminent-count sensitivity)

Output: docs/relevance-calibration-{date}.md (report) + .json (raw data)

    python scripts/relevance_calibration.py --dry-run   # plan + score, no DB write
    python scripts/relevance_calibration.py --run        # score + write relevance
"""
import argparse
import json
import logging
import os
import random
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from src import supabase_client
import src.relevance_scorer as rs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SAMPLE_N = 200
# Stratified by materiality bucket so every tier is represented.
PER_MATERIALITY = 40  # 5 buckets x 40 = 200 (shortfalls from thin strata are honest)

# defence_relevant lives on documents, not signals (same lesson as the
# 2026-07-28 portal incident). Join it via documents(defence_relevant) and
# flatten it into the signal dict in _load_signals().
_SELECT = (
    "id,title,summary,materiality,relevance,"
    "public_safety,expected_timing,documents(defence_relevant)"
)

REPORT_MD = "relevance-calibration.md"
REPORT_JSON = "relevance-calibration.json"

# Lens floors to compare against current (materiality >= 4).
FLOORS = [3, 4]
# Lead-day windows to compare.
WINDOWS = [30, 35]


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def _stratified_sample(signals: list, per_bucket: int, seed: str) -> tuple[list, dict]:
    """Sample per_bucket from each materiality level 1-5.

    Returns (sample, shortfalls) where shortfalls maps materiality ->
    deficit if a stratum had fewer than per_bucket signals.
    """
    rng = random.Random(seed)
    by_mat: dict[int, list] = {m: [] for m in range(1, 6)}
    for s in signals:
        m = int(s.get("materiality") or 3)
        m = max(1, min(5, m))
        by_mat[m].append(s)

    sample = []
    shortfalls = {}
    for m in range(1, 6):
        bucket = by_mat[m]
        rng.shuffle(bucket)
        take = bucket[:per_bucket]
        sample.extend(take)
        if len(bucket) < per_bucket:
            shortfalls[m] = per_bucket - len(bucket)
        log.info("  materiality=%d: pool=%d sampled=%d", m, len(bucket), len(take))

    return sample, shortfalls


# ---------------------------------------------------------------------------
# Lens comparison helpers
# ---------------------------------------------------------------------------

def _passes_current_lens(sig: dict) -> bool:
    """Current lens: defence_relevant OR (public_safety AND materiality >= 4)."""
    if sig.get("defence_relevant"):
        return True
    return bool(sig.get("public_safety")) and (sig.get("materiality") or 0) >= 4


def _passes_relevance_lens(sig: dict, floor: int) -> bool:
    """Proposed lens: defence_relevant OR relevance >= floor."""
    if sig.get("defence_relevant"):
        return True
    return (sig.get("relevance") or 0) >= floor


def _days_ahead(sig: dict, today: date) -> Optional[int]:
    """Return days until expected_timing, or None if absent/past."""
    et = sig.get("expected_timing")
    if not et:
        return None
    try:
        d = date.fromisoformat(str(et)[:10])
        delta = (d - today).days
        return delta if delta >= 0 else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def _load_signals() -> list:
    """Fetch all signals with materiality scored (no relevance filter -- we want
    the full distribution including already-scored signals for the table)."""
    log.info("Fetching signals pool...")
    rows = supabase_client.fetch_rows_where(
        "signals", _SELECT,
        filters={"materiality": "not.is.null"},
        limit=5000,
    )
    # Flatten defence_relevant from the nested documents join.
    # PostgREST returns documents as a list; take the first doc's flag.
    for row in rows:
        docs = row.pop("documents", None) or []
        if isinstance(docs, list):
            doc = docs[0] if docs else {}
        else:
            doc = docs or {}
        row["defence_relevant"] = bool(doc.get("defence_relevant"))
    log.info("  pool: %d signals with materiality", len(rows))
    return rows


def run(dry_run: bool = True, limit: int = SAMPLE_N,
        model: str = rs.DEFAULT_MODEL,
        out_dir: str = "docs") -> dict:
    """Score the calibration batch and render the DECISION table.

    dry_run=True: score via LLM, render the report, but do NOT write
    relevance scores back to the DB.
    """
    import anthropic

    today = date.today()
    seed = today.strftime("%Y-%m-%d")
    client = anthropic.Anthropic()

    # --- Sample ------------------------------------------------------------------
    pool = _load_signals()
    sample, shortfalls = _stratified_sample(pool, per_bucket=limit // 5, seed=seed)
    sample = sample[:limit]
    log.info("Calibration sample: %d signals (dry_run=%s)", len(sample), dry_run)

    # --- Score -------------------------------------------------------------------
    scored = []
    errors = 0
    for sig in sample:
        # Use existing relevance if already scored (avoids double-spend).
        if sig.get("relevance") is not None:
            scored.append(sig)
            log.debug("  reuse %s relevance=%d", sig["id"], sig["relevance"])
            continue
        try:
            rel = rs.score_one(sig.get("title") or "", sig.get("summary") or "", model, client)
            sig = dict(sig)
            sig["relevance"] = rel
            if not dry_run:
                supabase_client.update_row("signals", sig["id"], {"relevance": rel})
            log.info("  %s -> relevance=%d | %.60s", sig["id"], rel, sig.get("title") or "")
        except Exception as e:
            log.warning("  error scoring %s: %s", sig["id"], e)
            errors += 1
            sig = dict(sig)
            sig["relevance"] = None
        scored.append(sig)
        time.sleep(0.05)

    scorable = [s for s in scored if s.get("relevance") is not None]
    log.info("Scored: %d  errors: %d  reused: %d", len(scorable), errors,
             sum(1 for s in scored if s.get("relevance") is not None and
                 s not in sample[:len(sample) - len(scored)]))

    # --- Relevance distribution --------------------------------------------------
    rel_dist = Counter(s["relevance"] for s in scorable)

    # --- Lens comparison ---------------------------------------------------------
    current_in = sum(1 for s in scorable if _passes_current_lens(s))

    lens_rows = {}
    for floor in FLOORS:
        new_in = sum(1 for s in scorable if _passes_relevance_lens(s, floor))
        both = sum(1 for s in scorable
                   if _passes_current_lens(s) and _passes_relevance_lens(s, floor))
        added = sum(1 for s in scorable
                    if not _passes_current_lens(s) and _passes_relevance_lens(s, floor))
        dropped = sum(1 for s in scorable
                      if _passes_current_lens(s) and not _passes_relevance_lens(s, floor))
        lens_rows[floor] = {
            "new_in": new_in,
            "both": both,
            "added": added,
            "dropped": dropped,
        }

    # --- Timing window sensitivity -----------------------------------------------
    # How many imminent signals does the window size admit?
    window_counts = {}
    for w in WINDOWS:
        imminent = sum(
            1 for s in scorable
            if _days_ahead(s, today) is not None and _days_ahead(s, today) <= w
        )
        window_counts[w] = imminent

    # --- Render ------------------------------------------------------------------
    report = _render_report(
        sample=scorable,
        today=today,
        model=model,
        dry_run=dry_run,
        shortfalls=shortfalls,
        errors=errors,
        rel_dist=rel_dist,
        current_in=current_in,
        lens_rows=lens_rows,
        window_counts=window_counts,
        limit=limit,
    )

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = today.strftime("%Y-%m-%d")
    md_path = out / f"relevance-calibration-{stamp}.md"
    json_path = out / f"relevance-calibration-{stamp}.json"

    md_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps({
        "generated": stamp,
        "model": model,
        "dry_run": dry_run,
        "sample_n": len(scorable),
        "errors": errors,
        "rel_dist": {str(k): v for k, v in rel_dist.items()},
        "current_in": current_in,
        "lens": {str(f): v for f, v in lens_rows.items()},
        "window_counts": {str(w): c for w, c in window_counts.items()},
        "signals": [
            {"id": s["id"], "relevance": s.get("relevance"),
             "materiality": s.get("materiality"),
             "defence_relevant": bool(s.get("defence_relevant")),
             "public_safety": bool(s.get("public_safety")),
             "expected_timing": s.get("expected_timing")}
            for s in scorable
        ],
    }, indent=2), encoding="utf-8")

    log.info("Report: %s", md_path)
    log.info("Data:   %s", json_path)
    print(report)

    return {
        "sample_n": len(scorable),
        "errors": errors,
        "dry_run": dry_run,
        "current_in": current_in,
        "lens": lens_rows,
        "window_counts": window_counts,
        "md_path": str(md_path),
        "json_path": str(json_path),
    }


# ---------------------------------------------------------------------------
# Report renderer
# ---------------------------------------------------------------------------

def _render_report(
    sample, today, model, dry_run, shortfalls, errors,
    rel_dist, current_in, lens_rows, window_counts, limit,
) -> str:
    n = len(sample)
    lines = [
        "# Relevance calibration batch",
        f"",
        f"**Date:** {today}  ",
        f"**Model:** {model}  ",
        f"**Sample:** {n} of {limit} requested  ",
        f"**Errors:** {errors}  ",
        f"**Dry-run:** {dry_run}  ",
        f"",
    ]
    if shortfalls:
        for m, deficit in sorted(shortfalls.items()):
            lines.append(f"_Note: materiality={m} stratum short by {deficit} (thin pool)._")
        lines.append("")

    # Relevance distribution
    lines += [
        "## Relevance score distribution",
        "",
        "| Score | Count | % of sample |",
        "|-------|-------|-------------|",
    ]
    for score in range(1, 6):
        cnt = rel_dist.get(score, 0)
        pct = 100 * cnt / n if n else 0
        lines.append(f"| {score} | {cnt} | {pct:.1f}% |")
    lines.append("")

    # Materiality distribution (for reference)
    mat_dist = Counter(s.get("materiality") or 0 for s in sample)
    lines += [
        "## Materiality distribution (reference sample)",
        "",
        "| Materiality | Count |",
        "|-------------|-------|",
    ]
    for m in range(1, 6):
        lines.append(f"| {m} | {mat_dist.get(m, 0)} |")
    lines.append("")

    # Current lens baseline
    pct_curr = 100 * current_in / n if n else 0
    lines += [
        "## Lens comparison",
        "",
        f"**Current lens** (defence OR public_safety AND materiality >= 4): "
        f"{current_in} of {n} ({pct_curr:.1f}%)",
        "",
        "| Floor | In proposed lens | Added vs current | Dropped vs current | "
        "Overlap (both) |",
        "|-------|-----------------|------------------|-------------------|----------------|",
    ]
    for floor in FLOORS:
        r = lens_rows[floor]
        pct_new = 100 * r["new_in"] / n if n else 0
        lines.append(
            f"| relevance >= {floor} | {r['new_in']} ({pct_new:.1f}%) | "
            f"+{r['added']} | -{r['dropped']} | {r['both']} |"
        )
    lines.append("")

    # Window sensitivity
    lines += [
        "## Timing window sensitivity (imminent signals in sample)",
        "",
        "| Window | Imminent count |",
        "|--------|---------------|",
    ]
    for w in WINDOWS:
        lines.append(f"| +{w} days | {window_counts.get(w, 0)} |")
    lines.append("")

    # Decision prompt
    lines += [
        "## DECISION required",
        "",
        "Choose the floor and window for the new lens:",
        "",
        "- **Floor 3** admits more signals (broader net, includes dual-use adjacent)",
        "- **Floor 4** matches the current materiality bar in strictness",
        "- **+30 days** vs **+35 days**: the current default is +35; see window row above",
        "",
        "Respond with: `floor=<3|4> window=<30|35>`",
        "",
        "After the ruling, Phase 2 will: (1) full backfill all ~12,000 unscored signals, "
        "(2) update apply_lens() threshold, (3) update rank_key() to weighted score formula.",
        "",
    ]
    if dry_run:
        lines.append(
            "> **DRY-RUN**: relevance scores were computed but NOT written to the database. "
            "Run with `--run` to persist them."
        )
    else:
        lines.append(
            "> **SCORES WRITTEN**: relevance values for this batch are now in the database."
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description="Relevance calibration batch + DECISION table")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="Score via LLM but do not write to DB")
    mode.add_argument("--run", action="store_true",
                      help="Score and write relevance to DB")
    p.add_argument("--limit", type=int, default=SAMPLE_N,
                   help=f"Sample size (default {SAMPLE_N})")
    p.add_argument("--model", default=rs.DEFAULT_MODEL,
                   help="Override model (default: %(default)s)")
    p.add_argument("--out-dir", default="docs",
                   help="Output directory for report files (default: docs/)")
    args = p.parse_args(argv)
    result = run(dry_run=args.dry_run, limit=args.limit, model=args.model,
                 out_dir=args.out_dir)
    print(f"\nsample={result['sample_n']} errors={result['errors']} "
          f"current_in={result['current_in']} dry_run={result['dry_run']}")


if __name__ == "__main__":
    main()
