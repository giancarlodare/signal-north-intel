"""Phase 5 calibration audit: the standing honesty check on the scorer.

The corpus trusts the extraction scorer, so the scorer gets audited. Monthly
(or on demand after a prompt/collector change), a stratified sample of scored
signals is re-scored BLIND through the same extraction path (same module,
same prompt, same model, sight of the document only) and compared on the
LLM judgment fields: materiality, signal_type, confidence.

REPORT-ONLY, structurally. This module reads the database and writes two
local files (a markdown report and a JSON record) for the workflow to post
as a GitHub issue and artifact. It has NO database write path, and
tests/test_calibration_audit.py greps this source for write verbs so a
regression to auto-correction cannot land silently. No audit result may
modify a signal, a score, or a threshold: adjudication is a human decision
made after reading the report. Design: docs/calibration-audit-design.md.

    python -m src.calibration_audit --dry-run   # fetch + sample + plan, no LLM
    python -m src.calibration_audit --run       # full audit, writes report files
"""
import argparse
import json
import logging
import random
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from . import supabase_client, taxonomy
from .brief_generator import LENS_MIN_MATERIALITY, RECENT_MIN_MATERIALITY
from .signal_extractor import DEFAULT_MODEL, extract_signals

log = logging.getLogger(__name__)

BACK_DAYS = 90            # audit the trailing window; older scores were audited earlier
PER_GRADE = 6             # 6 x 5 grades = the ~30 monthly sample
GRADES = (1, 2, 3, 4, 5)
MATCH_THRESHOLD = 0.5     # Jaccard floor for pairing an original with a re-score
# The decision boundaries in force: a materiality flip that crosses one of
# these changes the brief a reader sees; a flip that crosses none does not.
BOUNDARIES = (RECENT_MIN_MATERIALITY, LENS_MIN_MATERIALITY)

