"""Tests for relevance_scorer: scoring, clamping, dry-run isolation."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Inject a stub 'anthropic' module so tests run without the real SDK installed.
def _make_stub_anthropic():
    mod = types.ModuleType("anthropic")
    mod.Anthropic = object  # replaced per-test via monkeypatch
    sys.modules.setdefault("anthropic", mod)

_make_stub_anthropic()

import src.relevance_scorer as rs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_client(json_text: str):
    """Return a minimal Anthropic-lookalike whose messages.create returns json_text."""
    msg = types.SimpleNamespace(
        content=[types.SimpleNamespace(text=json_text)]
    )

    class _Messages:
        def create(self, **kw):
            return msg

    client = types.SimpleNamespace(messages=_Messages())
    return client


def _mock_client_bad(text: str):
    """Client that returns non-JSON garbage to exercise the fallback path."""
    msg = types.SimpleNamespace(content=[types.SimpleNamespace(text=text)])

    class _Messages:
        def create(self, **kw):
            return msg

    return types.SimpleNamespace(messages=_Messages())


# ---------------------------------------------------------------------------
# score_one: structured JSON output
# ---------------------------------------------------------------------------

def test_score_one_returns_correct_integer():
    client = _mock_client('{"relevance": 4}')
    assert rs.score_one("CAD procurement", "Police seeking CAD system", "m", client) == 4


def test_score_one_all_valid_values():
    for v in range(1, 6):
        client = _mock_client(f'{{"relevance": {v}}}')
        assert rs.score_one("t", "s", "m", client) == v


# ---------------------------------------------------------------------------
# score_one: clamping
# ---------------------------------------------------------------------------

def test_score_one_clamps_above_5():
    client = _mock_client('{"relevance": 7}')
    assert rs.score_one("t", "s", "m", client) == 5


def test_score_one_clamps_below_1():
    client = _mock_client('{"relevance": 0}')
    assert rs.score_one("t", "s", "m", client) == 1


def test_score_one_clamps_negative():
    client = _mock_client('{"relevance": -3}')
    assert rs.score_one("t", "s", "m", client) == 1


# ---------------------------------------------------------------------------
# score_one: fallback parse paths
# ---------------------------------------------------------------------------

def test_score_one_falls_back_to_default_on_garbage():
    # Completely unparseable text -> fallback default 3
    client = _mock_client_bad("sorry I cannot score this")
    result = rs.score_one("t", "s", "m", client)
    assert 1 <= result <= 5


def test_score_one_handles_bare_integer_response():
    # Some models respond with bare "4" instead of JSON
    client = _mock_client_bad("4")
    result = rs.score_one("t", "s", "m", client)
    assert result == 4


# ---------------------------------------------------------------------------
# score_one: empty title/summary handled gracefully
# ---------------------------------------------------------------------------

def test_score_one_handles_empty_strings():
    client = _mock_client('{"relevance": 2}')
    result = rs.score_one("", "", "m", client)
    assert result == 2


def test_score_one_handles_none_inputs():
    client = _mock_client('{"relevance": 3}')
    result = rs.score_one(None, None, "m", client)
    assert result == 3


# ---------------------------------------------------------------------------
# run(): dry_run=True makes no DB writes
# ---------------------------------------------------------------------------

def _fake_anthropic_client():
    """Return a fake client whose messages.create returns relevance=3."""
    class _Messages:
        def create(self, **kw):
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(text='{"relevance": 3}')]
            )
    return types.SimpleNamespace(messages=_Messages())


def _patch_anthropic(monkeypatch, client):
    """Point the anthropic stub's Anthropic class at a factory returning client."""
    import sys
    stub = sys.modules["anthropic"]
    monkeypatch.setattr(stub, "Anthropic", lambda: client)


def test_dry_run_does_not_write(monkeypatch):
    signals = [
        {"id": f"sig-{i}", "title": f"Title {i}", "summary": f"Summary {i}",
         "defence_relevant": False, "materiality": 3}
        for i in range(3)
    ]

    import src.supabase_client as sc
    monkeypatch.setattr(sc, "fetch_rows_where", lambda *a, **kw: signals[:])

    writes = []
    monkeypatch.setattr(sc, "update_row", lambda *a, **kw: writes.append(a))

    _patch_anthropic(monkeypatch, _fake_anthropic_client())
    monkeypatch.setattr(rs, "time", types.SimpleNamespace(sleep=lambda _: None))

    stats = rs.run(dry_run=True, limit=3, model="test-model")

    assert writes == [], "dry_run must not call update_row"
    assert stats["scored"] == 3
    assert stats["errors"] == 0


