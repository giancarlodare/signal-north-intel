"""Tests for OpenTimestamps anchoring (Phase B). The OTS stamp call is mocked
(the real API is verified in CI); these lock the run() write/idempotency logic."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import anchor


class _FakeDB:
    def __init__(self, predictions, anchors):
        self.predictions = predictions
        self.anchors = anchors
        self.inserted = []

    def fetch_all_rows_where(self, table, select, filters):
        if table == "predictions":
            return self.predictions
        if table == "prediction_anchors":
            return self.anchors
        return []

    def insert_row(self, table, payload):
        self.inserted.append(payload)
        return {"id": "new"}


def _wire(monkeypatch, db, stamp=lambda h: (b"proofbytes", 3)):
    monkeypatch.setattr(anchor.supabase_client, "fetch_all_rows_where", db.fetch_all_rows_where)
    monkeypatch.setattr(anchor.supabase_client, "insert_row", db.insert_row)
    monkeypatch.setattr(anchor, "stamp_hash", stamp)


def test_anchors_unanchored_predictions(monkeypatch):
    db = _FakeDB(predictions=[{"id": "p1", "claim_hash": "abc123"}], anchors=[])
    _wire(monkeypatch, db)
    assert anchor.run(dry_run=False) == 0
    assert len(db.inserted) == 1
    row = db.inserted[0]
    assert row["prediction_id"] == "p1"
    assert row["anchor_type"] == "opentimestamps"
    assert row["claim_hash"] == "abc123"
    assert row["anchor_ref"] == b"proofbytes".hex()


def test_skips_already_anchored(monkeypatch):
    db = _FakeDB(
        predictions=[{"id": "p1", "claim_hash": "h1"}, {"id": "p2", "claim_hash": "h2"}],
        anchors=[{"prediction_id": "p1", "anchor_type": "opentimestamps"}])
    _wire(monkeypatch, db)
    anchor.run(dry_run=False)
    assert [r["prediction_id"] for r in db.inserted] == ["p2"]


def test_a_non_ots_anchor_does_not_count_as_anchored(monkeypatch):
    """A git-commit anchor (say) does not satisfy the OTS anchoring pass."""
    db = _FakeDB(predictions=[{"id": "p1", "claim_hash": "h1"}],
                 anchors=[{"prediction_id": "p1", "anchor_type": "git_commit"}])
    _wire(monkeypatch, db)
    anchor.run(dry_run=False)
    assert len(db.inserted) == 1


def test_dry_run_writes_nothing(monkeypatch):
    db = _FakeDB(predictions=[{"id": "p1", "claim_hash": "h1"}], anchors=[])
    _wire(monkeypatch, db)
    anchor.run(dry_run=True)
    assert db.inserted == []


def test_a_failed_stamp_records_no_anchor(monkeypatch):
    def boom(_h):
        raise RuntimeError("all calendars down")
    db = _FakeDB(predictions=[{"id": "p1", "claim_hash": "h1"}], anchors=[])
    _wire(monkeypatch, db, stamp=boom)
    rc = anchor.run(dry_run=False)
    assert db.inserted == []   # never a bogus anchor
    assert rc == 1             # the error is surfaced
