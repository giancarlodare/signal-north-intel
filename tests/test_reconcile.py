"""Tests for the reconciliation decision (Phase B, propose-only)."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import reconcile as rc


def _pred(predicted_rung=4, made_at="2026-01-01T00:00:00Z",
          horizon_ends_on="2026-10-01", kind="procurement"):
    return {"id": "p1", "subject_kind": kind, "predicted_rung": predicted_rung,
            "made_at": made_at, "horizon_ends_on": horizon_ends_on,
            "subject_procurement_id": "proc-1"}


def _sig(grade, published_on, doc_id="d1"):
    return {"evidence_grade": grade, "published_on": published_on, "document_id": doc_id}


TODAY = date(2026, 11, 1)   # after the sample horizon


def test_correct_when_predicted_rung_reached_in_window():
    pred = _pred(predicted_rung=4)
    sigs = [_sig(2, "2026-03-01"),          # too weak
            _sig(4, "2026-05-01", "d-win")]  # reaches in_market inside the window
    assert rc.decide_outcome(pred, sigs, TODAY) == ("correct", "d-win", "2026-05-01")


def test_correct_picks_earliest_settling_for_honest_lead_time():
    pred = _pred(predicted_rung=4)
    sigs = [_sig(5, "2026-06-01", "d-late"),
            _sig(4, "2026-04-01", "d-early")]
    assert rc.decide_outcome(pred, sigs, TODAY) == ("correct", "d-early", "2026-04-01")


def test_a_weaker_rung_never_settles_a_claim():
    """Q4: a claim predicting in_market (4) is not settled by a commitment (3)
    signal, and never by chatter/intent."""
    pred = _pred(predicted_rung=4)
    sigs = [_sig(3, "2026-05-01"), _sig(2, "2026-05-02"), _sig(1, "2026-05-03")]
    # horizon not yet passed as of a mid-window date -> still open
    assert rc.decide_outcome(pred, sigs, date(2026, 6, 1)) is None


def test_evidence_outside_the_window_does_not_settle():
    pred = _pred(predicted_rung=4, made_at="2026-01-01T00:00:00Z",
                 horizon_ends_on="2026-10-01")
    sigs = [_sig(5, "2025-12-01"),          # before made_at
            _sig(5, "2026-10-15")]          # after horizon end
    # both out of window; horizon passed as of TODAY -> expired
    assert rc.decide_outcome(pred, sigs, TODAY) == ("expired", None, None)


def test_expired_when_horizon_passed_with_no_settling_evidence():
    pred = _pred(horizon_ends_on="2026-10-01")
    assert rc.decide_outcome(pred, [], TODAY) == ("expired", None, None)


def test_still_open_before_horizon_with_no_evidence():
    pred = _pred(horizon_ends_on="2026-10-01")
    assert rc.decide_outcome(pred, [], date(2026, 6, 1)) is None


def test_expiry_is_never_auto_incorrect():
    """The auto-state for a lapsed claim is 'expired', never 'incorrect'
    (a human decides incorrect)."""
    outcome, _, _ = rc.decide_outcome(_pred(horizon_ends_on="2026-10-01"), [], TODAY)
    assert outcome == "expired"


# --- run()-level idempotency and closure, with a fake supabase_client --------
class _FakeDB:
    def __init__(self, predictions, subject_signals, outcomes):
        self.predictions = predictions
        self.subject_signals = subject_signals   # keyed by procurement id
        self.outcomes = outcomes                 # keyed by prediction id
        self.inserted = []

    def fetch_all_rows_where(self, table, select, filters):
        if table == "predictions":
            return self.predictions
        if table == "prediction_outcomes":
            pid = filters["prediction_id"].split(".", 1)[1]
            return self.outcomes.get(pid, [])
        if table == "procurement_signals":
            pid = filters["procurement_id"].split(".", 1)[1]
            return [{"active": True,
                     "signals": {"evidence_grade": s["evidence_grade"],
                                 "documents": {"id": s["document_id"],
                                               "published_on": s["published_on"]}}}
                    for s in self.subject_signals.get(pid, [])]
        return []

    def insert_row(self, table, payload):
        self.inserted.append(payload)
        return {"id": "new"}


def _wire(monkeypatch, db):
    monkeypatch.setattr(rc.supabase_client, "fetch_all_rows_where", db.fetch_all_rows_where)
    monkeypatch.setattr(rc.supabase_client, "insert_row", db.insert_row)
    monkeypatch.setattr(rc, "date", type("D", (), {"today": staticmethod(lambda: TODAY)}))


def test_run_proposes_correct_and_expired(monkeypatch):
    db = _FakeDB(
        predictions=[
            _pred() | {"id": "settleable", "subject_procurement_id": "pc-win"},
            _pred() | {"id": "lapsed", "subject_procurement_id": "pc-none"},
        ],
        subject_signals={"pc-win": [_sig(4, "2026-05-01", "d-win")], "pc-none": []},
        outcomes={})
    _wire(monkeypatch, db)
    assert rc.run(dry_run=False) == 0
    by_pred = {o["prediction_id"]: o for o in db.inserted}
    assert by_pred["settleable"]["outcome"] == "correct"
    assert by_pred["settleable"]["settling_document_id"] == "d-win"
    # lead-time freeze: the settling event date is snapshotted at proposal
    assert by_pred["settleable"]["settling_published_on"] == "2026-05-01"
    assert by_pred["settleable"]["status"] == "proposed"
    assert by_pred["lapsed"]["outcome"] == "expired"


def test_run_skips_confirmed_and_already_proposed(monkeypatch):
    db = _FakeDB(
        predictions=[
            _pred() | {"id": "closed", "subject_procurement_id": "pc-win"},
            _pred() | {"id": "already", "subject_procurement_id": "pc-none"},
        ],
        subject_signals={"pc-win": [_sig(4, "2026-05-01")], "pc-none": []},
        outcomes={
            "closed": [{"outcome": "correct", "status": "confirmed"}],
            "already": [{"outcome": "expired", "status": "proposed"}],
        })
    _wire(monkeypatch, db)
    rc.run(dry_run=False)
    assert db.inserted == []   # one closed, one already-proposed -> nothing new


def test_run_dry_run_writes_nothing(monkeypatch):
    db = _FakeDB(predictions=[_pred() | {"subject_procurement_id": "pc-win"}],
                 subject_signals={"pc-win": [_sig(4, "2026-05-01")]}, outcomes={})
    _wire(monkeypatch, db)
    rc.run(dry_run=True)
    assert db.inserted == []
