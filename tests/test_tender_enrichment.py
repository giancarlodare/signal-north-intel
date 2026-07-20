"""Tests for CanadaBuys tender enrichment: UNSPSC parsing, the row parser
(close date as event date, buyer, solicitation hard key, content header),
amendment refresh-in-place vs duplicate skip, and the backfill's dry-run
honesty plus the imminent-window operator flag. Fixture columns use the real
header names probed live on 2026-07-20."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import backfill_tender_details as bt
from src import main
from src.canadabuys import build_tender_content, parse_unspsc_codes

COLS = [
    "title-titre-eng", "title-titre-fra",
    "referenceNumber-numeroReference", "amendmentNumber-numeroModification",
    "solicitationNumber-numeroSollicitation",
    "publicationDate-datePublication", "tenderClosingDate-appelOffresDateCloture",
    "amendmentDate-dateModification",
    "expectedContractStartDate-dateDebutContratPrevue",
    "expectedContractEndDate-dateFinContratPrevue",
    "tenderStatus-appelOffresStatut-eng", "tenderStatus-appelOffresStatut-fra",
    "unspsc", "unspscDescription-eng", "unspscDescription-fra",
    "noticeType-avisType-eng", "procurementMethod-methodeApprovisionnement-eng",
    "regionsOfDelivery-regionsLivraison-eng",
    "contractingEntityName-nomEntitContractante-eng",
    "contractingEntityName-nomEntitContractante-fra",
    "endUserEntitiesName-nomEntitesUtilisateurFinal-eng",
    "tenderDescription-descriptionAppelOffres-eng",
    "tenderDescription-descriptionAppelOffres-fra",
]


def _row(**over):
    row = {c: "" for c in COLS}
    row.update({
        "title-titre-eng": "Specialized Police Radio Communication Equipment and Services",
        "referenceNumber-numeroReference": "cb-126-64565337",
        "amendmentNumber-numeroModification": "000",
        "solicitationNumber-numeroSollicitation": "W6399-27-TR05",
        "publicationDate-datePublication": "2026-07-20",
        "tenderClosingDate-appelOffresDateCloture": "2026-07-27T23:59:00",
        "tenderStatus-appelOffresStatut-eng": "Open",
        "unspsc": "*25132100\n*72151600",
        "unspscDescription-eng": "*Unmanned aerial vehicle\n*Specialized communication system services",
        "contractingEntityName-nomEntitContractante-eng": "Department of National Defence (DND)",
        "tenderDescription-descriptionAppelOffres-eng": "This requirement is an RFP against a Supply Arrangement.",
    })
    row.update(over)
    return row


# --- UNSPSC parsing -----------------------------------------------------------
def test_parse_unspsc_codes_multi_and_malformed():
    assert parse_unspsc_codes("*25132100\n*72151600") == ["25132100", "72151600"]
    assert parse_unspsc_codes("*25132100 * 25132100 *junk *123") == ["25132100"]
    assert parse_unspsc_codes("00131600") == ["00131600"]   # leading zero survives
    assert parse_unspsc_codes("") == []
    assert parse_unspsc_codes(None) == []


# --- the row parser -----------------------------------------------------------
def test_close_date_is_the_event_date_and_hard_key_is_the_solicitation():
    t = main.parse_tender_row(_row(), COLS)
    assert t["published_on"] == date(2026, 7, 27)          # close date, not publication
    assert t["solicitation"] == "W6399-27-TR05"            # the procurement hard key
    assert t["cb_reference"] == "cb-126-64565337"          # drives the URL as before
    assert t["buyer_name"] == "Department of National Defence (DND)"
    assert t["unspsc_codes"] == ["25132100", "72151600"]


def test_missing_close_date_never_substitutes_another_date():
    t = main.parse_tender_row(_row(**{"tenderClosingDate-appelOffresDateCloture": ""}), COLS)
    assert t["published_on"] is None                       # policy: NULL, no substitute
    assert "Published: 2026-07-20" in t["content"]         # publication date kept as a fact


def test_content_header_carries_facts_and_description_only():
    t = main.parse_tender_row(_row(), COLS)
    c = t["content"]
    assert "Solicitation number: W6399-27-TR05" in c
    assert "Buyer: Department of National Defence (DND)" in c
    assert "Closing date: 2026-07-27T23:59:00" in c
    assert "Status: Open" in c
    assert "25132100 Unmanned aerial vehicle" in c
    assert "RFP against a Supply Arrangement." in c
    assert "End user:" not in c                            # empty facts omitted


def test_build_tender_content_returns_none_when_empty():
    assert build_tender_content({}, "") is None


# --- collector: insert, duplicate skip, amendment refresh ---------------------
class _Db:
    def __init__(self, existing=None):
        self.existing = existing
        self.inserted, self.updated = [], []

    def get_document_by_hash(self, chash):
        return self.existing

    def insert_document(self, payload):
        self.inserted.append(payload)
        return {"id": "new"}

    def update_row(self, table, rid, payload):
        self.updated.append((table, rid, payload))


def _run_collector(monkeypatch, rows, existing=None):
    db = _Db(existing)
    monkeypatch.setattr(main, "fetch_csv_rows", lambda url: rows)
    for name in ("get_document_by_hash", "insert_document", "update_row"):
        monkeypatch.setattr(main.supabase_client, name, getattr(db, name))
    keywords = main.load_keywords()
    stats = main.process_tender_notices("src1", keywords)
    return db, stats


def test_new_notice_inserts_enriched_document(monkeypatch):
    db, stats = _run_collector(monkeypatch, [_row()])
    assert stats["inserted"] == 1 and not db.updated
    doc = db.inserted[0]
    assert doc["published_on"] == date(2026, 7, 27)
    assert doc["reference_number"] == "W6399-27-TR05"
    assert doc["unspsc_codes"] == ["25132100", "72151600"]
    assert doc["buyer_name"].startswith("Department of National Defence")
    assert "Solicitation number: W6399-27-TR05" in doc["content"]


def test_duplicate_at_amendment_zero_skips(monkeypatch):
    db, stats = _run_collector(monkeypatch, [_row()], existing={"id": "d1"})
    assert stats["skipped_duplicate"] == 1
    assert not db.inserted and not db.updated


def test_amendment_refreshes_in_place_never_duplicates(monkeypatch):
    amended = _row(**{"amendmentNumber-numeroModification": "001",
                      "amendmentDate-dateModification": "2026-07-22",
                      "tenderClosingDate-appelOffresDateCloture": "2026-08-15T14:00:00"})
    db, stats = _run_collector(monkeypatch, [amended], existing={"id": "d1"})
    assert stats["refreshed_amendment"] == 1 and not db.inserted
    table, rid, payload = db.updated[0]
    assert (table, rid) == ("documents", "d1")
    assert payload["published_on"] == date(2026, 8, 15)     # the moved close date lands
    assert "Amendment: 001 (2026-07-22)" in payload["content"]


# --- backfill: dry-run honesty + the imminent-window operator flag ------------
def _backfill_env(monkeypatch, docs, rows, today):
    writes = []
    monkeypatch.setattr(bt.supabase_client, "fetch_all_rows_where", lambda *a, **k: docs)
    monkeypatch.setattr(bt, "fetch_csv_rows", lambda url: rows)
    monkeypatch.setattr(bt.supabase_client, "update_row",
                        lambda table, rid, payload: writes.append((rid, payload)))
    return writes


def test_backfill_dry_run_reports_and_flags_imminent_writes_nothing(monkeypatch):
    today = date(2026, 7, 20)
    docs = [
        {"id": "a", "url": "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-1", "title": "t1"},
        {"id": "b", "url": "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-2", "title": "t2"},
        {"id": "c", "url": "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-gone", "title": "t3"},
    ]
    rows = [
        _row(**{"referenceNumber-numeroReference": "cb-1",
                "tenderClosingDate-appelOffresDateCloture": "2026-07-29T14:00:00"}),  # imminent
        _row(**{"referenceNumber-numeroReference": "cb-2",
                "tenderClosingDate-appelOffresDateCloture": "2026-10-01T14:00:00"}),  # beyond lead
    ]
    writes = _backfill_env(monkeypatch, docs, rows, today)
    stats = bt.run(dry_run=True, today=today)
    assert stats == {"title_only": 3, "fillable": 2, "unmatched": 1,
                     "pulled_into_imminent": 1, "filled": 0, "dry_run": True}
    assert writes == []                                     # dry-run writes nothing


def test_backfill_apply_fills_only_matched(monkeypatch):
    today = date(2026, 7, 20)
    docs = [{"id": "a", "url": ".../tender-notice/cb-1", "title": "t1"},
            {"id": "z", "url": ".../tender-notice/cb-none", "title": "tz"}]
    rows = [_row(**{"referenceNumber-numeroReference": "cb-1"})]
    writes = _backfill_env(monkeypatch, docs, rows, today)
    stats = bt.run(dry_run=False, today=today)
    assert stats["filled"] == 1 and len(writes) == 1
    rid, payload = writes[0]
    assert rid == "a"
    assert payload["reference_number"] == "W6399-27-TR05"
    assert payload["unspsc_codes"] == ["25132100", "72151600"]


def test_backfill_latest_amendment_wins(monkeypatch):
    today = date(2026, 7, 20)
    docs = [{"id": "a", "url": ".../tender-notice/cb-1", "title": "t1"}]
    rows = [_row(**{"referenceNumber-numeroReference": "cb-1",
                    "tenderClosingDate-appelOffresDateCloture": "2026-07-25T14:00:00"}),
            _row(**{"referenceNumber-numeroReference": "cb-1",
                    "amendmentNumber-numeroModification": "001",
                    "tenderClosingDate-appelOffresDateCloture": "2026-08-20T14:00:00"})]
    writes = _backfill_env(monkeypatch, docs, rows, today)
    bt.run(dry_run=False, today=today)
    assert writes[0][1]["published_on"] == date(2026, 8, 20)
