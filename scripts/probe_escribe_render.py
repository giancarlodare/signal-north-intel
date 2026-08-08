"""Render probe: Hamilton HPSB (Umbraco) + Ottawa PSB (eScribe Meeting.aspx).

Answers three specific questions for the Aug 11-13 adapter build window:
  Q1. After clicking into a meeting, are document links visible in the rendered
      DOM, or are docs behind a further navigation layer?
  Q2. Is there auth, CAPTCHA, or unusual click patterns blocking access?
  Q3. Are Hamilton and Ottawa the same shell shape, or do they differ in ways
      requiring different adapter logic?

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
from urllib.parse import urljoin, urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HAMILTON_LISTING = "https://www.hamiltonpsb.ca/meetings/agendas-and-materials/"
OTTAWA_WP = "https://www.ottawapoliceboard.ca/opsb-cspo/meetings.html"
OTTAWA_ESCRIBE_HOST = "pub-ottawa.escribemeetings.com"
OTTAWA_ESCRIBE = f"https://{OTTAWA_ESCRIBE_HOST}/Meeting.aspx"


# ---------------------------------------------------------------------------
# Robots check
# ---------------------------------------------------------------------------

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
        log.warning("[Hamilton] robots.txt disallows fetch -- aborting")
        return result

    log.info("[Hamilton] Loading listing: %s", HAMILTON_LISTING)
    page.goto(HAMILTON_LISTING, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    result["listing_page_title"] = page.title()
    result["listing_url_after_load"] = page.url
    html = page.content()
    result["listing_html_length"] = len(html)
    log.info("[Hamilton] Listing loaded: %d chars, title=%r", len(html), result["listing_page_title"])

    # Detect JS framework markers
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

    # Collect all links on the listing page
    all_links = page.eval_on_selector_all(
        "a[href]",
        "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80)}))"
    )
    result["listing_link_count"] = len(all_links)
    result["listing_links_sample"] = all_links[:30]
    log.info("[Hamilton] Listing links: %d total", len(all_links))

    # SELECT dropdowns (year filter?)
    selects = page.eval_on_selector_all(
        "select",
        "els => els.map(s => ({name: s.name||s.id, options: [...s.options].map(o => o.value)}))"
    )
    result["select_elements"] = selects

    # Attempt to find and click a meeting entry
    # Hamilton Umbraco typically renders: list of meeting titles -> click -> detail page with PDFs
    meeting_click_candidates = [
        ("a[href*='meeting']", "meeting in href"),
        ("a[href*='agenda']", "agenda in href"),
        ("a[href*='minutes']", "minutes in href"),
        (".meetings-list a", "meetings-list class"),
        (".agendas-list a", "agendas-list class"),
        ("ul.listing li a", "ul.listing li a"),
        ("article a", "article a"),
        (".content-list a", "content-list a"),
        (".document-list a", "document-list a"),
        ("table a", "table a"),
        (".accordion .panel a", "accordion panel a"),
        (".list-group-item a", "list-group-item a"),
    ]

    meeting_href = None
    meeting_text = None
    used_selector = None

    for sel, desc in meeting_click_candidates:
        try:
            el = page.query_selector(sel)
            if el:
                href = el.get_attribute("href") or ""
                text = (el.inner_text() or "").strip()
                # Skip navigation/header/footer links
                if href and not any(skip in href for skip in ["#", "javascript:", "mailto:"]):
                    meeting_href = href
                    meeting_text = text
                    used_selector = sel
                    log.info("[Hamilton] First meeting link via '%s': %r -> %r", sel, text[:60], href[:80])
                    break
        except Exception:
            pass

    if not meeting_href:
        # Fall back: any deep link on the same host that looks like a content page
        for link in all_links:
            href = link["href"]
            text = link["text"]
            if "hamiltonpsb.ca" in href and href != HAMILTON_LISTING:
                if any(kw in href.lower() for kw in ["2024", "2025", "2026", "meet", "agenda", "board"]):
                    meeting_href = href
                    meeting_text = text
                    used_selector = "fallback-keyword-match"
                    log.info("[Hamilton] Fallback meeting link: %r -> %r", text[:60], href[:80])
                    break

    result["found_meeting_link"] = meeting_href is not None
    result["first_meeting_href"] = meeting_href
    result["first_meeting_text"] = meeting_text
    result["first_meeting_selector"] = used_selector

    if not meeting_href:
        log.warning("[Hamilton] No meeting link found on listing page")
        # Take screenshot of listing for manual inspection
        page.screenshot(path="hamilton_listing.png")
        result["listing_screenshot"] = "hamilton_listing.png"
        return result

    # Navigate to the meeting detail page
    log.info("[Hamilton] Navigating to meeting detail: %s", meeting_href)
    page.goto(meeting_href, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)

    result["meeting_page_url"] = page.url
    result["meeting_page_title"] = page.title()
    meeting_html = page.content()
    result["meeting_html_length"] = len(meeting_html)
    log.info("[Hamilton] Meeting detail: %d chars, title=%r", len(meeting_html), result["meeting_page_title"])

    # Screenshot
    page.screenshot(path="hamilton_meeting.png", full_page=True)
    result["meeting_screenshot"] = "hamilton_meeting.png"

    # Collect doc links (PDFs, Word docs, direct downloads)
    meeting_links = page.eval_on_selector_all(
        "a[href]",
        "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80)}))"
    )
    doc_links = [
        lk for lk in meeting_links
        if any(ext in lk["href"].lower() for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx"])
        or any(kw in lk["href"].lower() for kw in ["document", "attachment", "download", "file"])
    ]
    result["doc_link_count"] = len(doc_links)
    result["doc_links"] = doc_links[:20]
    log.info("[Hamilton] Document links on meeting page: %d", len(doc_links))
    for lk in doc_links[:8]:
        log.info("  DOC: %r -> %r", lk["text"][:50], lk["href"][:100])

    # Iframes (embedded viewers)
    iframes = page.eval_on_selector_all(
        "iframe",
        "els => els.map(f => f.src || f.getAttribute('data-src') || '')"
    )
    result["iframes"] = iframes

    # Auth signals
    auth = []
    if page.query_selector("input[type='password']"):
        auth.append("password_field")
    if page.query_selector("[class*='login'],[class*='auth'],[id*='login']"):
        auth.append("login_ui_element")
    if "sign in" in meeting_html.lower() or "log in" in meeting_html.lower():
        auth.append("sign_in_text_in_html")
    if page.query_selector("[class*='captcha'],[id*='captcha']"):
        auth.append("captcha_element")
    result["auth_signals"] = auth

    # Further navigation: tabs or accordions that might reveal more docs
    tabs = page.eval_on_selector_all(
        "[role='tab'], .nav-tab, [data-toggle='tab'], [data-bs-toggle='tab']",
        "els => els.map(e => (e.innerText||'').trim().slice(0,50))"
    )
    result["nav_tabs"] = tabs

    # DOM structure around doc links (to understand adapter selector)
    doc_container = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('a[href]').forEach(a => {
            const href = a.href || '';
            if (href.match(/\\.pdf|\\.doc|attachment|download/i)) {
                const parent = a.parentElement;
                out.push({
                    tag: a.tagName,
                    href: href.slice(0, 120),
                    text: (a.innerText||'').trim().slice(0,60),
                    parent_tag: parent ? parent.tagName : '',
                    parent_class: parent ? parent.className : ''
                });
            }
        });
        return out.slice(0, 15);
    }""")
    result["doc_dom_structure"] = doc_container

    log.info("[Hamilton] Probe complete. doc_links=%d auth=%s iframes=%s",
             len(doc_links), auth, iframes[:3] if iframes else [])
    return result


