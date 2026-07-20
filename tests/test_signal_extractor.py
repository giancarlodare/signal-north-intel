import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import prompts

from src import signal_extractor as se
from src.signal_extractor import build_resolver, build_signal_payload, fill_prompt


def _orgs():
    return [
        {"id": "org-dnd", "canonical_name": "Department of National Defence",
         "aliases": ["DND", "National Defence"]},
        {"id": "org-rcmp", "canonical_name": "Royal Canadian Mounted Police",
         "aliases": ["RCMP"]},
    ]


def test_resolver_matches_canonical_and_alias_case_insensitively():
    resolve = build_resolver(_orgs(), key_fields=("canonical_name",), alias_field="aliases")
    assert resolve("Department of National Defence") == "org-dnd"
    assert resolve("dnd") == "org-dnd"          # alias, lowercased
    assert resolve("  RCMP ") == "org-rcmp"     # whitespace normalized
    assert resolve("Canada Post") is None       # unknown


def test_resolver_is_accent_insensitive():
    orgs = [{"id": "org-sq", "canonical_name": "Sûreté du Québec", "aliases": ["SQ"]}]
    resolve = build_resolver(orgs, key_fields=("canonical_name",), alias_field="aliases")
    assert resolve("Sûreté du Québec") == "org-sq"   # exact, accented
    assert resolve("Surete du Quebec") == "org-sq"   # model dropped the accents
    assert resolve("SURETE DU QUEBEC") == "org-sq"   # accents dropped + caps


def test_resolver_does_not_substring_match():
    # "DND" must not match some unrelated org just because letters overlap.
    resolve = build_resolver(_orgs(), key_fields=("canonical_name",), alias_field="aliases")
    assert resolve("National Defence Headquarters Ottawa") is None


def _cats():
    return [{"id": "cat-drones", "slug": "drones-rpas", "name": "Drones / RPAS"}]


def test_resolved_org_produces_linked_signal():
    resolve_org = build_resolver(_orgs(), ("canonical_name",), "aliases")
    resolve_cat = build_resolver(_cats(), ("slug", "name"))
    raw = {
        "title": "New body-worn camera program",
        "signal_type": "pilot_program",
        "summary": "A pilot.",
        "confidence": "probable",
        "materiality": 4,
        "organization_name": "DND",
        "category_slug": "drones-rpas",
        "defence_relevant": True,
    }
    p = build_signal_payload(raw, "doc-1", "extraction@v1", resolve_org, resolve_cat)
    assert p["organization_id"] == "org-dnd"
    assert p["category_id"] == "cat-drones"
    assert p["needs_org_resolution"] is False
    assert p["unresolved_org_name"] is None
    assert p["extracted_by"] == "extraction@v1"
    assert p["reviewed"] is False


def test_unresolved_org_is_stored_not_dropped():
    resolve_org = build_resolver(_orgs(), ("canonical_name",), "aliases")
    resolve_cat = build_resolver(_cats(), ("slug", "name"))
    raw = {
        "title": "Halton Police drone RFP",
        "signal_type": "rfi_pre_rfp",
        "summary": "...",
        "confidence": "speculative",
        "materiality": 3,
        "organization_name": "Halton Regional Police Service",
        "category_slug": "unknown-slug",
    }
    p = build_signal_payload(raw, "doc-2", "extraction@v1", resolve_org, resolve_cat)
    assert p["organization_id"] is None            # not resolved
    assert p["needs_org_resolution"] is True       # but flagged, not dropped
    assert p["unresolved_org_name"] == "Halton Regional Police Service"
    assert p["category_id"] is None                # unknown slug -> null (nullable)


def test_no_org_named_is_not_flagged_for_resolution():
    resolve_org = build_resolver(_orgs(), ("canonical_name",), "aliases")
    resolve_cat = build_resolver(_cats(), ("slug", "name"))
    raw = {"title": "Policy note", "signal_type": "policy_announcement",
           "summary": "...", "confidence": "probable", "materiality": 2,
           "organization_name": None, "category_slug": None}
    p = build_signal_payload(raw, "doc-3", "extraction@v1", resolve_org, resolve_cat)
    assert p["organization_id"] is None
    assert p["needs_org_resolution"] is False      # nothing to resolve
    assert p["unresolved_org_name"] is None


def test_materiality_and_enums_are_clamped_and_validated():
    resolve = build_resolver([], ())
    raw = {"title": "x", "signal_type": "not_a_real_type", "summary": "s",
           "confidence": "wrong", "materiality": 99, "organization_name": None,
           "category_slug": None}
    p = build_signal_payload(raw, "doc-4", "extraction@v1", resolve, resolve)
    assert p["materiality"] == 5                    # clamped into 1..5
    assert p["signal_type"] == "other"             # invalid enum -> other
    assert p["confidence"] == "probable"           # invalid enum -> default


