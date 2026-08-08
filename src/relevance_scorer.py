"""Relevance scorer: assigns signals.relevance 1..5 (generic-context).

The scored integer answers: "how much does this procurement signal matter to
someone selling into Canadian public safety?" Anchors from the design doc:

    5  Core public-safety vendor category (RMS, CAD, body-worn, ALPR, radio,
       forensics, dispatch, fleet, use-of-force, digital evidence)
    4  Directly relevant but not a primary vendor category (e.g. facilities
       renovation AT a police/fire service, major emergency-services IT)
    3  Dual-use or adjacent (a large municipality buying general IT, a
       regional infrastructure project that also serves public safety)
    2  Tangential (general civic spend near a public-safety agency)
    1  No public-safety vendor would bid this (civil works, watermain,
       parks, transit capital unrelated to dispatch/fleet)

The score is generic-context only (relevance(item, generic-context)).
It is NOT a member profile match; the Pro-tier monitoring product uses the
same function with a member profile as the context parameter (design:
docs/lens-redesign-design.md, addendum 2026-08-02). Nothing here bakes
context-as-scalar.

The lens inclusion rule (post-floor-ruling) will be:
    defence_relevant  OR  (public_safety AND relevance >= threshold)
where threshold is set by the operator from the calibration batch report.
This module scores; it does not change the lens.

    python -m src.relevance_scorer --dry-run --limit 200   # plan only
    python -m src.relevance_scorer --run    --limit 200    # calibration batch
    python -m src.relevance_scorer --run                   # full backfill
"""
import argparse
import logging
import os
import time
from typing import Optional

log = logging.getLogger(__name__)

# Default model: Haiku-class for cost efficiency (single-integer output,
# short prompt). Override via RELEVANCE_MODEL env var.
DEFAULT_MODEL = os.environ.get("RELEVANCE_MODEL", "claude-haiku-4-5-20251001")

# Scored-by stamp written to the DB so a future recalibration can filter
# by version and rescore only the rows that used an older prompt.
SCORER_VERSION = "relevance@v1"

# PostgREST select for signals missing a relevance score.
_SELECT = "id,title,summary"

_SYSTEM = (
    "You are a procurement-intelligence analyst specialising in Canadian "
    "public safety and defence. Score the relevance of this signal to "
    "vendors selling into police, fire, EMS, corrections, or defence agencies. "
    "Respond only with JSON matching the provided schema."
)

_USER_TEMPLATE = """\
Signal title: {title}

Summary: {summary}

Score how relevant this procurement signal is to a vendor selling into
Canadian public-safety or defence agencies. Use the 1-5 scale:

5 — Core vendor category: the procurement is the primary market for a
    public-safety or defence specialist (RMS, CAD, body-worn cameras,
    ALPR, radio communications, forensics, dispatch systems, armoured
    vehicles, use-of-force equipment, tactical gear, digital evidence
    management, fleet vehicles for police/fire/EMS, corrections technology)

4 — Directly relevant: facilities work, major IT, or infrastructure AT a
    police/fire/EMS/corrections/defence facility; the buyer is a
    public-safety agency even if any capable contractor can respond

3 — Dual-use or adjacent: a large municipality buying general technology
    or services that a public-safety vendor might supply; security systems
    at a civic facility; emergency management adjacent

2 — Tangential: general civic or regional spend near a public-safety
    agency but not specifically for it; unlikely to attract a specialist

1 — Irrelevant: civil infrastructure, parks, transit unrelated to
    emergency dispatch or fleet, watermains, road resurfacing, general
    civic amenities — no public-safety or defence vendor would bid this

Return: {{"relevance": <integer 1-5>}}"""

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "relevance": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    },
    "required": ["relevance"],
    "additionalProperties": False,
}


