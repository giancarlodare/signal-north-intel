"""Unified eScribe / CivicWeb adapter for boards AND councils.

One adapter, not two projects (operator 2026-08-02): a police board and a
city council on the same tenant differ by BODY TYPE, not platform. A tenant
is (host, body, body_type, mode); councils are a config extension of this
same code.

Two shapes, from the fleet-discovery buckets:
  * 'html'  server-rendered (bucket A/B eScribe + all CivicWeb): parse
            meeting links from the year listing, then document links from
            each meeting page. Reuses board_minutes' fetch discipline.
  * 'api'   JS-shell tenants (bucket C eScribe): fetch the meeting list from
            the shell's data endpoint. INERT BY DEFAULT: a tenant is only
            called in this mode once the shell-endpoint probe has recorded
            it CLEAN (robots + terms) AND supplied the discovered endpoint.
            An AMBIGUOUS, DISALLOW, or unprobed tenant is never called --
            enforced by clean_endpoint being required and non-empty.

LOUD FAILURE FROM DAY ONE (operator 2026-08-02): a reversed JS-shell
endpoint is more brittle than server-rendered HTML and can change without
notice. A tenant marked expect_meetings=True that yields ZERO meetings
raises LoudZeroMeetings -- a shape change reds the run instead of silently
collecting nothing. That failure mode has already cost a day and four
nights this week.

This module is PARSE + FETCH-PLAN only (collect-only, safe class): it emits
the document rows a caller inserts through the existing board_minutes path.
No schema, no member surface, no LLM.
"""
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

# Meeting links. eScribe server-rendered: Meeting.aspx?Id=<guid>. CivicWeb:
# /Portal/MeetingInformation.aspx?Id= or /document/ under a meeting.
MEETING_RE = re.compile(
    r'(Meeting\.aspx\?Id=[0-9a-f-]+'
    r'|/Portal/MeetingInformation\.aspx\?[^"\'\s]*'
    r'|/Portal/Meeting[^"\'\s]*)', re.I)
# Document links inside a meeting page.
DOC_RE = re.compile(
    r'(FileStream\.ashx\?[^"\'\s]+'
    r'|/filepro/documents/[^"\'\s]+'
    r'|/document/[^"\'\s]+'
    r'|[^"\'\s]+\.pdf\b)', re.I)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
BINARY_EXT = (".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".zip")


class LoudZeroMeetings(RuntimeError):
    """A tenant that should have meetings returned none: a shape change,
    surfaced loudly rather than swallowed as an empty collect."""


@dataclass
class Tenant:
    host: str
    body: str                       # e.g. "Ottawa Police Services Board"
    body_type: str                  # "police_board" | "council" | "committee" | ...
    mode: str = "html"              # "html" | "api"
    year_path: str = "/?Year={year}"
    # api mode only, and REQUIRED for it: the CLEAN endpoint from the probe.
    clean_endpoint: str = ""
    expect_meetings: bool = True     # loud-failure applies when True


def parse_meeting_links(html: str, base_url: str) -> list:
    """Absolute meeting-page URLs found in a listing page (dedup, ordered)."""
    seen, out = set(), []
    for m in MEETING_RE.findall(html or ""):
        u = urljoin(base_url, m)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def parse_document_links(html: str, base_url: str) -> list:
    """(url, title) document links on a meeting page. Office binaries are
    skipped (the board_minutes pipeline reads PDF/HTML only). Title falls
    back to the URL's last path segment."""
    out, seen = [], set()
    # Prefer anchor text where present; fall back to bare URL matches.
    for href in HREF_RE.findall(html or ""):
        if not DOC_RE.search(href):
            continue
        u = urljoin(base_url, href)
        low = u.lower()
        if low.endswith(BINARY_EXT) or u in seen:
            continue
        seen.add(u)
        title = urlparse(u).path.rsplit("/", 1)[-1] or u
        out.append((u, title))
    for m in DOC_RE.findall(html or ""):
        u = urljoin(base_url, m)
        if u.lower().endswith(BINARY_EXT) or u in seen:
            continue
        seen.add(u)
        out.append((u, urlparse(u).path.rsplit("/", 1)[-1] or u))
    return out


def api_callable(tenant: Tenant) -> bool:
    """A tenant may be called in api mode ONLY when the probe has cleared it
    and handed over a discovered endpoint. This is the inert-by-default gate:
    no CLEAN endpoint => never called."""
    return tenant.mode == "api" and bool(tenant.clean_endpoint)


def guard_meetings(tenant: Tenant, n_meetings: int) -> None:
    """Loud-failure guard. Raise if a tenant that should have meetings has
    none -- the shape changed, and silence is the enemy."""
    if tenant.expect_meetings and n_meetings == 0:
        raise LoudZeroMeetings(
            f"{tenant.host} ({tenant.mode}) returned 0 meetings but "
            f"expect_meetings=True -- likely a shape change; failing loudly "
            f"instead of collecting nothing.")


def listing_url(tenant: Tenant, year: int) -> str:
    return f"https://{tenant.host}" + tenant.year_path.format(year=year)


def plan_from_listing(tenant: Tenant, listing_html: str, year: int) -> dict:
    """Turn one year-listing page into a fetch plan: the meeting URLs to
    visit. Applies the loud-failure guard. api-mode tenants that are not yet
    callable return an inert plan and a stated reason (never a silent zero)."""
    if tenant.mode == "api" and not api_callable(tenant):
        return {"tenant": tenant.host, "mode": tenant.mode, "meetings": [],
                "inert": True,
                "reason": "api mode but no CLEAN endpoint from the probe -- "
                          "not called (inert by default)"}
    base = listing_url(tenant, year)
    meetings = parse_meeting_links(listing_html, base)
    guard_meetings(tenant, len(meetings))
    return {"tenant": tenant.host, "mode": tenant.mode, "meetings": meetings,
            "inert": False}
