import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.hashing import content_hash


def test_hash_is_stable_and_case_insensitive():
    a = content_hash("PW-24-00123", "tender_notice")
    b = content_hash("pw-24-00123", "TENDER_NOTICE")
    assert a == b


def test_different_doc_type_changes_hash():
    a = content_hash("PW-24-00123", "tender_notice")
    b = content_hash("PW-24-00123", "award_notice")
    assert a != b
