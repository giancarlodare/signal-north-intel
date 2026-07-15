"""Tests for src/brief_copy.py: the deterministic draft copy (per-item vendor
read and The Read paragraph). The contract is honesty and structure, so the
assertions enforce both: never an em dash, never a clause without its input,
2 to 3 sentences per item keyed on doc_type, and a real fallback for a quiet
week."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import brief_copy as bc


def _sentences(text: str) -> int:
    return sum(1 for part in text.split(". ") if part.strip())


# --- the absolute rule: no em dashes anywhere copy is authored -----------------
def test_no_em_dash_in_any_item_note():
    for dt in ("tender_notice", "award_notice", "grant_program", "board_minutes", None):
        note = bc.draft_item_note(doc_type=dt, timing_path="imminent",
                                  buyer="Region of Peel", title="Roof renovation",
                                  amount_cad=1_500_000)
        assert "—" not in note


def test_no_em_dash_in_the_read():
    clusters = [{"timing_path": "imminent", "org": "Region of Peel"},
                {"timing_path": "recent", "org": "Region of Peel"}]
    assert "—" not in bc.draft_the_read(clusters, peel_recent_awards=326)
    assert "—" not in bc.draft_the_read([])


# --- _fmt_amount: compact, and None (never invented) for missing/non-positive --
def test_fmt_amount_ranges():
    assert bc._fmt_amount(1_500_000) == "$1.5M"
    assert bc._fmt_amount(42_000) == "$42K"
    assert bc._fmt_amount(750) == "$750"


def test_fmt_amount_missing_or_zero_is_none():
    assert bc._fmt_amount(None) is None
    assert bc._fmt_amount(0) is None
    assert bc._fmt_amount(-5) is None
    assert bc._fmt_amount("not a number") is None


# --- no fabrication: a clause appears only when its input is present -----------
def test_amount_clause_absent_when_no_amount():
    note = bc.draft_item_note(doc_type="award_notice", timing_path="recent",
                              buyer="City", title="Consulting services", amount_cad=None)
    assert "reported value" not in note.lower()


def test_amount_clause_present_when_amount_given():
    note = bc.draft_item_note(doc_type="award_notice", timing_path="recent",
                              buyer="City", title="Consulting services", amount_cad=2_000_000)
    assert "$2.0M" in note


def test_field_clause_absent_when_title_unrecognized():
    note = bc.draft_item_note(doc_type="award_notice", timing_path="recent",
                              buyer="City", title="Miscellaneous item", amount_cad=None)
    assert "reads as" not in note


# --- plausible_field: a reading of the title's own words ------------------------
def test_plausible_field_from_title_keywords():
    assert bc.plausible_field("Roof renovation at city hall") == \
        "general contractors with public-sector experience"
    assert bc.plausible_field("SCADA integration") == "systems integrators and IT suppliers"
    assert bc.plausible_field("Bridge engineering study") == "engineering and consulting firms"
    assert bc.plausible_field("") is None
    assert bc.plausible_field("something opaque") is None


# --- structure: 2 to 3 sentences, keyed on doc_type ----------------------------
def test_item_note_is_two_to_three_sentences():
    for dt, tp in (("tender_notice", "imminent"), ("award_notice", "recent"),
                   ("grant_program", "imminent"), ("board_minutes", "recent")):
        note = bc.draft_item_note(doc_type=dt, timing_path=tp, buyer="Region of Peel",
                                  title="Roof renovation", amount_cad=1_000_000)
        assert 2 <= _sentences(note) <= 3, (dt, note)


def test_tender_prequalification_note_is_distinct():
    pre = bc.draft_item_note(doc_type="tender_notice", timing_path="imminent",
                             buyer="Region of Peel", title="Prequalification of general contractors")
    plain = bc.draft_item_note(doc_type="tender_notice", timing_path="imminent",
                               buyer="Region of Peel", title="Roof renovation")
    assert "prequalif" in pre.lower() and "shortlist" in pre.lower()
    assert "prequalif" not in plain.lower()


def test_item_note_names_the_buyer():
    note = bc.draft_item_note(doc_type="award_notice", timing_path="recent",
                              buyer="Region of Peel", title="Roof renovation")
    assert "Region of Peel" in note


def test_item_note_falls_back_without_buyer_or_title():
    note = bc.draft_item_note(doc_type=None, timing_path=None, buyer=None, title=None)
    assert note and "—" not in note


# --- The Read: item mix + optional corpus scale fact ---------------------------
def test_the_read_empty_week_fallback():
    read = bc.draft_the_read([])
    assert "quiet week" in read.lower()
    assert str  # sanity


def test_the_read_counts_items_and_imminent():
    clusters = [{"timing_path": "imminent", "org": "Region of Peel"},
                {"timing_path": "imminent", "org": "Region of Peel"},
                {"timing_path": "recent", "org": "City of Brampton"}]
    read = bc.draft_the_read(clusters)
    assert "3 items" in read
    assert "Region of Peel is the dominant buyer" in read


def test_the_read_peel_fact_only_when_provided():
    clusters = [{"timing_path": "recent", "org": "City"}]
    assert "Region of Peel has closed" not in bc.draft_the_read(clusters, None)
    assert "Region of Peel has closed 326 contracts" in bc.draft_the_read(clusters, 326)
    # a zero/None count is never rendered as a fake scale fact
    assert "Region of Peel has closed" not in bc.draft_the_read(clusters, 0)
