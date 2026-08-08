"""Render probe: Hamilton HPSB (Umbraco) + Ottawa PSB (eScribe Meeting.aspx).

Answers three specific questions for the Aug 11-13 adapter build window:
  Q1. After clicking into a meeting, are document links visible in the rendered
      DOM, or are docs behind a further navigation layer?
  Q2. Is there auth, CAPTCHA, or unusual click patterns blocking access?
  Q3. Are Hamilton and Ottawa the same shell shape, or do they differ in ways
      requiring different adapter logic?

Context from earlier probes:
  - Ottawa: 27 Meeting.aspx URLs found in static WordPress HTML (no JS needed
    for the listing layer). Pattern: Meeting.aspx?Id=<UUID>&Agenda=Agenda&lang=English
    This probe renders one of those directly to see the document layer.
  - Hamilton: Listing page is Umbraco JS-rendered; existing probe found 45
    nav-only links and empty <main> after networkidle+3s. This probe tries
    harder: explicit wait-for-selector, raw HTML dump if still empty, network
    request intercept to find the data fetch URL.

Read-only: no logins, no POSTs, no form submissions. Robots/terms discipline
enforced -- checks robots.txt before fetching each host and aborts if disallowed.

    python scripts/probe_escribe_render.py
"""
import json
import logging
import os
import sys
import time
import urllib.robotparser
from datetime import datetime
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HAMILTON_LISTING = "https://www.hamiltonpsb.ca/meetings/agendas-and-materials/"

# First Meeting.aspx URL from the Ottawa WordPress probe (Aug 8 run).
# All 27 use the same pattern: ?Id=<UUID>&Agenda=Agenda&lang=English
OTTAWA_MEETING_SAMPLE = (
    "https://pub-ottawa.escribemeetings.com/Meeting.aspx"
    "?Id=c6988bdf-ee5d-42cf-832a-2579bc4b19c1&Agenda=Agenda&lang=English"
)
OTTAWA_ESCRIBE_HOST = "pub-ottawa.escribemeetings.com"


