"""Tests for the pre-dispatch envelope guardrail.

The guard's whole value is that it BINDS. These tests hold it to the three
outcomes, and specifically to the one that matters most: an envelope whose
spend cannot be measured must RAISE, never be treated as having room.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import envelope_guard as eg


def _fake_db(monkeypatch, envelopes, spend):
    """Patch the two reads the guard makes."""
    def fetch_rows_where(table, select, filters, limit=10000, offset=0):
        assert table == eg.ENVELOPES_TABLE
        key = filters["key"].split("eq.", 1)[1]
        return [e for e in envelopes if e["key"] == key]

    def fetch_all_rows_where(table, select, filters, page_size=1000):
        assert table == eg.SPEND_TABLE
        key = filters["envelope"].split("eq.", 1)[1]
        return [s for s in spend if s["envelope"] == key]

    monkeypatch.setattr(eg.supabase_client, "fetch_rows_where", fetch_rows_where)
    monkeypatch.setattr(eg.supabase_client, "fetch_all_rows_where", fetch_all_rows_where)


OPEN_ENV = {"key": "e1", "label": "Test envelope", "declared_usd": 65.00,
            "seed_rate_usd_per_doc": 0.024, "status": "open",
            "approved_on": "2026-07-28"}


# --- PROCEED ---------------------------------------------------------------
def test_proceeds_when_batch_fits(monkeypatch):
    _fake_db(monkeypatch, [OPEN_ENV],
             [{"envelope": "e1", "cost_usd": 19.37, "documents_processed": 1000}])
    d = eg.check("e1", 200)
    assert d["proceed"] is True
    assert d["spent_usd"] == 19.37
    # rate is MEASURED from the ledger, not the seed
    assert d["rate_usd_per_doc"] == pytest.approx(0.01937)
    assert d["projected_usd"] == pytest.approx(3.87, abs=0.01)


def test_uses_seed_rate_when_no_runs_logged(monkeypatch):
    _fake_db(monkeypatch, [OPEN_ENV], [])
    d = eg.check("e1", 100)
    assert d["rate_usd_per_doc"] == pytest.approx(0.024)
    assert "seed rate" in d["rate_basis"]
    assert d["proceed"] is True


# --- SKIP ------------------------------------------------------------------
def test_skips_when_batch_would_exceed(monkeypatch):
    _fake_db(monkeypatch, [OPEN_ENV],
             [{"envelope": "e1", "cost_usd": 60.00, "documents_processed": 2500}])
    d = eg.check("e1", 1000)
    assert d["proceed"] is False
    assert d["would_total_usd"] > d["declared_usd"]
    # and it says how much room is actually left, so the cap can be lowered
    assert d["docs_affordable"] == int(5.00 / (60.00 / 2500))


def test_exact_fit_proceeds(monkeypatch):
    """<= declared proceeds; the boundary is inclusive, not off by a batch."""
    _fake_db(monkeypatch, [OPEN_ENV],
             [{"envelope": "e1", "cost_usd": 60.00, "documents_processed": 3000}])
    rate = 60.00 / 3000                       # 0.02
    d = eg.check("e1", int(5.00 / rate))      # exactly the remaining $5
    assert d["proceed"] is True


# --- UNMEASURABLE: the outcome that must never silently pass ----------------
def test_unknown_envelope_raises(monkeypatch):
    _fake_db(monkeypatch, [], [])
    with pytest.raises(eg.EnvelopeUnmeasurable, match="no envelope declared"):
        eg.check("nope", 100)


def test_unmeasured_status_raises_even_though_ledger_reads_low(monkeypatch):
    """The Toronto case: logged spend is a FLOOR, not the total. A guard that
    treats the unknown remainder as zero would re-authorize the whole
    envelope."""
    env = {**OPEN_ENV, "key": "tor", "status": "unmeasured", "declared_usd": 63.00}
    _fake_db(monkeypatch, [env],
             [{"envelope": "tor", "cost_usd": 2.00, "documents_processed": 100}])
    with pytest.raises(eg.EnvelopeUnmeasurable, match="UNMEASURED"):
        eg.check("tor", 100)


def test_closed_envelope_raises(monkeypatch):
    _fake_db(monkeypatch, [{**OPEN_ENV, "status": "closed"}], [])
    with pytest.raises(eg.EnvelopeUnmeasurable, match="CLOSED"):
        eg.check("e1", 10)


def test_zero_declared_raises(monkeypatch):
    _fake_db(monkeypatch, [{**OPEN_ENV, "declared_usd": 0}], [])
    with pytest.raises(eg.EnvelopeUnmeasurable):
        eg.check("e1", 10)


def test_no_runs_and_no_seed_rate_raises(monkeypatch):
    _fake_db(monkeypatch, [{**OPEN_ENV, "seed_rate_usd_per_doc": None}], [])
    with pytest.raises(eg.EnvelopeUnmeasurable, match="cannot be priced"):
        eg.check("e1", 10)


def test_missing_table_raises_rather_than_defaulting_to_zero(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('relation "extraction_envelopes" does not exist')
    monkeypatch.setattr(eg.supabase_client, "fetch_rows_where", boom)
    with pytest.raises(eg.EnvelopeUnmeasurable, match="cannot read"):
        eg.check("e1", 10)


def test_unreadable_spend_table_raises(monkeypatch):
    def ok(table, select, filters, limit=10000, offset=0):
        return [OPEN_ENV]

    def boom(*a, **k):
        raise RuntimeError("permission denied")
    monkeypatch.setattr(eg.supabase_client, "fetch_rows_where", ok)
    monkeypatch.setattr(eg.supabase_client, "fetch_all_rows_where", boom)
    with pytest.raises(eg.EnvelopeUnmeasurable, match="unknown is not zero"):
        eg.check("e1", 10)


# --- cost arithmetic -------------------------------------------------------
def test_cost_usd_prices_all_four_token_classes():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000,
             "cache_write_tokens": 1_000_000, "cache_read_tokens": 1_000_000}
    # 5.00 + 25.00 + 6.25 + 0.50
    assert eg.cost_usd(usage, "claude-opus-4-8") == pytest.approx(36.75)


def test_unknown_model_falls_back_to_the_default_rate_card():
    usage = {"input_tokens": 1_000_000}
    assert eg.cost_usd(usage, "some-future-model") == pytest.approx(5.00)
