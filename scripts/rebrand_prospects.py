"""One-off data fix (operator 2026-08-05): the firm formerly named
"Synapse Advisory" rebranded to "Da-Ré Advisory". Two prospects rows carry
the old name in conflict_note (Skydio, Warroad). This updates the LIVE table
only -- the seed migration (migrations/2026-07-10_prospects_seed.sql) is left
untouched as historical record, per operator instruction.

Substring replace, so the rest of each note is preserved and the run is
idempotent: a second run finds no "Synapse Advisory" left and changes nothing.
Default is a dry-run that prints before/after; pass --apply to write.

    python -m scripts.rebrand_prospects              # dry-run, prints diff
    python -m scripts.rebrand_prospects --apply       # writes the update
"""
import sys

from src.supabase_client import _headers, _request, fetch_rows_where

OLD = "Synapse Advisory"
NEW = "Da-Ré Advisory"


def main() -> int:
    apply = "--apply" in sys.argv[1:]

    # BEFORE: every prospects row whose conflict_note still carries the old name.
    rows = fetch_rows_where(
        "prospects",
        select="id,company_name,conflict_note",
        filters={"conflict_note": f"ilike.*{OLD}*"},
    )

    print(f"[rebrand-prospects] mode={'APPLY' if apply else 'DRY-RUN'}")
    print(f"[rebrand-prospects] rows matching {OLD!r} in conflict_note: {len(rows)}")
    if not rows:
        print("[rebrand-prospects] nothing to do (already rebranded or no match).")
        return 0

    for r in rows:
        old_note = r["conflict_note"] or ""
        new_note = old_note.replace(OLD, NEW)
        print(f"\n  {r['company_name']} (id={r['id']})")
        print(f"    BEFORE: {old_note}")
        print(f"    AFTER : {new_note}")
        if apply:
            # PATCH the single row by id; write only conflict_note.
            _request(
                "PATCH",
                "prospects",
                headers=_headers(),
                params={"id": f"eq.{r['id']}"},
                json={"conflict_note": new_note},
            )

    if not apply:
        print("\n[rebrand-prospects] DRY-RUN only. Re-run with --apply to write.")
        return 0

    # AFTER: read the same rows back and confirm the old name is gone.
    check = fetch_rows_where(
        "prospects",
        select="id,company_name,conflict_note",
        filters={"conflict_note": f"ilike.*{OLD}*"},
    )
    print(f"\n[rebrand-prospects] post-write rows still matching {OLD!r}: {len(check)}")
    for r in rows:
        confirm = fetch_rows_where(
            "prospects",
            select="company_name,conflict_note",
            filters={"id": f"eq.{r['id']}"},
        )
        note = confirm[0]["conflict_note"] if confirm else "<row not found>"
        print(f"  {r['company_name']}: {note}")
    if check:
        print("[rebrand-prospects] ERROR: some rows still carry the old name.")
        return 1
    print("[rebrand-prospects] done. All matching rows rebranded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
