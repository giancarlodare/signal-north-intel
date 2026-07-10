import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import discovery as dv


def _doc(i, source, *hosts, title="Minutes"):
    body = " ".join(f"See https://{h}/reports/item-{i}.pdf for detail." for h in hosts)
    return {"id": f"doc-{i}", "source_id": source, "title": title, "content": body}


# ---------------------------------------------------------------------------
# Detector 1 — source domains (§8: >=5 docs across >=2 sources)
# ---------------------------------------------------------------------------
def test_domain_needs_five_docs_and_two_sources():
    docs = [_doc(i, "src-1", "halton.example.ca") for i in range(4)]
    # 4 docs: below doc threshold
    assert dv.detect_source_domains(docs, set(), set()) == []
    # 5 docs but all one source: below source threshold
    docs.append(_doc(4, "src-1", "halton.example.ca"))
    assert dv.detect_source_domains(docs, set(), set()) == []
    # 5 docs across 2 sources: proposed
    docs[4] = _doc(4, "src-2", "halton.example.ca")
    proposals = dv.detect_source_domains(docs, set(), set())
    assert len(proposals) == 1
    p = proposals[0]
    assert p["domain"] == "halton.example.ca"
    assert p["mention_count"] == 5 and p["source_count"] == 2
    assert len(p["evidence_document_ids"]) == 5           # provenance mandatory
    assert p["proposed_by"] == "heuristic@v1"


def test_same_doc_counts_once_per_domain():
    doc = _doc(1, "src-1", "x.example.ca", "x.example.ca", "x.example.ca")
    docs = [doc] + [_doc(i, "src-2", "x.example.ca") for i in range(2, 6)]
    p = dv.detect_source_domains(docs, set(), set())[0]
    assert p["mention_count"] == 5                        # not 7


def test_blocklist_and_known_hosts_are_excluded():
    docs = [_doc(i, f"src-{i % 2}", "news.google.com", "tpsb.ca", "fresh.example.ca")
            for i in range(6)]
    proposals = dv.detect_source_domains(
        docs, known_hosts={"tpsb.ca"}, blocklist={"news.google.com"})
    assert [p["domain"] for p in proposals] == ["fresh.example.ca"]


def test_blocklist_blocks_subdomains():
    assert dv.is_blocked("feeds.news.google.com", {"news.google.com"})
    assert dv.is_blocked("news.google.com", {"news.google.com"})
    assert not dv.is_blocked("newsgoogle.com", {"news.google.com"})


def test_kind_guess_and_name():
    assert dv.guess_kind(["https://x.ca/board/minutes-jan.pdf"]) == "board"
    assert dv.guess_kind(["https://x.ca/newsroom/rss"]) == "newsroom"
    assert dv.guess_kind(["https://x.ca/whatever"]) == "publisher_other"
    assert "peelpolice" in dv.suggest_name("peelpolice.ca").lower()


# ---------------------------------------------------------------------------
# Detector 2 tier 1 — unresolved orgs (§8: >=3 docs)
# ---------------------------------------------------------------------------
def _sig(i, name, doc=None):
    return {"id": f"sig-{i}", "document_id": doc or f"doc-{i}",
            "unresolved_org_name": name}


def test_unresolved_org_threshold_and_normalization():
    signals = [_sig(1, "Halton Regional Police Service"),
               _sig(2, "HALTON  Regional Police Service"),      # case/space folded
               _sig(3, "Halton Régional Police Service")]       # accent folded
    proposals = dv.detect_unresolved_orgs(signals, {})
    assert len(proposals) == 1
    p = proposals[0]
    assert p["entity_kind"] == "organization"
    assert p["mention_count"] == 3
    assert p["proposed_by"] == "unresolved-orgs@v1"

    # Two docs only: below threshold
    assert dv.detect_unresolved_orgs(signals[:2], {}) == []


def test_near_match_becomes_alias_update():
    org_lookup = {dv.normalize("Ministry of the Solicitor General"):
                  ("org-9", "Ministry of the Solicitor General")}
    signals = [_sig(i, "Ontario Ministry of the Solicitor General") for i in range(3)]
    p = dv.detect_unresolved_orgs(signals, org_lookup)[0]
    assert p["entity_kind"] == "alias_update"
    assert p["existing_organization_id"] == "org-9"
    assert p["detail"]["add_alias_to"] == "Ministry of the Solicitor General"


def test_same_document_counts_once_for_entity():
    signals = [_sig(i, "Halton Police", doc="doc-same") for i in range(5)]
    assert dv.detect_unresolved_orgs(signals, {}) == []   # 1 distinct doc < 3


