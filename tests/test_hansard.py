"""Tests for the Ontario Hansard collector's pure logic: dated-URL discovery,
scope filtering (the Hansard keep-all exception), page-date parsing, and
payload construction. The network path is exercised by a CI dry-run."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import hansard as h
from src.filters import Keywords

KW = Keywords(general=("infrastructure",), defence=("police",))

INDEX_HTML = """
<html><body>
<a href="/en/legislative-business/house-documents/parliament-43/session-1/2024-12-12/hansard">December 12, 2024</a>
<a href="/en/legislative-business/house-documents/parliament-43/session-1/2025-03-05/">March 5, 2025</a>
<a href="/en/legislative-business/house-documents/parliament-43/session-1/">index self-link</a>
<a href="/en/members/some-mpp">not a debate</a>
<a href="/en/legislative-business/house-documents/parliament-43/session-1/2024-12-12/hansard">dup</a>
</body></html>
"""


def test_dated_debate_urls_finds_days_newest_first_no_dups():
    days = h.dated_debate_urls(INDEX_HTML, h.SESSION_INDEX)
    assert [d for d, _ in days] == ["2025-03-05", "2024-12-12"]


def test_dated_debate_urls_empty_on_no_matches():
    assert h.dated_debate_urls("<html><a href='/x'>x</a></html>", h.SESSION_INDEX) == []


def test_scope_filter_keeps_solgen_and_capital_drops_offtopic():
    assert "solicitor general" in h.matches_scope(
        "The Solicitor General rose to speak on community safety funding.")
    assert "capital plan" in h.matches_scope(
        "The ten-year capital plan includes new courthouse construction.")
    assert h.matches_scope(
        "Debate on the proposed amendments to the Farm Products Act.") == []


def test_page_date_parses_textual_sitting_date():
    assert h.page_date("Thursday 12 December 2024, Legislative Assembly") == "2024-12-12"
    assert h.page_date("no date here") is None


def test_payload_scope_hits_lead_content_and_hash_on_url():
    p = h.build_payload(
        "https://www.ola.org/x/2024-12-12/", "Ontario Hansard, 2024-12-12 sitting",
        "The Solicitor General discussed police modernization.", "2024-12-12",
        "src-1", KW, ["solicitor general", "police"])
    assert p["doc_type"] == "legislative_debate"
    assert p["published_on"] == "2024-12-12"
    assert p["date_precision"] == "day"
    assert p["content"].startswith("[scope: solicitor general, police]")
    assert p["content_hash"] == h.content_hash("https://www.ola.org/x/2024-12-12/",
                                               "legislative_debate")
    assert p["defence_relevant"] is True      # "police" defence keyword


def test_payload_null_date_stays_valid():
    p = h.build_payload("https://www.ola.org/c/doc", "Committee estimates",
                        "public safety estimates discussion", None, "s", KW,
                        ["public safety"])
    assert p["published_on"] is None
    assert p["date_precision"] == "day"