def score_one(title: str, summary: str, model: str, client) -> int:
    """Score a single signal. Returns 1..5. Clamps if the model misbehaves."""
    filled = _USER_TEMPLATE.format(
        title=(title or "").strip() or "(no title)",
        summary=(summary or "").strip() or "(no summary)",
    )
    resp = client.messages.create(
        model=model,
        max_tokens=32,
        system=_SYSTEM,
        messages=[{"role": "user", "content": filled}],
        output_config={"format": {"type": "json_schema", "schema": _RESPONSE_SCHEMA}},
    )
    try:
        raw = int(resp.content[0].text.strip()) if hasattr(resp.content[0], "text") else 3
    except Exception:
        import json as _json
        try:
            raw = int(_json.loads(resp.content[0].text).get("relevance", 3))
        except Exception:
            raw = 3
    return min(max(int(raw), 1), 5)


def run(dry_run: bool = False, limit: Optional[int] = None,
        model: str = DEFAULT_MODEL, workers: int = 1) -> dict:
    """Score unscored signals. Returns {scored, skipped_already_scored, errors}.

    dry_run=True fetches and calls the LLM but does NOT write to the DB,
    so you can check the distribution before committing the backfill.
    limit caps the number of signals processed (use 200 for the calibration
    batch; omit for the full backfill).
    workers > 1 enables concurrent scoring via ThreadPoolExecutor; the
    Anthropic client and supabase_client are both thread-safe.
    """
    import anthropic
    from . import supabase_client

    client = anthropic.Anthropic()
    stats = {"scored": 0, "skipped_already_scored": 0, "errors": 0, "model": model}

    log.info("relevance_scorer: model=%s dry_run=%s limit=%s workers=%d",
             model, dry_run, limit, workers)

    filters: dict = {"relevance": "is.null"}
    page_size = min(limit or 500, 500)
    fetched: list = []
    offset = 0
    while True:
        batch = supabase_client.fetch_rows_where(
            "signals", _SELECT, filters,
            limit=page_size, offset=offset,
        )
        fetched.extend(batch)
        if len(batch) < page_size or (limit and len(fetched) >= limit):
            break
        offset += len(batch)

    if limit:
        fetched = fetched[:limit]

    log.info("relevance_scorer: fetched %d unscored signals", len(fetched))

    def _process_one(sig):
        sig_id = sig["id"]
        title = sig.get("title") or ""
        summary = sig.get("summary") or ""
        try:
            score = score_one(title, summary, model, client)
            if dry_run:
                log.info("[dry-run] %s -> relevance=%d | %.60s", sig_id, score, title)
            else:
                supabase_client.update_row("signals", sig_id, {"relevance": score})
            return True
        except Exception as e:
            log.warning("relevance_scorer: error scoring %s: %s", sig_id, e)
            return False

    def _tally(ok: bool) -> None:
        if ok:
            stats["scored"] += 1
        else:
            stats["errors"] += 1

    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        lock = threading.Lock()
        done_count = 0
        total = len(fetched)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_process_one, sig): sig["id"] for sig in fetched}
            for future in as_completed(futures):
                ok = future.result()
                with lock:
                    done_count += 1
                    _tally(ok)
                    if done_count % 500 == 0:
                        log.info("relevance_scorer: progress %d/%d scored=%d errors=%d",
                                 done_count, total, stats["scored"], stats["errors"])
    else:
        for sig in fetched:
            ok = _process_one(sig)
            _tally(ok)
            # Polite rate-limit: Haiku has generous limits but a brief pause
            # prevents burst spikes on large backfills.
            time.sleep(0.05)

    log.info(
        "relevance_scorer: done — scored=%d errors=%d dry_run=%s",
        stats["scored"], stats["errors"], dry_run,
    )
    return stats


def main(argv=None):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    p = argparse.ArgumentParser(description="Assign signals.relevance 1..5")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="Score via LLM but do not write to DB")
    mode.add_argument("--run", action="store_true",
                      help="Score and write to DB")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap signals processed (200 for calibration batch)")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="Override model (default: %(default)s)")
    p.add_argument("--workers", type=int, default=1,
                   help="Concurrent scoring threads (default 1; use 20 for full backfill)")
    args = p.parse_args(argv)
    stats = run(dry_run=args.dry_run, limit=args.limit, model=args.model, workers=args.workers)
    print(f"scored={stats['scored']} errors={stats['errors']} "
          f"model={stats['model']} dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