def _robots_allowed(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        allowed = rp.can_fetch("*", url)
        log.info("robots.txt %s -> can_fetch=%s", robots_url, allowed)
        return allowed, robots_url
    except Exception as e:
        log.warning("robots.txt unreachable at %s: %s -- treating as allowed", robots_url, e)
        return True, robots_url


# ---------------------------------------------------------------------------
# Hamilton HPSB probe
# ---------------------------------------------------------------------------

def probe_hamilton(page) -> dict:
    result = {"site": "Hamilton HPSB", "listing_url": HAMILTON_LISTING}

    allowed, _ = _robots_allowed(HAMILTON_LISTING)
    result["robots_allowed"] = allowed
    if not allowed:
        result["status"] = "BLOCKED by robots.txt"
        return result

    # Capture all XHR/fetch calls to understand where meeting data comes from
    api_calls = []

    def on_request(request):
        if request.resource_type in ("xhr", "fetch"):
            api_calls.append({"url": request.url[:200], "method": request.method})

    page.on("request", on_request)

    log.info("[Hamilton] Loading listing: %s", HAMILTON_LISTING)
    page.goto(HAMILTON_LISTING, wait_until="networkidle", timeout=60000)

    # Extra wait -- Umbraco sometimes fires a second async call after networkidle
    page.wait_for_timeout(5000)

    result["api_calls_captured"] = api_calls[:20]
    log.info("[Hamilton] API calls captured: %d", len(api_calls))
    for call in api_calls[:10]:
        log.info("  %s %s", call["method"], call["url"])

    result["listing_page_title"] = page.title()
    result["listing_url_after_load"] = page.url
    html = page.content()
    result["listing_html_length"] = len(html)
    log.info("[Hamilton] Listing loaded: %d chars, title=%r", len(html), result["listing_page_title"])

    # JS framework hints
    fw = []
    if "umbraco" in html.lower():
        fw.append("Umbraco")
    if "__NEXT_DATA__" in html:
        fw.append("Next.js")
    if "ng-version" in html or '"ng-' in html:
        fw.append("Angular")
    if "react" in html.lower() and "__react" in html:
        fw.append("React")
    result["js_framework_hints"] = fw

    # Dump the raw <main> HTML to understand its structure
    main_html = page.evaluate("""() => {
        const main = document.querySelector('main') || document.querySelector('#main') || document.querySelector('.main-content');
        return main ? main.innerHTML.slice(0, 6000) : null;
    }""")
    result["main_html_snippet"] = main_html[:3000] if main_html else None
    log.info("[Hamilton] main HTML: %s chars (truncated to 3000)",
             len(main_html) if main_html else 0)
    if main_html:
        log.info("[Hamilton] main HTML preview: %r", main_html[:500])

    # Try explicit wait for any meeting-content element to appear
    meeting_wait_selectors = [
        "article", ".meeting-item", ".meeting-list", ".meetings",
        "table.meetings", "table", "ul.listing", ".content-list",
        "li.meeting", "[data-meeting]", ".accordion", ".panel",
        ".list-group", "section.content",
    ]
    content_found_sel = None
    for sel in meeting_wait_selectors:
        try:
            page.wait_for_selector(sel, timeout=3000)
            content_found_sel = sel
            log.info("[Hamilton] Waited for and found: '%s'", sel)
            break
        except Exception:
            pass

    result["content_selector_found"] = content_found_sel

    # Re-query all links after the extra wait
    all_links = page.eval_on_selector_all(
        "a[href]",
        "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80)}))"
    )
    result["listing_link_count"] = len(all_links)
    result["listing_links_sample"] = all_links[:30]

    # Find meeting-entry-style links
    meeting_links = [
        lk for lk in all_links
        if any(kw in lk["href"].lower() for kw in ["meeting", "agenda", "minute", "2024", "2025", "2026"])
        and "hamiltonpsb.ca" in lk["href"]
    ]
    result["meeting_link_candidates"] = meeting_links[:10]
    log.info("[Hamilton] Meeting-candidate links: %d / %d total", len(meeting_links), len(all_links))
    for lk in meeting_links[:5]:
        log.info("  MEETING CANDIDATE: %r -> %r", lk["text"][:60], lk["href"][:100])

    # Full DOM structure snapshot (tag + class + text for all elements with links)
    dom_structure = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('*').forEach(el => {
            if (el.querySelectorAll('a').length > 0) {
                const text = (el.innerText || '').trim().slice(0, 60);
                if (text && !['HTML','BODY','HEAD'].includes(el.tagName)) {
                    out.push({tag: el.tagName, cls: (el.className||'').slice(0,60), text});
                }
            }
        });
        return out.slice(0, 40);
    }""")
    result["dom_structure_with_links"] = dom_structure[:20]
    log.info("[Hamilton] DOM elements with links: %d", len(dom_structure))
    for el in dom_structure[:10]:
        log.info("  <%s class=%r>: %r", el["tag"], el["cls"], el["text"])

    # Screenshot
    page.screenshot(path="hamilton_listing.png", full_page=False)
    result["screenshot"] = "hamilton_listing.png"

    # If we found meeting links, navigate to the first one
    meeting_href = meeting_links[0]["href"] if meeting_links else None
    result["found_meeting_link"] = meeting_href is not None

    if meeting_href:
        log.info("[Hamilton] Navigating to meeting detail: %s", meeting_href)
        page.goto(meeting_href, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)
        result["meeting_page_url"] = page.url
        result["meeting_page_title"] = page.title()
        meeting_html = page.content()
        result["meeting_html_length"] = len(meeting_html)

        page.screenshot(path="hamilton_meeting.png", full_page=True)
        result["meeting_screenshot"] = "hamilton_meeting.png"

        meeting_all_links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80)}))"
        )
        doc_links = [
            lk for lk in meeting_all_links
            if any(ext in lk["href"].lower() for ext in [".pdf", ".doc", ".docx"])
            or any(kw in lk["href"].lower() for kw in ["document", "attachment", "download"])
        ]
        result["doc_link_count"] = len(doc_links)
        result["doc_links"] = doc_links[:20]
        log.info("[Hamilton] Doc links on meeting page: %d", len(doc_links))
        for lk in doc_links[:5]:
            log.info("  DOC: %r -> %r", lk["text"][:50], lk["href"][:100])

        auth = []
        if page.query_selector("input[type='password']"):
            auth.append("password_field")
        if "sign in" in meeting_html.lower() or "log in" in meeting_html.lower():
            auth.append("sign_in_text")
        result["auth_signals"] = auth

        iframes = page.eval_on_selector_all(
            "iframe", "els => els.map(f => f.src || '')"
        )
        result["iframes"] = iframes

    log.info("[Hamilton] Probe complete.")
    return result


# ---------------------------------------------------------------------------
# Ottawa PSB probe -- renders Meeting.aspx directly
# ---------------------------------------------------------------------------

def probe_ottawa(page) -> dict:
    result = {
        "site": "Ottawa PSB",
        "note": "Listing layer already solved: 27 Meeting.aspx URLs in static WP HTML. "
                "This probe renders one Meeting.aspx page to answer Q1-Q3.",
        "meeting_url_probed": OTTAWA_MEETING_SAMPLE,
    }

    allowed, _ = _robots_allowed(OTTAWA_MEETING_SAMPLE)
    result["robots_escribe_allowed"] = allowed
    if not allowed:
        result["status"] = "BLOCKED by robots.txt"
        return result

    # Capture XHR/fetch to understand eScribe's data loading
    api_calls = []

    def on_request(request):
        if request.resource_type in ("xhr", "fetch"):
            api_calls.append({"url": request.url[:200], "method": request.method})

    page.on("request", on_request)

    log.info("[Ottawa] Navigating to Meeting.aspx: %s", OTTAWA_MEETING_SAMPLE[:100])
    page.goto(OTTAWA_MEETING_SAMPLE, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(4000)

    result["api_calls_captured"] = api_calls[:20]
    log.info("[Ottawa] API calls: %d", len(api_calls))
    for call in api_calls[:10]:
        log.info("  %s %s", call["method"], call["url"])

    result["escribe_page_title"] = page.title()
    result["escribe_url_after_load"] = page.url
    html = page.content()
    result["escribe_html_length"] = len(html)
    log.info("[Ottawa] Meeting.aspx: %d chars, title=%r", len(html), result["escribe_page_title"])

    # Screenshot of landing
    page.screenshot(path="ottawa_meeting_aspx.png", full_page=False)
    result["landing_screenshot"] = "ottawa_meeting_aspx.png"

    # JS framework hints
    fw = []
    if "__VIEWSTATE" in html or "WebForms" in html:
        fw.append("ASP.NET WebForms")
    if "angular" in html.lower():
        fw.append("Angular")
    if "jquery" in html.lower():
        fw.append("jQuery")
    if "escribe" in html.lower():
        fw.append("eScribe-branded")
    result["js_framework_hints"] = fw

    # Auth check before anything else
    auth_initial = []
    if page.query_selector("input[type='password']"):
        auth_initial.append("password_field")
    if page.query_selector("[class*='login'],[id*='login']"):
        auth_initial.append("login_ui_element")
    if "sign in" in html.lower() or "log in" in html.lower():
        auth_initial.append("sign_in_text")
    if page.query_selector("[class*='captcha'],[id*='captcha']"):
        auth_initial.append("captcha_element")
    result["auth_signals_on_landing"] = auth_initial

    # Collect all links on the Meeting.aspx page
    all_links = page.eval_on_selector_all(
        "a[href]",
        "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80)}))"
    )
    result["link_count"] = len(all_links)
    result["links_sample"] = all_links[:30]
    log.info("[Ottawa] Links on Meeting.aspx: %d", len(all_links))

    # Direct document links (PDFs, Word docs)
    doc_links = [
        lk for lk in all_links
        if any(ext in lk["href"].lower() for ext in [".pdf", ".doc", ".docx"])
        or any(kw in lk["href"].lower() for kw in ["document", "attachment", "download", "file"])
    ]
    result["doc_link_count_direct"] = len(doc_links)
    result["doc_links_direct"] = doc_links[:20]
    log.info("[Ottawa] Direct doc links: %d", len(doc_links))
    for lk in doc_links[:8]:
        log.info("  DOC: %r -> %r", lk["text"][:50], lk["href"][:100])

    # eScribe renders agenda items as clickable rows in a table -- look for them
    agenda_item_selectors = [
        "table#tblAgendaItems tr", "table.agendaItems tr", "#AgendaItems tr",
        "[class*='AgendaItem']", "[class*='agendaItem']",
        "tr[class*='item']", "#ctl00_ContentPlaceHolder1",
        "table tr", "tbody tr",
    ]
    agenda_entries = []
    used_agenda_sel = None
    for sel in agenda_item_selectors:
        try:
            els = page.query_selector_all(sel)
            if len(els) > 2:
                for el in els[:5]:
                    text = (el.inner_text() or "").strip()
                    if text and len(text) > 3:
                        agenda_entries.append(text[:100])
                if agenda_entries:
                    used_agenda_sel = sel
                    log.info("[Ottawa] Agenda items via '%s': %d entries", sel, len(els))
                    break
        except Exception:
            pass
    result["agenda_item_selector"] = used_agenda_sel
    result["agenda_item_samples"] = agenda_entries[:5]

    # Raw main content HTML snippet
    main_html = page.evaluate("""() => {
        const main = document.querySelector('#ctl00_ContentPlaceHolder1')
            || document.querySelector('main')
            || document.querySelector('.content')
            || document.querySelector('#content');
        return main ? main.innerHTML.slice(0, 6000) : document.body.innerHTML.slice(0, 4000);
    }""")
    result["main_html_snippet"] = main_html[:3000] if main_html else None
    log.info("[Ottawa] main HTML snippet: %d chars", len(main_html) if main_html else 0)
    if main_html:
        log.info("[Ottawa] main HTML preview: %r", main_html[:500])

    # DOM structure
    dom_structure = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('*').forEach(el => {
            if (el.querySelectorAll('a').length > 0) {
                const text = (el.innerText || '').trim().slice(0, 60);
                if (text && !['HTML','BODY','HEAD'].includes(el.tagName)) {
                    out.push({tag: el.tagName, cls: (el.className||'').slice(0,60), text});
                }
            }
        });
        return out.slice(0, 40);
    }""")
    result["dom_structure_with_links"] = dom_structure[:20]

    # Check iframes
    iframes = page.eval_on_selector_all(
        "iframe", "els => els.map(f => f.src || f.getAttribute('data-src') || '')"
    )
    result["iframes"] = iframes
    if iframes:
        log.info("[Ottawa] Iframes: %s", iframes[:5])

    # Full page screenshot
    page.screenshot(path="ottawa_meeting_aspx_full.png", full_page=True)
    result["full_screenshot"] = "ottawa_meeting_aspx_full.png"

    log.info("[Ottawa] Probe complete. doc_links=%d auth=%s iframes=%d",
             len(doc_links), auth_initial, len(iframes))
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    from playwright.sync_api import sync_playwright

    log.info("eScribe render probe starting -- %s EST", datetime.now().strftime("%Y-%m-%d %H:%M"))

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()

        log.info("=== HAMILTON HPSB PROBE ===")
        hamilton = probe_hamilton(page)

        log.info("=== OTTAWA PSB PROBE ===")
        ottawa = probe_ottawa(page)

        browser.close()

    findings = {
        "probe_time_utc": datetime.utcnow().isoformat() + "Z",
        "hamilton": hamilton,
        "ottawa": ottawa,
    }

    with open("escribe_probe_findings.json", "w") as f:
        json.dump(findings, f, indent=2)

    # Compact summary
    print("\n" + "=" * 70)
    print("PROBE SUMMARY")
    print("=" * 70)

    h = hamilton
    print("\n--- HAMILTON HPSB ---")
    print(f"  Listing HTML: {h.get('listing_html_length', '?')} chars")
    print(f"  JS frameworks: {h.get('js_framework_hints', [])}")
    print(f"  API calls on load: {len(h.get('api_calls_captured', []))}")
    for c in h.get("api_calls_captured", [])[:5]:
        print(f"    {c['method']} {c['url'][:80]}")
    print(f"  Total links: {h.get('listing_link_count', '?')}")
    print(f"  Meeting link candidates: {len(h.get('meeting_link_candidates', []))}")
    if h.get("meeting_link_candidates"):
        for lk in h["meeting_link_candidates"][:3]:
            print(f"    {lk['text'][:40]} -> {lk['href'][:80]}")
    print(f"  Content selector found: {h.get('content_selector_found', 'None')}")
    print(f"  main HTML length: {len(h.get('main_html_snippet') or '')}")
    if h.get("main_html_snippet"):
        print(f"  main HTML: {h['main_html_snippet'][:300]!r}")
    if h.get("doc_link_count") is not None:
        print(f"  Doc links on meeting page: {h['doc_link_count']}")

    o = ottawa
    print("\n--- OTTAWA PSB (eScribe Meeting.aspx) ---")
    print(f"  URL probed: {o.get('meeting_url_probed', '?')[:80]}")
    print(f"  Page title: {o.get('escribe_page_title', '?')}")
    print(f"  HTML: {o.get('escribe_html_length', '?')} chars")
    print(f"  JS frameworks: {o.get('js_framework_hints', [])}")
    print(f"  API calls on load: {len(o.get('api_calls_captured', []))}")
    for c in o.get("api_calls_captured", [])[:5]:
        print(f"    {c['method']} {c['url'][:80]}")
    print(f"  Auth signals: {o.get('auth_signals_on_landing', [])}")
    print(f"  Total links: {o.get('link_count', '?')}")
    print(f"  Direct doc links: {o.get('doc_link_count_direct', '?')}")
    if o.get("doc_links_direct"):
        for lk in o["doc_links_direct"][:5]:
            print(f"    {lk['text'][:40]:<40} {lk['href'][:80]}")
    print(f"  Agenda item selector: {o.get('agenda_item_selector', 'None')}")
    print(f"  Agenda samples: {o.get('agenda_item_samples', [])[:3]}")
    print(f"  Iframes: {o.get('iframes', [])[:3]}")
    if o.get("main_html_snippet"):
        print(f"  Content HTML: {o['main_html_snippet'][:400]!r}")

    print("\n  Full findings: escribe_probe_findings.json")
    print("  Screenshots: hamilton_listing.png, hamilton_meeting.png, ottawa_meeting_aspx.png, ottawa_meeting_aspx_full.png")
    print("=" * 70)

    return findings


if __name__ == "__main__":
    main()
