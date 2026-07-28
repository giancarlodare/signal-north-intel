"""Tests for the live-surface projection writer (the member-facing gate)."""
from datetime import date

import pytest

from src import live_surface as ls


TODAY = date(2026, 7, 28)


def sig(**over):
    s = {
        "id": "sig-1",
        "title": "City of Peel tender for body-worn cameras",
        "public_safety": True,
        "suppressed": False,
        "evidence_grade": 4,
        "category_slug": "body-worn-cameras",
        "organizations": {"canonical_name": "Region of Peel"},
        "documents": {
            "doc_type": "tender_notice",
            "published_on": "2026-08-10",
            "date_precision": "day",
            "url": "https://peelregion.bidsandtenders.ca/Module/Tenders/en/Tender/Preview/x",
            "reference_number": "2026-104P",
            "defence_relevant": False,
        },
    }
    docs = over.pop("documents", None)
    s.update(over)
    if docs is not None:
        s["documents"] = {**s["documents"], **docs}
    return s


def test_clean_signal_projects_with_presentation_columns_only():
    rows, rej = ls.project([sig()], TODAY)
    assert len(rows) == 1
    r = rows[0]
    assert r["signal_id"] == "sig-1"
    assert r["buyer_name"] == "Region of Peel"
    assert r["closing_on"] == "2026-08-10"
    assert r["reference_number"] == "2026-104P"
    # No operator-internal fields leak into the projection (D3).
    for banned in ("evidence_grade", "amount_max_cad", "suppressed",
                   "reviewed_by", "public_safety", "defence_relevant"):
        assert banned not in r, banned


def test_non_public_safety_is_rejected_fail_closed():
    for val in (False, None):
        rows, rej = ls.project([sig(public_safety=val)], TODAY)
        assert rows == []
        assert rej["not_public_safety"] == 1


def test_suppressed_is_rejected():
    rows, rej = ls.project([sig(suppressed=True)], TODAY)
    assert rows == [] and rej["suppressed"] == 1


def test_below_grade_is_rejected():
    rows, rej = ls.project([sig(evidence_grade=3)], TODAY)
    assert rows == [] and rej["below_grade"] == 1
    rows, rej = ls.project([sig(evidence_grade=None)], TODAY)
    assert rows == [] and rej["below_grade"] == 1


def test_wrong_doc_type_is_rejected():
    rows, rej = ls.project([sig(documents={"doc_type": "award_notice"})], TODAY)
    assert rows == [] and rej["wrong_doc_type"] == 1
    rows, rej = ls.project([sig(documents={"doc_type": "board_minutes"})], TODAY)
    assert rows == [] and rej["wrong_doc_type"] == 1


def test_past_deadline_is_out_of_window():
    rows, rej = ls.project(
        [sig(documents={"published_on": "2026-07-01"})], TODAY)
    assert rows == [] and rej["out_of_window"] == 1


def test_tender_beyond_30_days_is_out_but_grant_gets_45():
    # A tender closing in 40 days is out; a grant closing in 40 days is in.
    rows, _ = ls.project(
        [sig(documents={"published_on": "2026-09-06"})], TODAY)  # +40d
    assert rows == []
    rows, _ = ls.project([sig(
        documents={"doc_type": "grant_program", "published_on": "2026-09-06"})],
        TODAY)
    assert len(rows) == 1


def test_today_is_in_window_inclusive():
    rows, _ = ls.project(
        [sig(documents={"published_on": "2026-07-28"})], TODAY)
    assert len(rows) == 1


def test_undated_deadline_is_out_of_window():
    rows, rej = ls.project(
        [sig(documents={"published_on": None})], TODAY)
    assert rows == [] and rej["out_of_window"] == 1


def test_rows_sorted_soonest_closing_first():
    rows, _ = ls.project([
        sig(id="a", documents={"published_on": "2026-08-20"}),
        sig(id="b", documents={"published_on": "2026-07-30"}),
        sig(id="c", documents={"published_on": "2026-08-05"}),
    ], TODAY)
    assert [r["signal_id"] for r in rows] == ["b", "c", "a"]


def test_unresolved_buyer_and_defence_tag_from_document():
    rows, _ = ls.project([sig(
        organizations=None,
        documents={"defence_relevant": True})], TODAY)
    assert rows[0]["buyer_name"] is None
    # Generic shape: an open tag array, not a fixed domain boolean.
    assert rows[0]["tags"] == ["defence"]


def test_non_defence_item_carries_no_tags():
    rows, _ = ls.project([sig()], TODAY)
    assert rows[0]["tags"] == []


def test_run_raises_on_empty_slice(monkeypatch):
    monkeypatch.setattr(ls, "table_present", lambda: True)
    monkeypatch.setattr(ls.supabase_client, "fetch_all_rows_where",
                        lambda *a, **k: [sig(evidence_grade=1)])  # all rejected
    with pytest.raises(RuntimeError, match="0 rows"):
        ls.run(dry_run=True, today=TODAY)


def test_run_skips_when_table_absent(monkeypatch):
    monkeypatch.setattr(ls, "table_present", lambda: False)
    assert ls.run(dry_run=False, today=TODAY) == {"skipped": "table_absent"}


def test_run_apply_deletes_then_rewrites(monkeypatch):
    monkeypatch.setattr(ls, "table_present", lambda: True)
    monkeypatch.setattr(ls.supabase_client, "fetch_all_rows_where",
                        lambda *a, **k: [sig(), sig(id="sig-2")])
    calls = {"deleted": [], "inserted": []}
    monkeypatch.setattr(ls.supabase_client, "delete_rows",
                        lambda t, f: calls["deleted"].append((t, f)))
    monkeypatch.setattr(ls.supabase_client, "insert_row",
                        lambda t, p: calls["inserted"].append(p) or {})
    out = ls.run(dry_run=False, today=TODAY)
    assert out["rows"] == 2
    assert calls["deleted"] == [("member_live_items", {"id": "not.is.null"})]
    assert len(calls["inserted"]) == 2
    assert all("refreshed_at" in p for p in calls["inserted"])