def test_fill_prompt_preserves_literal_json_braces():
    # The prompt ends with a literal {"signals": [...]} example. str.format()
    # would treat that as a replacement field and raise KeyError: '"signals"'.
    template = 'Title: {title}\nRespond as {"signals": [ ...objects... ]}'
    out = fill_prompt(template, title="Body-worn cameras", content="x")
    assert "Title: Body-worn cameras" in out
    assert '{"signals": [ ...objects... ]}' in out   # literal braces untouched


def test_real_extraction_prompt_fills_without_error():
    # Regression for the CI dry-run crash: the shipped prompt must fill cleanly.
    template, _stamp = prompts.get_prompt("extraction")
    out = fill_prompt(
        template, title="T", doc_type="award_notice", source_name="S",
        published_on="2026-01-01", url="http://x", content="C",
    )
    assert "{title}" not in out and "{content}" not in out  # tokens substituted
    assert '{"signals":' in out                              # example preserved


def test_dry_run_writes_nothing(monkeypatch):
    """Smoke-test mode must call extraction + resolution but never touch the DB."""
    monkeypatch.setattr(se.supabase_client, "fetch_rows",
                        lambda table, select, limit=10000: [])
    monkeypatch.setattr(se.supabase_client, "get_documents_by_status",
                        lambda status, limit, **k: [
                            {"id": "d1", "title": "t", "doc_type": "award_notice",
                             "url": "u", "published_on": None, "source_id": "s1"}])
    monkeypatch.setattr(se.supabase_client, "get_source_name", lambda sid: "Src")
    monkeypatch.setattr(se, "extract_signals",
                        lambda doc, source_name, model: (
                            [{"title": "x", "signal_type": "other", "summary": "s",
                              "confidence": "probable", "materiality": 3,
                              "organization_name": None, "category_slug": None}],
                            "extraction@v1"))

    calls = {"insert": 0, "update": 0}
    monkeypatch.setattr(se.supabase_client, "insert_signal",
                        lambda p: calls.__setitem__("insert", calls["insert"] + 1))
    monkeypatch.setattr(se.supabase_client, "update_document_status",
                        lambda *a, **k: calls.__setitem__("update", calls["update"] + 1))

    stats = se.run_extraction(batch_size=10, dry_run=True)

    assert calls["insert"] == 0          # nothing written
    assert calls["update"] == 0          # no status change
    assert stats["signals_created"] == 1  # but still counted/verified
    assert stats["documents_processed"] == 1


def test_doc_type_filter_is_passed_through(monkeypatch):
    seen = {}

    def fake_get(status, limit, select="x", doc_type=None, doc_types=None, order=None):
        seen.update(doc_type=doc_type, doc_types=doc_types, order=order)
        return []

    monkeypatch.setattr(se.supabase_client, "fetch_rows",
                        lambda table, select, limit=10000: [])
    monkeypatch.setattr(se.supabase_client, "get_documents_by_status", fake_get)
    se.run_extraction(batch_size=5, dry_run=True, doc_type="board_minutes")
    assert seen["doc_type"] == "board_minutes"
    assert seen["order"] is None  # single-type legacy path does not force an order


def test_forward_path_passes_doc_types_and_newest_first_order(monkeypatch):
    """The daily forward path scopes to several types and drains newest first."""
    seen = {}

    def fake_get(status, limit, select="x", doc_type=None, doc_types=None, order=None):
        seen.update(doc_types=doc_types, order=order)
        return []

    monkeypatch.setattr(se.supabase_client, "fetch_rows",
                        lambda table, select, limit=10000: [])
    monkeypatch.setattr(se.supabase_client, "get_documents_by_status", fake_get)
    se.run_extraction(batch_size=50, dry_run=True, newest_first=True,
                      doc_types=["tender_notice", "news_release", "grant_program"])
    assert seen["doc_types"] == ["tender_notice", "news_release", "grant_program"]
    # nullslast so undated backlog never sorts ahead of a dated, closing-soon doc
    assert seen["order"] == "published_on.desc.nullslast"


def test_get_documents_by_status_builds_in_filter_and_order(monkeypatch):
    """The PostgREST params: several doc_types become an in.() filter, and the
    order clause rides through verbatim."""
    from src import supabase_client as sc

    class _Resp:
        def json(self):
            return []

    seen = {}

    def fake_request(method, path, headers=None, params=None):
        seen.update(method=method, path=path, params=params)
        return _Resp()

    monkeypatch.setattr(sc, "_headers", lambda *a, **k: {})
    monkeypatch.setattr(sc, "_request", fake_request)
    sc.get_documents_by_status(
        "captured", 50,
        doc_types=["tender_notice", "news_release", "grant_program"],
        order="published_on.desc.nullslast")
    p = seen["params"]
    assert p["status"] == "eq.captured"
    assert p["doc_type"] == "in.(tender_notice,news_release,grant_program)"
    assert p["order"] == "published_on.desc.nullslast"
    assert p["limit"] == 50