REPORT_MD = "audit-report.md"
REPORT_JSON = "audit-results.json"


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def _tokens(s) -> set:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def similarity(a, b) -> float:
    """Jaccard overlap of word tokens; 0.0 when either side is empty."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def stratified_sample(signals, per_grade: int = PER_GRADE, seed: str = ""):
    """Sample per evidence-grade stratum so high grades are always represented.
    A thin stratum contributes ALL of it and the shortfall is reported, never
    padded from other grades. Seeded (run month) so a re-run reproduces the
    sample for adjudication. Returns (sample, shortfalls: grade -> missing)."""
    rng = random.Random(seed)
    by_grade = {g: [] for g in GRADES}
    for s in signals:
        g = s.get("evidence_grade") or 0
        if g in by_grade:
            by_grade[g].append(s)
    sample, shortfalls = [], {}
    for g in GRADES:
        pool = sorted(by_grade[g], key=lambda s: str(s.get("id")))
        take = min(per_grade, len(pool))
        sample.extend(rng.sample(pool, take))
        if take < per_grade:
            shortfalls[g] = per_grade - take
    return sample, shortfalls


def match_reextracted(original, candidates):
    """Pair the audited signal with one blind re-extracted signal: best token
    overlap on quote_or_line first, then title, floor MATCH_THRESHOLD. Returns
    (candidate, score) or (None, 0.0): no match means NOT REPRODUCED, a
    first-class disagreement (the scorer no longer even finds the signal)."""
    best, best_score = None, 0.0
    for c in candidates:
        q = similarity(original.get("quote_or_line"), c.get("quote_or_line"))
        t = similarity(original.get("title"), c.get("title"))
        score = max(q, t)
        if score > best_score:
            best, best_score = c, score
    if best_score >= MATCH_THRESHOLD:
        return best, best_score
    return None, 0.0


def compare(original, matched, doc_type) -> dict:
    """Per-field agreement record for one audited signal. Exact match is the
    headline everywhere; within-one materiality is secondary; materiality
    flips that cross a decision boundary in force are flagged, because the
    boundaries are the product (a 4 to 3 flip changes the draft; 5 to 4
    changes nothing a reader sees)."""
    rec = {
        "signal_id": original.get("id"),
        "title": original.get("title"),
        "quote_or_line": original.get("quote_or_line"),
        "evidence_grade": original.get("evidence_grade"),
        "extracted_by": original.get("extracted_by"),
        "matched": matched is not None,
    }
    if matched is None:
        rec["category"] = "not_reproduced"
        return rec
    m_orig = int(original.get("materiality") or 0)
    m_new = int(matched.get("materiality") or 0)
    t_orig = original.get("signal_type")
    t_new = matched.get("signal_type")
    c_orig = original.get("confidence")
    c_new = matched.get("confidence")
    rec.update({
        "materiality": {"original": m_orig, "rescored": m_new,
                        "exact": m_orig == m_new,
                        "within_one": abs(m_orig - m_new) <= 1,
                        "boundary_crossings": [b for b in BOUNDARIES
                                               if (m_orig >= b) != (m_new >= b)]},
        "signal_type": {"original": t_orig, "rescored": t_new,
                        "exact": t_orig == t_new,
                        "grade_equal": taxonomy.grade(t_orig or "", doc_type or "")
                                       == taxonomy.grade(t_new or "", doc_type or "")},
        "confidence": {"original": c_orig, "rescored": c_new,
                       "exact": c_orig == c_new},
    })
    rec["category"] = ("agree" if rec["materiality"]["exact"]
                       and rec["signal_type"]["exact"]
                       and rec["confidence"]["exact"] else "field_mismatch")
    return rec


def _rate(hits, total) -> str:
    return f"{hits}/{total} ({hits / total:.0%})" if total else "n/a (0 compared)"


def render_report(records, meta) -> str:
    """The report the operator reads. Header, agreement table (exact headline,
    within-one secondary, boundary-crossing count), then EVERY disagreement
    with both scores and the signal text for adjudication, then caveats."""
    L = [f"# Calibration audit {meta['month']}", ""]
    trigger = meta.get("reason") or "scheduled monthly run"
    L += [f"Trigger: {trigger}", f"Re-score model: {meta['model']}",
          f"Window: trailing {BACK_DAYS} days ({meta['eligible']} eligible signals)",
          f"Prompt versions in sample: {', '.join(sorted(meta['prompt_versions'])) or 'none'}",
          ""]

    L.append("## Sample")
    L.append("")
    L.append("| Grade | Sampled | Target |")
    L.append("|---|---|---|")
    for g in GRADES:
        n = sum(1 for r in records if r.get("evidence_grade") == g)
        note = f" (short by {meta['shortfalls'][g]})" if g in meta["shortfalls"] else ""
        L.append(f"| {g} | {n}{note} | {meta['per_grade']} |")
    if meta.get("unfetchable"):
        L.append("")
        L.append(f"{meta['unfetchable']} sampled signal(s) excluded: source document "
                 "no longer fetchable. Counted here, never substituted.")
    L.append("")

    compared = [r for r in records if r["matched"]]
    not_reproduced = [r for r in records if not r["matched"]]
    n = len(compared)

    def field_rates(field, key="exact"):
        total_hits = sum(1 for r in compared if r[field][key])
        per_grade = {}
        for g in GRADES:
            gs = [r for r in compared if r.get("evidence_grade") == g]
            per_grade[g] = (sum(1 for r in gs if r[field][key]), len(gs))
        return total_hits, per_grade

    L.append("## Agreement (exact match is the headline; the boundaries are the product)")
    L.append("")
    L.append("| Field | Overall | " + " | ".join(f"G{g}" for g in GRADES) + " |")
    L.append("|---|---|" + "---|" * len(GRADES))
    for label, field, key in (("materiality (exact)", "materiality", "exact"),
                              ("materiality (within one, secondary)", "materiality", "within_one"),
                              ("signal_type (exact)", "signal_type", "exact"),
                              ("derived grade equal", "signal_type", "grade_equal"),
                              ("confidence (exact)", "confidence", "exact")):
        hits, per_grade = field_rates(field, key)
        row = [f"| {label} | {_rate(hits, n)} "]
        for g in GRADES:
            h, t = per_grade[g]
            row.append(f"| {_rate(h, t)} ")
        L.append("".join(row) + "|")
    boundary_flips = sum(1 for r in compared if r["materiality"]["boundary_crossings"])
    L += ["", f"Not reproduced (blind re-score no longer finds the signal): "
          f"{len(not_reproduced)} of {len(records)}",
          f"Materiality disagreements crossing a decision boundary in force "
          f"(bars {', '.join(str(b) for b in BOUNDARIES)}): {boundary_flips}", ""]

    disagreements = [r for r in records if r["category"] != "agree"]
    L.append(f"## Disagreements to adjudicate ({len(disagreements)})")
    L.append("")
    if not disagreements:
        L.append("None. Every sampled signal was reproduced with all three "
                 "fields matching exactly.")
    for r in disagreements:
        L.append(f"### {r.get('title') or '(untitled signal)'}")
        L.append("")
        L += [f"- signal: `{r['signal_id']}` (grade {r.get('evidence_grade')}, "
              f"scored by {r.get('extracted_by')})",
              f"- buyer: {r.get('buyer') or 'unresolved'}; doc_type: {r.get('doc_type')}",
              f"- document: {r.get('doc_url') or 'no public URL'}"]
        if r.get("quote_or_line"):
            L.append(f"- quote: \"{r['quote_or_line']}\"")
        if r["category"] == "not_reproduced":
            L.append("- NOT REPRODUCED: the blind re-score found no matching "
                     "signal in this document.")
        else:
            for field in ("materiality", "signal_type", "confidence"):
                f = r[field]
                if not f["exact"]:
                    extra = ""
                    if field == "materiality" and f["boundary_crossings"]:
                        extra = (" ; CROSSES boundary "
                                 + ", ".join(str(b) for b in f["boundary_crossings"]))
                    L.append(f"- {field}: {f['original']} vs re-scored "
                             f"{f['rescored']}{extra}")
        L.append("")

    L.append("## Method and rule")
    L.append("")
    L.append("Blind re-score through the production extraction path (same prompt, "
             "same model, document only). REPORT-ONLY: nothing in this audit "
             "modified a signal, a score, or a threshold; any correction is a "
             "human decision made from this report.")
    return "\n".join(L)


def run(dry_run: bool = True, today: date | None = None, reason: str = "",
        per_grade: int = PER_GRADE, model: str = DEFAULT_MODEL,
        out_dir: str = ".") -> dict:
    today = today or date.today()
    month = today.strftime("%Y-%m")
    cutoff = today - timedelta(days=BACK_DAYS)

    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,title,quote_or_line,signal_type,confidence,materiality,evidence_grade,"
        "extracted_by,document_id,created_at,organizations(canonical_name)",
        {"suppressed": "is.false", "extracted_by": "not.is.null",
         "document_id": "not.is.null", "created_at": f"gte.{cutoff}"})
    sample, shortfalls = stratified_sample(signals, per_grade=per_grade, seed=month)
    log.info("Calibration audit %s (%s): %d eligible signals, sampled %d "
             "(shortfalls %s)", month, "dry-run" if dry_run else "RUN",
             len(signals), len(sample), shortfalls or "{}")

    if dry_run:
        by_grade = Counter(s.get("evidence_grade") for s in sample)
        log.info("  sample by grade: %s; no LLM calls made, nothing written",
                 dict(by_grade))
        return {"month": month, "eligible": len(signals), "sampled": len(sample),
                "shortfalls": shortfalls, "dry_run": True}

    records = []
    unfetchable = 0
    prompt_versions = set()
    for sig in sample:
        prompt_versions.add(sig.get("extracted_by") or "unknown")
        docs = supabase_client.fetch_rows_where(
            "documents", "id,title,doc_type,url,published_on,source_id,content",
            {"id": f"eq.{sig['document_id']}"}, limit=1)
        doc = docs[0] if docs else None
        if not doc or not ((doc.get("content") or "").strip() or doc.get("title")):
            unfetchable += 1
            continue
        source_name = supabase_client.get_source_name(doc["source_id"])
        # Blind: the call sees the document only, never the original scores.
        # An API failure here propagates and fails the run RED on purpose; a
        # partial audit must never be posted as if complete.
        candidates, _stamp = extract_signals(doc, source_name, model)
        matched, _score = match_reextracted(sig, candidates)
        rec = compare(sig, matched, doc.get("doc_type"))
        rec["buyer"] = (_one(sig.get("organizations")) or {}).get("canonical_name")
        rec["doc_type"] = doc.get("doc_type")
        rec["doc_url"] = doc.get("url")
        records.append(rec)

    meta = {"month": month, "model": model, "reason": reason,
            "eligible": len(signals), "per_grade": per_grade,
            "shortfalls": shortfalls, "unfetchable": unfetchable,
            "prompt_versions": prompt_versions}
    report = render_report(records, meta)

    out = Path(out_dir)
    (out / REPORT_MD).write_text(report, encoding="utf-8")
    (out / REPORT_JSON).write_text(
        json.dumps({**meta, "prompt_versions": sorted(prompt_versions),
                    "records": records}, indent=2, default=str),
        encoding="utf-8")
    log.info("  wrote %s and %s", out / REPORT_MD, out / REPORT_JSON)

    agreed = sum(1 for r in records if r["category"] == "agree")
    return {"month": month, "eligible": len(signals), "sampled": len(sample),
            "compared": len(records), "agreed_exact_all_fields": agreed,
            "not_reproduced": sum(1 for r in records if not r["matched"]),
            "unfetchable": unfetchable, "shortfalls": shortfalls,
            "dry_run": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calibration audit: blind re-score of a stratified sample; report-only")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="fetch + sample + plan, no LLM calls, nothing written")
    group.add_argument("--run", action="store_true",
                       help="full audit; writes audit-report.md and audit-results.json")
    parser.add_argument("--reason", default="",
                        help="why this manual run (recorded in the report header)")
    parser.add_argument("--out-dir", default=".",
                        help="directory for the report files")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run(dry_run=not args.run, reason=args.reason, out_dir=args.out_dir)
    log.info("result: %s", result)
    sys.exit(0)
