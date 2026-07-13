"""Tests for corpus-hygiene triage: AR1 noise suppression.

Under the editorial model there is no approval gate; triage's only job is to
suppress obvious noise (AR1) from the live corpus. AR1 fires only when a signal
is weakest on every axis at once: materiality 1 AND speculative AND no amount
AND not defence-tagged. Suppression stamps suppressed_by='triage@v1'; the wall
to the ledger is absolute.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import triage


def _sig(confidence="speculative", materiality=1, amount=None):
    return {"id": "s1", "confidence": confidence, "materiality": materiality,
            "amount_max_cad": amount}


# --- is_ar1_noise: conservative, all four conditions AND-ed -------------------
def test_ar1_fires_on_bottom_of_every_axis():
    assert triage.is_ar1_noise(_sig(), defence_relevant=False) is True
    assert triage.is_ar1_noise(_sig(), defence_relevant=None) is True


def test_ar1_spares_defence_tagged_signals():
    # defence_relevant only ever spares; it never causes a suppression.
    assert triage.is_ar1_noise(_sig(), defence_relevant=True) is False


def test_ar1_needs_all_four_conditions():
    assert triage.is_ar1_noise(_sig(confidence="probable"), False) is False   # confidence
    assert triage.is_ar1_noise(_sig(materiality=2), False) is False           # materiality
    assert triage.is_ar1_noise(_sig(amount=5000), False) is False             # has amount


def test_ar1_defaults_bad_materiality_safely():
    # Non-numeric materiality falls back to 3 (not AR1), so a junk value never
    # causes an over-eager suppression.
    s = {"id": "s", "confidence": "speculative", "materiality": "n/a",
         "amount_max_cad": None}
    assert triage.is_ar1_noise(s, False) is False


# --- run() apply path, with a fake supabase_client ---------------------------
class _FakeDB:
    def __init__(self, signals):
        self._signals = signals
        self.updates = []   # (table, id, payload)

    def fetch_all_rows_where(self, table, select, filters):
        assert table == "signals"
        # Triage reads only the LIVE corpus (never re-touches suppressed rows).
        assert filters == {"suppressed": "is.false"}
        return self._signals

    def update_row(self, table, row_id, payload):
        self.updates.append((table, row_id, payload))


def _wire(monkeypatch, db):
    monkeypatch.setattr(triage.supabase_client, "fetch_all_rows_where",
                        db.fetch_all_rows_where)
    monkeypatch.setattr(triage.supabase_client, "update_row", db.update_row)


def _row(sid, doc_type="award_notice", defence=None, **kw):
    s = _sig(**kw)
    s["id"] = sid
    s["documents"] = {"doc_type": doc_type, "defence_relevant": defence}
    return s


def test_apply_suppresses_only_ar1_noise(monkeypatch):
    db = _FakeDB(signals=[
        _row("noise"),                                       # AR1 -> suppress
        _row("strong", confidence="confirmed", materiality=4),  # kept
        _row("defence", defence=True),                        # spared -> kept
        _row("valued", amount=250000),                        # kept
    ])
    _wire(monkeypatch, db)
    result = triage.run(dry_run=False)

    assert result["suppress"] == 1 and result["suppressed"] == 1
    assert result["kept"] == 3
    assert len(db.updates) == 1
    table, rid, payload = db.updates[0]
    assert table == "signals" and rid == "noise"
    assert payload == {"suppressed": True, "suppressed_reason": "AR1",
                       "suppressed_by": "triage@v1"}


def test_apply_only_touches_signals_never_the_ledger(monkeypatch):
    db = _FakeDB(signals=[_row("noise"), _row("noise2")])
    _wire(monkeypatch, db)
    triage.run(dry_run=False)
    assert {t for (t, _, _) in db.updates} == {"signals"}


def test_dry_run_writes_nothing(monkeypatch):
    db = _FakeDB(signals=[_row("noise")])
    _wire(monkeypatch, db)
    result = triage.run(dry_run=True)
    assert db.updates == []
    assert result["suppress"] == 1 and result["suppressed"] == 0
