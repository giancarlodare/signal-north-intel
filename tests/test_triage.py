"""Tests for review triage: three outcomes (auto_approve / auto_reject / flag)
and the apply path.

Auto-approve: structured search.open.canada.ca source AND confidence=confirmed
AND org resolved AND not high-stakes. Auto-reject (AR1): the conservative
bottom-of-every-axis noise rule -- materiality 1 AND speculative AND no amount
AND not defence-tagged. Everything else flags. Every automated outcome stamps
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


# --- classify() two-way gate (retained) --------------------------------------
def test_clean_structured_confirmed_low_stakes_auto_approves():
    assert triage.classify(_sig(), DISCLOSURE) == "auto_approve"
    assert triage.gate_failures(_sig(), DISCLOSURE) == []


def test_non_structured_source_is_manual():
    assert triage.classify(_sig(), NEWS) == "manual"
    assert "not_structured_source" in triage.gate_failures(_sig(), NEWS)


def test_canadabuys_is_not_structured():
    assert triage.is_structured_disclosure(CANADABUYS) is False
    assert triage.classify(_sig(), CANADABUYS) == "manual"


def test_high_materiality_and_amount_gate_auto_approve():
    assert triage.classify(_sig(materiality=4), DISCLOSURE) == "manual"
    assert triage.classify(_sig(amount=1_000_000), DISCLOSURE) == "manual"
    assert triage.classify(_sig(amount=999_999.99), DISCLOSURE) == "auto_approve"


# --- AR1 auto-reject: conservative, all four conditions AND-ed ----------------
def test_ar1_fires_only_on_bottom_of_every_axis():
    s = _sig(confidence="speculative", materiality=1, amount=None)
    assert triage.auto_reject_reason(s, defence_relevant=False) == "AR1"
    assert triage.auto_reject_reason(s, defence_relevant=None) == "AR1"


def test_ar1_spares_defence_tagged_signals():
    # defence_relevant only ever spares; it never causes a rejection.
    s = _sig(confidence="speculative", materiality=1, amount=None)
    assert triage.auto_reject_reason(s, defence_relevant=True) is None


def test_ar1_needs_all_four_conditions():
    # Strong on any single axis -> survives to a human (not auto-rejected).
    assert triage.auto_reject_reason(
        _sig(confidence="probable", materiality=1, amount=None), False) is None   # confidence
    assert triage.auto_reject_reason(
        _sig(confidence="speculative", materiality=2, amount=None), False) is None  # materiality
    assert triage.auto_reject_reason(
        _sig(confidence="speculative", materiality=1, amount=5000), False) is None  # has amount


# --- decide(): three outcomes and their precedence ---------------------------
def test_decide_auto_approve_beats_everything():
    assert triage.decide(_sig(), DISCLOSURE, None)[0] == "auto_approve"


def test_decide_auto_reject_for_ar1_noise():
    s = _sig(confidence="speculative", materiality=1, amount=None)
    assert triage.decide(s, NEWS, False) == ("auto_reject", "AR1")


def test_decide_flags_the_uncertain_middle():
    # Probable CanadaBuys award, M2: not clean, not noise -> a human decides.
    s = _sig(confidence="probable", materiality=2, amount=None)
    assert triage.decide(s, CANADABUYS, False)[0] == "flag"


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


def _row(sid, source_id, doc_type="award_notice", defence=None, **kw):
    s = _sig(**kw)
    s["id"] = sid
    s["documents"] = {"doc_type": doc_type, "source_id": source_id,
                      "defence_relevant": defence}
    return s


def test_apply_writes_both_automated_outcomes_and_flags_the_rest(monkeypatch):
    db = _FakeDB(
        signals=[
            _row("clean", "src-disc"),                                   # auto_approve
            _row("noise", "src-news", confidence="speculative",
                 materiality=1, amount=None, defence=False),             # auto_reject AR1
            _row("uncertain", "src-news", confidence="probable",
                 materiality=2),                                         # flag
        ],
        sources=[{"id": "src-disc", "url": DISCLOSURE},
                 {"id": "src-news", "url": NEWS}])
    _wire(monkeypatch, db)
    result = triage.run(dry_run=False)

    assert result["auto_approve"] == 1 and result["approved"] == 1
    assert result["auto_reject"] == 1 and result["rejected"] == 1
    assert result["flag"] == 1
    # Exactly the two automated rows were written; the flagged one was not.
    written = {rid: payload for (_t, rid, payload) in db.updates}
    assert set(written) == {"clean", "noise"}
    assert written["clean"] == {"reviewed": True, "review_note": "approved",
                                "reviewed_by": "triage@v1"}
    assert written["noise"]["reviewed_by"] == "triage@v1"
    assert written["noise"]["review_note"].startswith("rejected:")


def test_apply_only_touches_signals_never_the_ledger(monkeypatch):
    db = _FakeDB(
        signals=[_row("clean", "src-disc"),
                 _row("noise", "src-news", confidence="speculative",
                      materiality=1, amount=None)],
        sources=[{"id": "src-disc", "url": DISCLOSURE},
                 {"id": "src-news", "url": NEWS}])
    _wire(monkeypatch, db)
    triage.run(dry_run=False)
    assert {t for (t, _, _) in db.updates} == {"signals"}


def test_dry_run_writes_nothing(monkeypatch):
    db = _FakeDB(
        signals=[_row("clean", "src-disc"),
                 _row("noise", "src-news", confidence="speculative",
                      materiality=1, amount=None)],
        sources=[{"id": "src-disc", "url": DISCLOSURE},
                 {"id": "src-news", "url": NEWS}])
    _wire(monkeypatch, db)
    result = triage.run(dry_run=True)
    assert db.updates == []
    assert result["approved"] == 0 and result["rejected"] == 0
    assert result["auto_approve"] == 1 and result["auto_reject"] == 1