# ---------------------------------------------------------------------------
# Tier 2 merge rules
# ---------------------------------------------------------------------------
def test_llm_org_candidates_respect_threshold_and_known_orgs():
    stamp = "discovery@v1"
    cands = (
        [{"entity_kind": "organization", "name": "Durham Police Board",
          "detail": "d", "organization": None, "role": None,
          "evidence_doc_ids": [f"doc-{i}"]} for i in range(3)]
        + [{"entity_kind": "organization", "name": "Known Org",
            "detail": "d", "organization": None, "role": None,
            "evidence_doc_ids": ["doc-1", "doc-2", "doc-3"]}]
        + [{"entity_kind": "organization", "name": "Once Mentioned",
            "detail": "d", "organization": None, "role": None,
            "evidence_doc_ids": ["doc-9"]}]
    )
    known = {dv.normalize("Known Org"): ("org-1", "Known Org")}
    out = dv.merge_llm_candidates(cands, stamp, known)
    names = [p["name"] for p in out]
    assert "Durham Police Board" in names       # merged to 3 docs, kept
    assert "Known Org" not in names             # already tracked
    assert "Once Mentioned" not in names        # below threshold


def test_llm_appointments_keep_single_doc_bar():
    cands = [{"entity_kind": "person_appointment", "name": "Jane Doe",
              "detail": "named chief", "organization": "Testville PS",
              "role": "Chief", "evidence_doc_ids": ["doc-1"]}]
    out = dv.merge_llm_candidates(cands, "discovery@v1", {})
    assert len(out) == 1
    assert out[0]["detail"]["role"] == "Chief"
    assert out[0]["evidence_document_ids"] == ["doc-1"]


# ---------------------------------------------------------------------------
# Upsert rules: reviewed rows are never touched; dry run writes nothing
# ---------------------------------------------------------------------------
def _proposal(domain="new.example.ca"):
    return {"domain": domain, "suggested_name": "New", "kind": "publisher_other",
            "sample_urls": ["https://new.example.ca/a"],
            "evidence_document_ids": ["doc-1"], "mention_count": 5,
            "source_count": 2, "proposed_by": "heuristic@v1"}


def _wire(monkeypatch, existing=None):
    calls = {"insert": [], "update": []}
    monkeypatch.setattr(dv.supabase_client, "fetch_rows_where",
                        lambda table, select, filters, limit=10000: existing or [])
    monkeypatch.setattr(dv.supabase_client, "insert_row",
                        lambda t, p: calls["insert"].append((t, p)) or {"id": "n"})
    monkeypatch.setattr(dv.supabase_client, "update_row",
                        lambda t, i, p: calls["update"].append((t, i, p)))
    return calls


def test_new_proposal_inserts(monkeypatch):
    calls = _wire(monkeypatch)
    assert dv.upsert_source_proposal(_proposal(), dry_run=False) == "proposed"
    assert len(calls["insert"]) == 1


def test_rejected_row_is_never_touched(monkeypatch):
    calls = _wire(monkeypatch, existing=[{"id": "r1", "status": "rejected",
                                          "evidence_document_ids": []}])
    assert dv.upsert_source_proposal(_proposal(), dry_run=False) == "skipped_reviewed"
    assert calls["insert"] == [] and calls["update"] == []


def test_approved_row_is_never_touched(monkeypatch):
    calls = _wire(monkeypatch, existing=[{"id": "a1", "status": "approved",
                                          "evidence_document_ids": []}])
    assert dv.upsert_entity_proposal(
        {"entity_kind": "organization", "normalized_name": "x", "name": "X",
         "detail": {}, "evidence_document_ids": ["d"], "mention_count": 3,
         "proposed_by": "unresolved-orgs@v1"}, dry_run=False) == "skipped_reviewed"
    assert calls["insert"] == [] and calls["update"] == []


def test_proposed_row_refreshes_and_merges_evidence(monkeypatch):
    calls = _wire(monkeypatch, existing=[{"id": "p1", "status": "proposed",
                                          "evidence_document_ids": ["doc-0"]}])
    assert dv.upsert_source_proposal(_proposal(), dry_run=False) == "refreshed"
    (_, _, payload), = calls["update"]
    assert set(payload["evidence_document_ids"]) == {"doc-0", "doc-1"}


def test_dry_run_writes_nothing(monkeypatch):
    calls = _wire(monkeypatch)
    assert dv.upsert_source_proposal(_proposal(), dry_run=True) == "would_propose"
    calls2 = _wire(monkeypatch, existing=[{"id": "p1", "status": "proposed",
                                           "evidence_document_ids": []}])
    assert dv.upsert_source_proposal(_proposal(), dry_run=True) == "would_refresh"
    assert calls["insert"] == [] and calls["update"] == []
    assert calls2["insert"] == [] and calls2["update"] == []