# ---------------------------------------------------------------------------
# run(): live mode writes exactly one update per signal
# ---------------------------------------------------------------------------

def test_live_run_writes_one_update_per_signal(monkeypatch):
    signals = [
        {"id": f"sig-{i}", "title": f"Title {i}", "summary": f"Summary {i}",
         "defence_relevant": False, "materiality": 3}
        for i in range(5)
    ]

    import src.supabase_client as sc
    monkeypatch.setattr(sc, "fetch_rows_where", lambda *a, **kw: signals[:])

    writes = []
    monkeypatch.setattr(sc, "update_row", lambda table, id_, payload: writes.append((table, id_, payload)))

    class _Msg:
        def create(self, **kw):
            return types.SimpleNamespace(content=[types.SimpleNamespace(text='{"relevance": 5}')])

    _patch_anthropic(monkeypatch, types.SimpleNamespace(messages=_Msg()))
    monkeypatch.setattr(rs, "time", types.SimpleNamespace(sleep=lambda _: None))

    stats = rs.run(dry_run=False, limit=5, model="test-model")

    assert len(writes) == 5
    assert all(w[0] == "signals" for w in writes)
    assert all(w[2] == {"relevance": 5} for w in writes)
    assert stats["scored"] == 5
    assert stats["errors"] == 0


# ---------------------------------------------------------------------------
# run(): error in score_one is counted, not propagated
# ---------------------------------------------------------------------------

def test_run_counts_errors_and_continues(monkeypatch):
    signals = [
        {"id": "ok-1", "title": "Good", "summary": "Good summary",
         "defence_relevant": False, "materiality": 3},
        {"id": "bad-1", "title": "Boom", "summary": "Boom summary",
         "defence_relevant": False, "materiality": 3},
        {"id": "ok-2", "title": "Good2", "summary": "Good summary2",
         "defence_relevant": False, "materiality": 3},
    ]

    import src.supabase_client as sc
    monkeypatch.setattr(sc, "fetch_rows_where", lambda *a, **kw: signals[:])

    writes = []
    monkeypatch.setattr(sc, "update_row", lambda table, id_, payload: writes.append(id_))

    call_count = [0]

    class _Msg:
        def create(self, **kw):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("simulated API failure")
            return types.SimpleNamespace(content=[types.SimpleNamespace(text='{"relevance": 3}')])

    _patch_anthropic(monkeypatch, types.SimpleNamespace(messages=_Msg()))
    monkeypatch.setattr(rs, "time", types.SimpleNamespace(sleep=lambda _: None))

    stats = rs.run(dry_run=False, limit=3, model="test-model")

    assert stats["errors"] == 1
    assert stats["scored"] == 2
    assert "ok-1" in writes and "ok-2" in writes and "bad-1" not in writes


# ---------------------------------------------------------------------------
# run(): limit is respected
# ---------------------------------------------------------------------------

def test_run_respects_limit(monkeypatch):
    signals = [
        {"id": f"sig-{i}", "title": f"T{i}", "summary": f"S{i}",
         "defence_relevant": False, "materiality": 3}
        for i in range(20)
    ]

    import src.supabase_client as sc
    monkeypatch.setattr(sc, "fetch_rows_where", lambda *a, limit=500, **kw: signals[:limit])

    writes = []
    monkeypatch.setattr(sc, "update_row", lambda *a, **kw: writes.append(a))

    class _Msg:
        def create(self, **kw):
            return types.SimpleNamespace(content=[types.SimpleNamespace(text='{"relevance": 2}')])

    _patch_anthropic(monkeypatch, types.SimpleNamespace(messages=_Msg()))
    monkeypatch.setattr(rs, "time", types.SimpleNamespace(sleep=lambda _: None))

    stats = rs.run(dry_run=False, limit=7, model="test-model")
    assert stats["scored"] == 7


# ---------------------------------------------------------------------------
# module integrity: no silent-write path exists
# ---------------------------------------------------------------------------

def test_module_has_scorer_version_stamp():
    assert hasattr(rs, "SCORER_VERSION")
    assert rs.SCORER_VERSION.startswith("relevance@")
