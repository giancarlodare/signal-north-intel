"""OpenTimestamps anchoring for the prediction ledger (Phase B).

The external proof half of the "we called it, provably, before date X" claim.
The database already forces made_at = now() and blocks edits, but that only
proves a claim was not changed AFTER it was frozen and not backdated at insert
against OUR clock. To prove existence-by-date to a skeptical third party, each
claim's hash is submitted to the public OpenTimestamps calendars, which anchor
it (via Bitcoin) to a time no one can forge. The returned proof is stored in
prediction_anchors; because predictions are immutable, the anchor lives in its
own append-only table.

The proof returned at stamp time is PENDING (the calendars attest receipt
immediately; Bitcoin confirmation follows in hours). That pending proof is
already a valid timestamp anchor; completing it to a full Bitcoin proof is a
later `ots upgrade`, a future enhancement, and does not block anchoring now.

API verified against opentimestamps 0.4.5 from a CI runner (calendar servers
are unreachable through the local dev proxy), so this is exercised, not guessed.

    python -m src.anchor --dry-run
"""
import argparse
import logging
import sys
from typing import Optional

from . import supabase_client

log = logging.getLogger(__name__)

STAMP = "anchor@v1"
ANCHOR_TYPE = "opentimestamps"
CALENDARS = (
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://alice.btc.calendar.opentimestamps.org",
)


def stamp_hash(claim_hash_hex: str) -> tuple:
    """Submit a claim's sha256 hash to the OpenTimestamps calendars and return
    (proof_bytes, calendars_submitted). Raises if no calendar accepts it, so a
    failed stamp never records a bogus anchor. Isolated so tests mock it."""
    from opentimestamps.core.timestamp import Timestamp, DetachedTimestampFile
    from opentimestamps.core.op import OpSHA256
    from opentimestamps.calendar import RemoteCalendar
    from opentimestamps.core.serialize import BytesSerializationContext

    digest = bytes.fromhex(claim_hash_hex)
    ts = Timestamp(digest)
    submitted = 0
    for url in CALENDARS:
        try:
            ts.merge(RemoteCalendar(url).submit(digest))
            submitted += 1
        except Exception:   # noqa: BLE001 - one calendar down must not fail the stamp
            log.warning("OpenTimestamps calendar %s failed", url, exc_info=True)
    if submitted == 0:
        raise RuntimeError("no OpenTimestamps calendar accepted the stamp")

    ctx = BytesSerializationContext()
    DetachedTimestampFile(OpSHA256(), ts).serialize(ctx)
    return ctx.getbytes(), submitted


def run(dry_run: bool = False, limit: int = 100) -> int:
    stats = {"examined": 0, "anchored": 0, "skipped_existing": 0, "errors": 0}

    predictions = supabase_client.fetch_all_rows_where(
        "predictions", "id,claim_hash", {})
    anchors = supabase_client.fetch_all_rows_where(
        "prediction_anchors", "prediction_id,anchor_type", {})
    have_ots = {a["prediction_id"] for a in anchors
                if a.get("anchor_type") == ANCHOR_TYPE}

    for pred in predictions:
        stats["examined"] += 1
        if pred["id"] in have_ots:
            stats["skipped_existing"] += 1
            continue
        if stats["anchored"] >= limit:
            log.info("Per-run anchor cap (%d) reached; rest next run", limit)
            break
        try:
            proof, submitted = stamp_hash(pred["claim_hash"])
            payload = {
                "prediction_id": pred["id"],
                "claim_hash": pred["claim_hash"],
                "anchor_type": ANCHOR_TYPE,
                "anchor_ref": proof.hex(),
                "note": f"pending; {submitted} calendars",
            }
            if dry_run:
                log.info("[dry-run] would anchor prediction %s (%d-byte proof, %d calendars)",
                         pred["id"], len(proof), submitted)
            else:
                supabase_client.insert_row("prediction_anchors", payload)
            stats["anchored"] += 1
        except Exception:   # noqa: BLE001 - one bad claim must not kill the run
            log.exception("Failed to anchor prediction %s", pred.get("id"))
            stats["errors"] += 1

    log.info("Anchor%s: %s", " (DRY RUN)" if dry_run else "", stats)
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenTimestamps anchoring for predictions")
    parser.add_argument("--limit", type=int, default=100,
                        help="max predictions to anchor per run (default 100)")
    parser.add_argument("--dry-run", action="store_true",
                        help="stamp and log, write no anchor rows")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(dry_run=args.dry_run, limit=args.limit))
