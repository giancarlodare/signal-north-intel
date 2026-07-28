import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.filters import Keywords
from src.retag_defence import classify

KW = Keywords(general=(), defence=("uas", "ppe", "drone"))


def test_whole_word_hit_keeps_tag():
    assert classify("Drone detection pilot", "airport perimeter", KW) == "keep"


def test_substring_only_hit_is_verified_flip():
    # 'uas' inside "quashed", 'ppe' inside "shipped": the fixed bug's signature.
    assert classify("Default Real Estate Services",
                    "appeals quashed; goods shipped", KW) == "flip"


def test_no_stored_text_hit_is_unverifiable():
    # Award-notice docs store only a title; the tag came from unstored CSV text.
    assert classify("Default Real Estate Services", None, KW) == "unverifiable"


def test_none_fields_are_tolerated():
    assert classify(None, None, KW) == "unverifiable"
