"""eScribe/CivicWeb adapter: parsers, the api-mode inert gate, and the
loud-failure guard. Pinned without a network."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import escribe_adapter as ea


ESCRIBE_LISTING = """
<html><body>
  <a href="Meeting.aspx?Id=aaaaaaaa-1111-2222-3333-444444444444">Jan 15 Board</a>
  <a href="Meeting.aspx?Id=bbbbbbbb-1111-2222-3333-444444444444">Feb 19 Board</a>
  <a href="Meeting.aspx?Id=aaaaaaaa-1111-2222-3333-444444444444">dup</a>
  <a href="/about">not a meeting</a>
</body></html>
"""

ESCRIBE_MEETING = """
<html><body>
  <a href="FileStream.ashx?DocumentId=99">Agenda Package</a>
  <a href="/somewhere/minutes-2026-02-19.pdf">Minutes</a>
  <a href="/somewhere/report.docx">Word (skipped)</a>
  <a href="/about">nope</a>
</body></html>
"""

CIVICWEB_LISTING = """
<html><body>
  <a href="/Portal/MeetingInformation.aspx?Id=17">Council May 5</a>
  <a href="/Portal/Meeting/Details/22">Committee</a>
</body></html>
"""


def test_parse_escribe_meeting_links_absolute_and_deduped():
    links = ea.parse_meeting_links(ESCRIBE_LISTING,
                                   "https://pub-x.escribemeetings.com/?Year=2026")
    assert links == [
        "https://pub-x.escribemeetings.com/Meeting.aspx?Id=aaaaaaaa-1111-2222-3333-444444444444",
        "https://pub-x.escribemeetings.com/Meeting.aspx?Id=bbbbbbbb-1111-2222-3333-444444444444",
    ]


def test_parse_civicweb_meeting_links():
    links = ea.parse_meeting_links(CIVICWEB_LISTING, "https://x.civicweb.net/")
    assert "https://x.civicweb.net/Portal/MeetingInformation.aspx?Id=17" in links
    assert any("/Portal/Meeting/Details/22" in u for u in links)


def test_parse_document_links_skips_office_binaries():
    docs = ea.parse_document_links(ESCRIBE_MEETING,
                                   "https://pub-x.escribemeetings.com/Meeting.aspx?Id=1")
    urls = [u for u, _ in docs]
    assert any("FileStream.ashx" in u for u in urls)
    assert any(u.endswith("minutes-2026-02-19.pdf") for u in urls)
    assert not any(u.endswith(".docx") for u in urls)


# --- api-mode inert gate -----------------------------------------------------
def test_api_tenant_without_endpoint_is_not_callable():
    t = ea.Tenant("pub-ottawa.escribemeetings.com", "Ottawa PSB",
                  "police_board", mode="api")   # no clean_endpoint
    assert ea.api_callable(t) is False
    plan = ea.plan_from_listing(t, "", 2026)
    assert plan["inert"] is True
    assert "no CLEAN endpoint" in plan["reason"]


def test_api_tenant_with_clean_endpoint_is_callable():
    t = ea.Tenant("pub-ottawa.escribemeetings.com", "Ottawa PSB",
                  "police_board", mode="api",
                  clean_endpoint="/api/meetings?year=2026")
    assert ea.api_callable(t) is True


# --- loud failure ------------------------------------------------------------
def test_zero_meetings_when_expected_raises_loud():
    t = ea.Tenant("pub-hamilton.escribemeetings.com", "Hamilton", "council",
                  mode="html", expect_meetings=True)
    with pytest.raises(ea.LoudZeroMeetings):
        ea.plan_from_listing(t, "<html>no meetings here</html>", 2026)


def test_zero_meetings_tolerated_when_not_expected():
    t = ea.Tenant("pub-new.escribemeetings.com", "New", "council",
                  mode="html", expect_meetings=False)
    plan = ea.plan_from_listing(t, "<html>nothing yet</html>", 2026)
    assert plan["meetings"] == [] and plan["inert"] is False


def test_html_tenant_plan_lists_meetings():
    t = ea.Tenant("pub-x.escribemeetings.com", "X Board", "police_board")
    plan = ea.plan_from_listing(t, ESCRIBE_LISTING, 2026)
    assert len(plan["meetings"]) == 2
    assert plan["inert"] is False
