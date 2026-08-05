import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.filters import Keywords, evaluate, load_keywords, unspsc_segment


def test_load_keywords_splits_general_and_defence():
    kw = load_keywords()
    assert "police" in kw.general
    assert "drone" in kw.defence or "drones" in kw.defence
    assert "drone" not in kw.general
    assert "police" not in kw.defence


def test_keyword_match_marks_kept_but_not_defence():
    kw = Keywords(general=("police",), defence=("drone",))
    result = evaluate("Police vehicle maintenance", "routine service contract", "", kw)
    assert result.kept
    assert not result.defence_relevant


def test_defence_keyword_marks_defence_relevant():
    kw = Keywords(general=("police",), defence=("drone",))
    result = evaluate("Counter-drone system procurement", "", "", kw)
    assert result.kept
    assert result.defence_relevant


def test_unrelated_notice_is_dropped():
    kw = Keywords(general=("police",), defence=("drone",))
    result = evaluate("Office chairs for regional office", "standard furniture", "44120000", kw)
    assert not result.kept


def test_unspsc_segment_forces_keep():
    kw = Keywords(general=("police",), defence=("drone",))
    result = evaluate("Widget purchase", "generic widgets", "46101800", kw)
    assert result.kept
    assert result.matched_unspsc_segment == "46"


def test_unspsc_segment_helper():
    assert unspsc_segment("46101800") == "46"
    assert unspsc_segment("") is None
    assert unspsc_segment("x") is None


# --- Whole-word matching (2026-07-28 fix; CMHC / Bendix false-positive class) ---

def test_substring_inside_word_does_not_match():
    kw = Keywords(general=("ems",), defence=("uas", "ppe"))
    result = evaluate("Bendix Air Brake Systems overhaul",
                      "the appeal was quashed and shipped", "", kw)
    assert not result.kept
    assert not result.defence_relevant


def test_whole_word_still_matches():
    kw = Keywords(general=("ems",), defence=("uas",))
    result = evaluate("EMS station retrofit", "", "", kw)
    assert result.kept and not result.defence_relevant
    result = evaluate("Counter UAS evaluation", "", "", kw)
    assert result.defence_relevant


def test_hyphenated_and_phrase_keywords_match_whole():
    kw = Keywords(general=("911 dispatch",), defence=("counter-drone",))
    assert evaluate("911 dispatch console refresh", "", "", kw).kept
    assert evaluate("Counter-drone pilot project", "", "", kw).defence_relevant
    # ...but not embedded in a longer word
    assert not evaluate("Encounter-drones exhibit", "", "", kw).defence_relevant


def test_punctuation_edged_keyword_still_matches():
    # 'ops/' ends in a non-word char; a bare \b wrapper would kill it.
    kw = Keywords(general=(), defence=("ops/",))
    assert evaluate("Portal", "see https://example.com/ops/plan", "", kw).defence_relevant
    assert not evaluate("Develops/ships weekly", "", "", kw).defence_relevant


# --- Plural tolerance (operator 2026-07-28): s/es inside the boundary --------

def test_plural_tolerance_recovers_plurals():
    kw = Keywords(general=("forensic", "port of entry"), defence=("radio",))
    assert evaluate("Forensics laboratory services", "", "", kw).kept
    assert evaluate("Ports of entry modernization", "", "", kw).kept
    assert evaluate("Portable radios purchase", "", "", kw).defence_relevant


def test_plural_tolerance_keeps_bendix_class_closed():
    # The hard constraint: plural tolerance must not reopen substring hits.
    kw = Keywords(general=("ems",), defence=("uas", "ppe"))
    r = evaluate("Bendix Air Brake Systems", "quashed appeals shipped", "", kw)
    assert not r.kept and not r.defence_relevant


# --- Corridor construction pack (operator 2026-08-05) ------------------------
# The load-bearing property: a construction-ONLY keep is captured but held out
# of the daily extraction pass via its status. A document that ALSO matches the
# core packs stays on the core pipeline byte-identically.
from src.filters import CONSTRUCTION_HOLD_STATUS, document_status


def test_construction_section_loads_separately():
    kw = load_keywords()
    assert "watermain" in kw.construction
    assert "asset management plan" in kw.construction
    assert "watermain" not in kw.general
    assert "police" not in kw.construction


def test_construction_only_keep_gets_hold_status():
    kw = Keywords(general=("police",), defence=("drone",), construction=("watermain",))
    result = evaluate("Watermain replacement Contract 4", "sanitary sewer works", "", kw)
    assert result.kept
    assert result.construction_relevant
    assert result.construction_only
    assert not result.defence_relevant
    assert document_status(result) == CONSTRUCTION_HOLD_STATUS


def test_core_plus_construction_stays_on_core_pipeline():
    kw = Keywords(general=("police",), defence=("drone",), construction=("concrete",))
    result = evaluate("Police station concrete works", "", "", kw)
    assert result.kept
    assert result.construction_relevant
    assert not result.construction_only
    assert document_status(result) == "captured"


def test_core_only_keep_status_unchanged():
    kw = Keywords(general=("police",), defence=("drone",), construction=("watermain",))
    result = evaluate("Police radio system", "", "", kw)
    assert document_status(result) == "captured"


def test_no_match_still_dropped():
    kw = Keywords(general=("police",), defence=("drone",), construction=("watermain",))
    result = evaluate("Office furniture standing offer", "janitorial services", "", kw)
    assert not result.kept


def test_bare_ea_not_in_pack_but_spelled_forms_are():
    kw = load_keywords()
    assert "ea" not in kw.construction  # bare-EA held out (the 'rms' precedent)
    assert "environmental assessment" in kw.construction
    assert "class ea" in kw.construction
