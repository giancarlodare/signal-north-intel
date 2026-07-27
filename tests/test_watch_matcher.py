"""Tests for the watch matcher's pure logic (stage 3, operator decisions
A-D 2026-07-27): whole-word keyword semantics, forward-vs-backfill
classification, buyer matching, and idempotency."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import watch_matcher as wm

TODAY = date(2026, 7, 27)


# --- D3: whole-word, case-insensitive ----------------------------------------
def test_keyword_whole_word_only():
    # The pilot's "contracting" lesson: substring matches are false positives.
    assert wm.keyword_matches("contract", "New contract for radios")
    assert not wm.keyword_matches("contract", "General contracting services")
    assert wm.keyword_matches("Dispatch", "dispatch replacement RFP")


def test_keyword_phrases_match_as_phrases():
    assert wm.keyword_matches("digital evidence", "Digital Evidence management")
    assert not wm.keyword_matches("digital evidence", "digital forensic evidence")


def test_keyword_empty_never_matches():
    assert not wm.keyword_matches("", "anything")
    assert not wm.keyword_matches("  ", "anything")


# --- B/D4: forward match vs labelled backfill --------------------------------
def test_classify_forward_match_and_backfill_window():
    # Watch created 2026-07-20.
    assert wm.classify("2026-07-20", "2026-07-20T10:00:00Z", TODAY) == "match"
    assert wm.classify("2026-07-27", "2026-07-20T10:00:00Z", TODAY) == "match"
    assert wm.classify("2026-07-13", "2026-07-20T10:00:00Z", TODAY) == "backfill"
    # Older than 30 days before the watch: ignored entirely.
    assert wm.classify("2026-06-01", "2026-07-20T10:00:00Z", TODAY) is None


def test_classify_bad_dates_are_ignored():
    assert wm.classify("", "2026-07-20", TODAY) is None
    assert wm.classify("2026-07-20", "", TODAY) is None


# --- compute_events: matching, dedup, detail ---------------------------------
W_KW = {"id": "w1", "member_id": "m1", "kind": "keyword",
        "keyword": "dispatch", "organization_id": None,
        "created_at": "2026-07-20T00:00:00Z"}
W_BUYER = {"id": "w2", "member_id": "m1", "kind": "buyer",
           "keyword": None, "organization_id": "org-peel",
           "created_at": "2026-07-20T00:00:00Z"}
U = [
    {"signal_id": "s1", "title": "Peel dispatch replacement",
     "organization_id": "org-peel", "org_name": "Peel Regional Police",
     "week_start": "2026-07-20"},
    {"signal_id": "s2", "title": "Radio tower maintenance",
     "organization_id": "org-halton", "org_name": "Halton",
     "week_start": "2026-07-20"},
]


def test_keyword_and_buyer_watches_fire_independently():
    events = wm.compute_events([W_KW, W_BUYER], U, set(), TODAY)
    got = {(e[0]["id"], e[1]["signal_id"], e[2]) for e in events}
    # s1 matches BOTH the keyword and the buyer watch; s2 matches neither.
    assert got == {("w1", "s1", "match"), ("w2", "s1", "match")}


def test_existing_events_are_skipped_idempotent():
    events = wm.compute_events([W_KW], U, {("w1", "s1")}, TODAY)
    assert events == []


def test_backfill_labelled_not_match():
    old = [{**U[0], "week_start": "2026-07-06"}]
    events = wm.compute_events([W_KW], old, set(), TODAY)
    assert len(events) == 1
    assert events[0][2] == "backfill"


def test_detail_names_the_trigger():
    events = wm.compute_events([W_KW, W_BUYER], U, set(), TODAY)
    details = {e[0]["id"]: e[3] for e in events}
    assert details["w1"] == "keyword: dispatch"
    assert details["w2"] == "buyer: Peel Regional Police"