# ---------------------------------------------------------------------------
# Ottawa PSB probe
# ---------------------------------------------------------------------------

def probe_ottawa(page) -> dict:
    result = {"site": "Ottawa PSB", "wp_url": OTTAWA_WP, "escribe_url": OTTAWA_ESCRIBE}

    # Check robots on both hosts
    wp_allowed, _ = _robots_allowed(OTTAWA_WP)
    escribe_allowed, _ = _robots_allowed(OTTAWA_ESCRIBE)
    result["robots_wp_allowed"] = wp_allowed
    result["robots_escribe_allowed"] = escribe_allowed

    if not wp_allowed and not escribe_allowed:
        result["status"] = "BLOCKED by robots.txt on both hosts"
        return result

    # Navigate WordPress nav page to find eScribe deep links
    escribe_entry_url = None
    if wp_allowed:
        log.info("[Ottawa] Loading WordPress nav: %s", OTTAWA_WP)
        page.goto(OTTAWA_WP, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)
        result["wp_title"] = page.title()

        escribe_links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80)}))"
        )
        escribe_links = [lk for lk in escribe_links if OTTAWA_ESCRIBE_HOST in lk["href"]]
        result["escribe_links_on_wp"] = escribe_links[:10]
        log.info("[Ottawa] eScribe links on WP page: %d", len(escribe_links))

        if escribe_links:
            escribe_entry_url = escribe_links[0]["href"]
            log.info("[Ottawa] Using eScribe entry URL from WP: %s", escribe_entry_url[:100])

    # Fall back to the base eScribe URL if WP had none or was blocked
    if not escribe_entry_url and escribe_allowed:
        escribe_entry_url = OTTAWA_ESCRIBE
        log.info("[Ottawa] Using base eScribe URL: %s", escribe_entry_url)

    if not escribe_entry_url:
        result["status"] = "No eScribe URL available and both hosts blocked"
        return result

    # Navigate to eScribe
    log.info("[Ottawa] Navigating to eScribe: %s", escribe_entry_url)
    page.goto(escribe_entry_url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(4000)

    result["escribe_landed_url"] = page.url
    result["escribe_page_title"] = page.title()
    escribe_html = page.content()
    result["escribe_html_length"] = len(escribe_html)
    log.info("[Ottawa] eScribe page: %d chars, title=%r, url=%s",
             len(escribe_html), result["escribe_page_title"], page.url)

    # Screenshot of listing
    page.screenshot(path="ottawa_escribe_listing.png")
    result["listing_screenshot"] = "ottawa_escribe_listing.png"

    # JS framework
    fw = []
    if "__VIEWSTATE" in escribe_html or "WebForms" in escribe_html:
        fw.append("ASP.NET WebForms")
    if "angular" in escribe_html.lower():
        fw.append("Angular")
    if "jquery" in escribe_html.lower():
        fw.append("jQuery")
    if "escribe" in escribe_html.lower():
        fw.append("eScribe-branded")
    result["js_framework_hints"] = fw

    # Auth signals before trying to navigate
    auth = []
    if page.query_selector("input[type='password']"):
        auth.append("password_field")
    if page.query_selector("[class*='login'],[id*='login']"):
        auth.append("login_ui_element")
    if "sign in" in escribe_html.lower() or "log in" in escribe_html.lower():
        auth.append("sign_in_text")
    if page.query_selector("[class*='captcha'],[id*='captcha']"):
        auth.append("captcha_element")
    result["auth_signals_on_listing"] = auth

    # Collect all links on the listing page
    listing_links = page.eval_on_selector_all(
        "a[href]",
        "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80)}))"
    )
    result["listing_link_count"] = len(listing_links)
    result["listing_links_sample"] = listing_links[:30]

    # Find meeting entry links
    meeting_link_candidates = [
        lk for lk in listing_links
        if any(kw in lk["href"].lower() for kw in [
            "agendaid", "meetingid", "meeting.aspx", "agenda", "minutes"
        ])
    ]
    result["meeting_link_candidates_count"] = len(meeting_link_candidates)
    result["meeting_link_candidates"] = meeting_link_candidates[:10]
    log.info("[Ottawa] Meeting link candidates: %d", len(meeting_link_candidates))

    # Try clicking the first meeting
    click_selectors = [
        "a[href*='AgendaID']",
        "a[href*='MeetingID']",
        "a[href*='Meeting.aspx?']",
        "table a",
        "tbody tr:first-child a",
        "tbody tr td a",
    ]

    clicked_url = None
    for sel in click_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                href = el.get_attribute("href") or ""
                text = (el.inner_text() or "").strip()
                if href and "#" not in href[:5]:
                    log.info("[Ottawa] Clicking meeting via '%s': %r -> %r", sel, text[:50], href[:80])
                    page.click(sel)
                    page.wait_for_load_state("networkidle", timeout=30000)
                    page.wait_for_timeout(3000)
                    clicked_url = page.url
                    result["meeting_click_selector"] = sel
                    result["meeting_click_href"] = href
                    result["meeting_click_text"] = text[:80]
                    break
        except Exception as e:
            log.debug("[Ottawa] Selector '%s' failed: %s", sel, e)

    result["clicked_meeting"] = clicked_url is not None
    if clicked_url:
        result["meeting_page_url"] = clicked_url
        result["meeting_page_title"] = page.title()
        meeting_html = page.content()
        result["meeting_html_length"] = len(meeting_html)
        log.info("[Ottawa] Meeting detail: url=%s title=%r len=%d",
                 clicked_url, result["meeting_page_title"], len(meeting_html))

        page.screenshot(path="ottawa_meeting_detail.png", full_page=True)
        result["meeting_screenshot"] = "ottawa_meeting_detail.png"

        # Doc links
        meeting_links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80)}))"
        )
        doc_links = [
            lk for lk in meeting_links
            if any(ext in lk["href"].lower() for ext in [".pdf", ".doc", ".docx"])
            or any(kw in lk["href"].lower() for kw in ["document", "attachment", "download", "file"])
        ]
        result["doc_link_count"] = len(doc_links)
        result["doc_links"] = doc_links[:20]
        log.info("[Ottawa] Doc links on meeting detail: %d", len(doc_links))
        for lk in doc_links[:8]:
            log.info("  DOC: %r -> %r", lk["text"][:50], lk["href"][:100])

        # Auth re-check on meeting page
        auth2 = []
        if page.query_selector("input[type='password']"):
            auth2.append("password_field")
        if "sign in" in meeting_html.lower() or "log in" in meeting_html.lower():
            auth2.append("sign_in_text")
        if page.query_selector("[class*='captcha']"):
            auth2.append("captcha_element")
        result["auth_signals_on_meeting"] = auth2

        # Iframes
        iframes = page.eval_on_selector_all(
            "iframe",
            "els => els.map(f => f.src || f.getAttribute('data-src') || '')"
        )
        result["iframes"] = iframes

        # Navigation tabs / accordion
        tabs = page.eval_on_selector_all(
            "[role='tab'], .nav-tab, [data-toggle='tab'], [data-bs-toggle='tab']",
            "els => els.map(e => (e.innerText||'').trim().slice(0,50))"
        )
        result["nav_tabs"] = tabs

        # DOM structure for doc links
        doc_dom = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const href = a.href || '';
                if (href.match(/\\.pdf|\\.doc|attachment|download/i)) {
                    const parent = a.parentElement;
                    out.push({
                        href: href.slice(0, 120),
                        text: (a.innerText||'').trim().slice(0,60),
                        parent_tag: parent ? parent.tagName : '',
                        parent_class: parent ? parent.className : ''
                    });
                }
            });
            return out.slice(0, 15);
        }""")
        result["doc_dom_structure"] = doc_dom

    else:
        log.warning("[Ottawa] Could not click into a meeting entry")

    log.info("[Ottawa] Probe complete.")
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

    # Print compact summary for the workflow log
    print("\n" + "=" * 70)
    print("PROBE SUMMARY")
    print("=" * 70)

    for site_key, res in [("hamilton", hamilton), ("ottawa", ottawa)]:
        print(f"\n--- {res.get('site', site_key).upper()} ---")
        if "status" in res:
            print(f"  STATUS: {res['status']}")
            continue
        print(f"  Listing: {res.get('listing_url', res.get('wp_url', '?'))}")
        print(f"  Listing HTML length: {res.get('listing_html_length', res.get('escribe_html_length', '?'))}")
        print(f"  JS framework hints: {res.get('js_framework_hints', [])}")
        print(f"  Found meeting link: {res.get('found_meeting_link', res.get('clicked_meeting', '?'))}")
        print(f"  Meeting URL: {res.get('meeting_page_url', '(not clicked)')}")
        print(f"  Doc links on meeting page: {res.get('doc_link_count', 0)}")
        print(f"  Auth signals: {res.get('auth_signals', res.get('auth_signals_on_listing', []))}")
        print(f"  Iframes: {res.get('iframes', [])}")
        print(f"  Nav tabs: {res.get('nav_tabs', [])}")
        if res.get("doc_links"):
            print("  Doc link samples:")
            for lk in res["doc_links"][:5]:
                print(f"    {lk['text'][:40]:<40} {lk['href'][:80]}")
        if res.get("doc_dom_structure"):
            print("  Doc DOM structure (first 3):")
            for d in res["doc_dom_structure"][:3]:
                print(f"    <{d.get('parent_tag','')} class={d.get('parent_class','')[:30]!r}>"
                      f" <a href={d.get('href','')[:60]!r}> {d.get('text','')[:40]!r}")

    print("\n  Full findings: escribe_probe_findings.json")
    print("  Screenshots: hamilton_meeting.png, ottawa_escribe_listing.png, ottawa_meeting_detail.png")
    print("=" * 70)

    return findings


if __name__ == "__main__":
    main()
