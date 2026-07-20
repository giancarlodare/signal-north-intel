"""Regression tests for issue #74: find_or_create_vendor must actually find a
repeat vendor (the quoted-ilike lookup silently never matched, so every repeat
vendor's award linked vendor_id=None), and the relink backfill must patch
exactly the rows that were left unlinked."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import relink_vendors, supabase_client


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _patch_request(monkeypatch, handler, calls):
    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs.get("params") or {}))
        return _Resp(handler(method, path, kwargs))
    monkeypatch.setattr(supabase_client, "_request", fake_request)
    monkeypatch.setattr(supabase_client, "_headers", lambda prefer=None: {})


def test_repeat_vendor_is_found_with_eq_not_quoted_ilike(monkeypatch):
    calls = []

    def handler(method, path, kwargs):
        params = kwargs.get("params") or {}
        if method == "GET" and params.get("canonical_name") == "eq.Acme Corp. (Canada), Ltd.":
            return [{"id": "v1"}]
        return []
    _patch_request(monkeypatch, handler, calls)

    vid = supabase_client.find_or_create_vendor("Acme Corp. (Canada),  Ltd.")
    assert vid == "v1"
    # The lookup must be eq (a quoted ilike value is matched literally by
    # PostgREST and never hits), and no insert may happen on a hit.
    assert all(m == "GET" for m, _, _ in calls)
    assert calls[0][2]["canonical_name"].startswith("eq.")


def test_lost_insert_race_refetches_instead_of_returning_none(monkeypatch):
    # Lookup misses, ignore-duplicates insert returns an empty body (duplicate
    # created concurrently): the function must re-fetch, never return None.
    calls = []
    state = {"gets": 0}

    def handler(method, path, kwargs):
        if method == "POST":
            return []            # ignored duplicate: empty body
        state["gets"] += 1
        if state["gets"] >= 3:   # first two lookups miss; the re-fetch hits
            return [{"id": "v9"}]
        return []
    _patch_request(monkeypatch, handler, calls)

    assert supabase_client.find_or_create_vendor("Repeat Vendor Inc.") == "v9"


def test_relink_backfill_patches_only_unlinked_rows(monkeypatch):
    rows = [{"id": "a1", "vendor_name": "Acme  Corp."},
            {"id": "a2", "vendor_name": "Acme Corp."},
            {"id": "a3", "vendor_name": "  "}]
    patched = []
    monkeypatch.setattr(relink_vendors.supabase_client, "fetch_all_rows_where",
                        lambda *a, **k: rows)
    monkeypatch.setattr(relink_vendors.supabase_client, "find_or_create_vendor",
                        lambda name: "v1" if name == "Acme Corp." else None)
    monkeypatch.setattr(relink_vendors.supabase_client, "update_row",
                        lambda table, rid, payload: patched.append((table, rid, payload)))

    stats = relink_vendors.run(dry_run=False)
    # Both Acme rows link to the same vendor (whitespace-normalized once);
    # the blank name is counted unlinkable, never written.
    assert stats == {"rows": 3, "distinct_names": 1, "linked": 2, "unlinkable": 1}
    assert patched == [("contract_awards", "a1", {"vendor_id": "v1"}),
                       ("contract_awards", "a2", {"vendor_id": "v1"})]


def test_relink_dry_run_writes_nothing(monkeypatch):
    monkeypatch.setattr(relink_vendors.supabase_client, "fetch_all_rows_where",
                        lambda *a, **k: [{"id": "a1", "vendor_name": "X Inc."}])

    def boom(*a, **k):
        raise AssertionError("dry-run must not write or resolve vendors")
    monkeypatch.setattr(relink_vendors.supabase_client, "find_or_create_vendor", boom)
    monkeypatch.setattr(relink_vendors.supabase_client, "update_row", boom)

    stats = relink_vendors.run(dry_run=True)
    assert stats["rows"] == 1 and stats["linked"] == 0
