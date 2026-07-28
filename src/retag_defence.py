"""Deterministic re-tag of documents.defence_relevant after the whole-word
matcher fix (operator 2026-07-28; the CMHC "Default Real Estate Services"
false positive, same class as public_safety's Bendix 'ems'-in-"Systems").

Scope: only documents currently tagged defence_relevant=true. The whole-word
matcher is strictly narrower than the substring matcher it replaced, so no
false-tagged document can flip TO true; the pass only ever clears tags.

Per document, on the SAME stored text the tag can be re-derived from
(title + content):
  keep          whole-word defence match present -> tag stands.
  flip          substring hit but NO whole-word hit -> verified false
                positive of the fixed bug; clear the tag.
  unverifiable  no hit of either kind in stored text. The original tag came
                from source text we did not store (award-notice CSV rows keep
                only a title). Left UNCHANGED: clearing it would fabricate
                certainty about text we cannot re-read.

Flip-count discipline (operator 2026-07-28): --dry-run reports the corpus-wide
flip count and per-doc-type breakdown for approval BEFORE any --apply run.
Once applied, the daily apply_public_safety --apply pass in daily-collect
re-derives signals.public_safety from the corrected tags, so member-facing and
public surfaces self-heal with no further wiring.

Loud failure: zero defence-tagged documents raises rather than reporting a
clean pass on an empty read.

    python -m src.retag_defence --dry-run   # flip count + examples, no writes
    python -m src.retag_defence --apply     # clear verified false positives
"""
import argparse
import logging
import sys

from . import supabase_client
from .filters import Keywords, _matches_any, _substring_matches_any, load_keywords

log = logging.getLogger(__name__)


def classify(title: str | None, content: str | None, keywords: Keywords) -> str:
    """Pure: 'keep' | 'flip' | 'unverifiable' for one defence-tagged doc."""
    text = f"{title or ''} {content or ''}"
    if _matches_any(text, keywords.defence):
        return "keep"
    if _substring_matches_any(text, keywords.defence):
        return "flip"
    return "unverifiable"


def run(dry_run: bool = True) -> dict:
    docs = supabase_client.fetch_all_rows_where(
        "documents", "id,doc_type,title,content,defence_relevant",
        {"defence_relevant": "is.true"})
    if not docs:
        raise SystemExit("retag_defence: zero defence-tagged documents fetched; "
                         "refusing to report success on an empty read.")

    keywords = load_keywords()
    counts = {"keep": 0, "flip": 0, "unverifiable": 0}
    by_type: dict[str, dict] = {}
    flips = []
    for d in docs:
        verdict = classify(d.get("title"), d.get("content"), keywords)
        counts[verdict] += 1
        t = d.get("doc_type") or "?"
        by_type.setdefault(t, {"keep": 0, "flip": 0, "unverifiable": 0})[verdict] += 1
        if verdict == "flip":
            flips.append(d)

    log.info("retag_defence %s: %d defence-tagged docs; keep=%d flip=%d "
             "unverifiable=%d", "dry-run" if dry_run else "APPLY",
             len(docs), counts["keep"], counts["flip"], counts["unverifiable"])
    for t in sorted(by_type):
        c = by_type[t]
        log.info("  by doc_type %-14s keep=%-4d flip=%-4d unverifiable=%d",
                 t, c["keep"], c["flip"], c["unverifiable"])
    for d in flips[:20]:
        log.info("  FLIP %s [%s] %s", d["id"], d.get("doc_type"),
                 (d.get("title") or "")[:90])
    if len(flips) > 20:
        log.info("  ... and %d more flips", len(flips) - 20)

    written = 0
    if not dry_run:
        for d in flips:
            supabase_client.update_row("documents", d["id"],
                                       {"defence_relevant": False})
            written += 1
        log.info("  cleared defence_relevant on %d documents", written)

    return {"docs": len(docs), **counts, "written": written}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Re-tag documents.defence_relevant (whole-word fix)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="flip count + examples, no writes")
    group.add_argument("--apply", action="store_true",
                       help="clear verified false positives")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    run(dry_run=not args.apply)
    sys.exit(0)
