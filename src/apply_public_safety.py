"""Derive signals.public_safety across the corpus: the INDEPENDENT member-read
gate (docs/public-safety-relevance-filter-design.md, operator 2026-07-27).

This is deliberately SEPARATE from the brief generator. The brief lens is the
composition gate; this pass is the second, independent barrier that populates
the persisted flag the member RLS clamp reads. Because it shares no code path
with brief_generator, a lens break or a new composition path cannot make a
non-public-safety signal member-visible: the flag here (and the RLS clamp that
reads it) still says no.

Determination per signal (same predicate as the lens, applied per-signal):
  public_safety := defence_relevant OR is_public_safety(resolved org_type, title)
A defence_relevant signal is public-safety by definition (dual-use subset).

Idempotent: writes only rows whose stored flag differs from the computed value,
so a steady state is a no-op. Loud-failure: an empty corpus raises rather than
silently reporting success. Fail-closed by construction: the column defaults
false in the migration, so anything this pass has not yet set true is invisible
to a member.

Pre-migration guard: if the public_safety column does not exist yet (the
operator has not pasted 2026-07-27_signals_public_safety.sql), the pass logs a
clear notice and exits 0, so wiring it into the daily pipeline before go-live
does not turn the pipeline red. Once the column exists it runs normally.

    python -m src.apply_public_safety --dry-run   # compute + report, write nothing
    python -m src.apply_public_safety --apply      # write the flag
"""
import argparse
import logging
import sys

from . import public_safety, supabase_client
from .filters import load_keywords

log = logging.getLogger(__name__)


def _one(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def column_present() -> bool:
    """True if signals.public_safety exists. A missing column means the
    member-read migration has not been pasted yet (pre-go-live)."""
    try:
        supabase_client.fetch_rows_where("signals", "id,public_safety", {}, limit=1)
        return True
    except Exception as e:  # noqa: BLE001 - any read error here means "not ready"
        log.info("public_safety column not present yet (%s); skipping. Paste "
                 "migrations/2026-07-27_signals_public_safety.sql to enable the "
                 "member-read gate.", type(e).__name__)
        return False


def compute(signals, keywords) -> list:
    """Pure: return [(signal_id, new_value)] for signals whose computed
    public_safety differs from the stored value. `signals` carry title,
    public_safety, organizations(org_type), documents(defence_relevant)."""
    changes = []
    for s in signals:
        org = _one(s.get("organizations")) or {}
        doc = _one(s.get("documents")) or {}
        defence = bool(doc.get("defence_relevant"))
        val = defence or public_safety.is_public_safety(
            org.get("org_type"), s.get("title"), keywords)
        if bool(s.get("public_safety")) != val:
            changes.append((s["id"], val))
    return changes


def run(dry_run: bool = True) -> dict:
    if not column_present():
        return {"skipped": True, "reason": "column_absent"}

    signals = supabase_client.fetch_all_rows_where(
        "signals",
        "id,title,public_safety,"
        "organizations(org_type),"
        "documents!inner(defence_relevant)",
        {"suppressed": "is.false"})
    if not signals:
        # Loud failure: a silent-empty corpus is never recorded as success.
        raise SystemExit("apply_public_safety: zero live signals fetched; "
                         "refusing to report success on an empty read.")

    keywords = load_keywords()
    changes = compute(signals, keywords)
    n_true = sum(1 for _, v in changes if v)
    n_false = sum(1 for _, v in changes if not v)
    stored_true = sum(1 for s in signals if bool(s.get("public_safety")))
    post_true = stored_true + n_true - n_false

    log.info("apply_public_safety %s: %d live signals; %d flag changes "
             "(%d -> true, %d -> false); public-safety after: %d of %d",
             "dry-run" if dry_run else "APPLY", len(signals), len(changes),
             n_true, n_false, post_true, len(signals))

    written = 0
    if not dry_run:
        for sid, val in changes:
            supabase_client.update_row("signals", sid, {"public_safety": val})
            written += 1
        log.info("  wrote %d public_safety updates", written)

    return {"signals": len(signals), "changes": len(changes),
            "to_true": n_true, "to_false": n_false,
            "public_safety_after": post_true, "written": written}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Derive signals.public_safety (member-read gate)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="compute + report, write nothing")
    group.add_argument("--apply", action="store_true", help="write the flag")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    result = run(dry_run=not args.apply)
    sys.exit(0)
