"""Tests for review triage: the auto-approve rules and the apply path.

The rules (operator-approved 2026-07-13): auto-approve iff the signal comes
from a search.open.canada.ca proactive-disclosure source AND confidence is
confirmed AND the org is resolved AND it is not high-stakes (materiality < 4 and
amount < $1M). Everything else stays manual. Auto-approvals stamp
reviewed_by='triage@v1'; the wall to the ledger is absolute.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import triage

DISCLOSURE = "https://search.open.canada.ca/contracts/?owner_org=dnd-mdn"
CANADABUYS = "https://canadabuys.canada.ca/en/tender-opportunities/123"
NEWS = "https://www.ontario.ca/newsroom/example"


def _sig(confidence="confirmed", materiality=3, needs_org=False, amount=None):
    return {"id": "s1", "confidence": confidence, "materiality": materiality,
            "needs_org_resolution": needs_org, "amount_max_cad": amount}


# --- classify() rule matrix --------------------------------------------------
def test_clean_structured_confirmed_low_stakes_auto_approves():
    assert triage.classify(_sig(), DISCLOSURE) == "auto_approve"
    assert triage.gate_failures(_sig(), DISCLOSURE) == []


def test_non_structured_source_is_manual():
    assert triage.classify(_sig(), NEWS) == "manual"
    assert "not_structured_source" in triage.gate_failures(_sig(), NEWS)


def test_canadabuys_is_not_structured():
    # CanadaBuys is a distinct source class the operator keeps eyes on.
    assert triage.is_structured_disclosure(CANADABUYS) is False
    assert triage.classify(_sig(), CANADABUYS) == "manual"


def test_unconfirmed_confidence_is_manual():
    assert triage.classify(_sig(confidence="probable"), DISCLOSURE) == "manual"
    assert triage.classify(_sig(confidence="speculative"), DISCLOSURE) == "manual"
    assert "confidence_probable" in triage.gate_failures(
        _sig(confidence="probable"), DISCLOSURE)


def test_needs_org_resolution_is_manual():
    fails = triage.gate_failures(_sig(needs_org=True), DISCLOSURE)
    assert "needs_org_resolution" in fails
    assert triage.classify(_sig(needs_org=True), DISCLOSURE) == "manual"


def test_high_materiality_is_manual():
    assert triage.classify(_sig(materiality=4), DISCLOSURE) == "manual"
    assert "materiality_ge_4" in triage.gate_failures(_sig(materiality=4), DISCLOSURE)


def test_amount_at_or_above_1M_is_manual():
    assert triage.classify(_sig(amount=1_000_000), DISCLOSURE) == "manual"
    assert triage.classify(_sig(amount=5_000_000), DISCLOSURE) == "manual"
    assert "amount_ge_1M" in triage.gate_failures(_sig(amount=1_000_000), DISCLOSURE)


def test_amount_just_under_1M_still_auto_approves():
    assert triage.classify(_sig(amount=999_999.99), DISCLOSURE) == "auto_approve"


def test_multiple_failures_counted_independently():
    fails = triage.gate_failures(
        _sig(confidence="probable", needs_org=True, amount=2_000_000), NEWS)
    assert set(fails) >= {
        "not_structured_source", "confidence_probable",
        "needs_org_resolution", "amount_ge_1M"}


def test_bad_materiality_and_amount_values_default_safely():
    # Non-numeric materiality falls back to 3 (not high); bad amount to None.
    s = {"id": "s", "confidence": "confirmed", "materiality": "n/a",
         "needs_org_resolution": False, "amount_max_cad": "n/a"}
    assert triage.classify(s, DISCLOSURE) == "auto_approve"


# --- run() apply path, with a fake supabase_client ---------------------------
class _FakeDB:
    def __init__(self, signals, sources):
        self._signals = signals
        self._sources = sources
        self.updates = []   # (table, id, payload)

    def fetch_all_rows_where(self, table, select, filters):
        assert table == "signals"
        assert filters == {"reviewed": "is.false"}
        return self._signals

    def fetch_rows(self, table, select, limit=10000):
        assert table == "sources"
        return self._sources

    def update_row(self, table, row_id, payload):
        self.updates.append((table, row_id, payload))


def _wire(monkeypatch, db):
    monkeypatch.setattr(triage.supabase_client, "fetch_all_rows_where",
                        db.fetch_all_rows_where)
    monkeypatch.setattr(triage.supabase_client, "fetch_rows", db.fetch_rows)
    monkeypatch.setattr(triage.supabase_client, "update_row", db.update_row)


def _row(sid, source_id, doc_type="award_notice", **kw):
    s = _sig(**kw)
    s["id"] = sid
    s["documents"] = {"doc_type": doc_type, "source_id": source_id}
    return s


def test_apply_approves_only_the_clean_structured_set(monkeypatch):
    db = _FakeDB(
        signals=[
            _row("clean", "src-disc"),                       # auto
            _row("news", "src-news"),                        # manual: source
            _row("probable", "src-disc", confidence="probable"),  # manual: conf
            _row("big", "src-disc", amount=2_000_000),       # manual: stakes
        ],
        sources=[{"id": "src-disc", "url": DISCLOSURE},
                 {"id": "src-news", "url": NEWS}])
    _wire(monkeypatch, db)
    result = triage.run(dry_run=False)

    assert result["auto"] == 1 and result["approved"] == 1
    assert result["manual"] == 3
    # Exactly the clean signal was written, exactly once, to the signals table.
    assert len(db.updates) == 1
    table, rid, payload = db.updates[0]
    assert table == "signals" and rid == "clean"
    assert payload == {"reviewed": True, "review_note": "approved",
                       "reviewed_by": "triage@v1"}


def test_apply_never_touches_the_ledger(monkeypatch):
    # The wall: triage writes ONLY to signals, never predictions/procurements.
    db = _FakeDB(
        signals=[_row("clean", "src-disc"), _row("clean2", "src-disc")],
        sources=[{"id": "src-disc", "url": DISCLOSURE}])
    _wire(monkeypatch, db)
    triage.run(dry_run=False)
    assert {t for (t, _, _) in db.updates} == {"signals"}


def test_dry_run_writes_nothing(monkeypatch):
    db = _FakeDB(
        signals=[_row("clean", "src-disc")],
        sources=[{"id": "src-disc", "url": DISCLOSURE}])
    _wire(monkeypatch, db)
    result = triage.run(dry_run=True)
    assert db.updates == []
    assert result["auto"] == 1 and result["approved"] == 0
