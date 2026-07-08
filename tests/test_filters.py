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
