"""
Hamilton HPSB search-submission probe.

Interaction probe (2026-08-08) confirmed:
  - Meeting list never renders passively (main_html stays 1893 chars)
  - Only interactive control: [data-toggle='collapse'] text='Expand Search'
  - No year tabs, no select elements, no lazy-load trigger found
  - Only XHR: member-auth check (GOVMemberSurface/GetMemberValue)

This probe focuses on the search flow:
  1. Expand search panel
  2. Dump form HTML (what fields exist, what the submit endpoint is)
  3. Submit the form (empty = show all)
  4. Capture resulting XHR + DOM changes
  5. If meeting items appear, navigate to first one and look for document links

Answers Q1: are document links visible after search submission?
Answers Q2: what is the search submission mechanism (XHR endpoint + params)?

Writes: hamilton_search_findings.json
Screenshots: hamilton_after_expand.png, hamilton_after_search.png, hamilton_meeting_detail.png
"""
import json
import logging
import re
import sys
import os
import urllib.robotparser

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

LISTING_URL = "https://www.hamiltonpsb.ca/meetings/agendas-and-materials/"
REAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

MEETING_CONTENT_SELECTORS = [
    "ul.listing li a",
    ".meetings-list a",
    ".agendas-list a",
    ".content-list a",
    "article a",
    ".document-list a",
    "table tbody tr a",
    ".list-group-item a",
    "[data-meeting] a",
    "[class*='meeting-item'] a",
    "[class*='agenda-item'] a",
    "li[class*='item'] a",
    ".node-item a",
    ".search-result a",
    ".results-list a",
    "[class*='result'] a",
    ".umbraco-list-item",
]

DOC_LINK_SELECTORS = [
    "a[href$='.pdf']",
    "a[href*='.pdf?']",
    "a[href*='document']",
    "a[href*='agenda']",
    "a[href*='minutes']",
    ".document-link",
    "[class*='doc'] a",
    "[class*='attach'] a",
]


def _robots_allowed(url: str) -> tuple[bool, str]:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as e:
        log.warning("robots.txt unreachable (%s) -- treating as allowed", e)
        return True, robots_url
    return rp.can_fetch("*", url), robots_url


def _count_nodes(page, selectors) -> int:
    total = 0
    for sel in selectors:
        try:
            n = page.eval_on_selector_all(sel, "els => els.length")
            if n:
                total += n
        except Exception:
            pass
    return total


def probe(page) -> dict:
    findings: dict = {
        "url": LISTING_URL,
        "robots": {},
        "xhr_log": [],
        "search_form": {},
        "meeting_nodes_after_search": 0,
        "meeting_links_found": [],
        "doc_links_on_detail": [],
        "search_xhr": [],
        "error": None,
    }

    allowed, robots_url = _robots_allowed(LISTING_URL)
    findings["robots"] = {"url": robots_url, "allowed": allowed}
    if not allowed:
        findings["error"] = "robots_blocked"
        log.error("robots.txt blocks %s", LISTING_URL)
        return findings
    log.info("robots.txt OK")

    xhr_log: list[dict] = []

    def on_request(req):
        if req.resource_type in ("xhr", "fetch"):
            entry = {"url": req.url, "method": req.method, "type": req.resource_type}
            xhr_log.append(entry)
            log.info("XHR  %s  %s", req.method, req.url)

    def on_response(resp):
        if resp.request.resource_type in ("xhr", "fetch"):
            # Try to capture response body for search-result XHRs
            url = resp.url
            if any(kw in url.lower() for kw in ["meeting", "agenda", "search", "getmeet", "surface"]):
                try:
                    body = resp.text()
                    log.info("XHR response (%d chars): %s", len(body), url)
                    # Find the matching entry and add body
                    for entry in xhr_log:
                        if entry["url"] == url and "body" not in entry:
                            entry["body_preview"] = body[:500]
                            break
                except Exception:
                    pass

    page.on("request", on_request)
    page.on("response", on_response)

    # --- Load page ---
    log.info("Loading %s", LISTING_URL)
    page.goto(LISTING_URL, wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(4000)
    log.info("Page loaded, main_html=%d",
             page.evaluate("() => { const m = document.querySelector('main'); return m ? m.innerHTML.length : 0; }"))

    # --- Step 1: Expand search panel ---
    log.info("Step 1: click 'Expand Search'")
    expand_btn = page.query_selector("[data-toggle='collapse']")
    if not expand_btn:
        expand_btn = page.query_selector("[data-bs-toggle='collapse']")
    if expand_btn:
        text = expand_btn.evaluate("el => (el.innerText || el.textContent || '').trim()")
        log.info("  Found collapse toggle: %r", text)
        expand_btn.click()
        page.wait_for_timeout(2000)
        page.screenshot(path="hamilton_after_expand.png")
        log.info("  Screenshot: hamilton_after_expand.png")
    else:
        log.warning("  No collapse toggle found -- form may already be visible")

    # --- Step 2: Dump search form ---
    log.info("Step 2: dump search form HTML")
    try:
        form_html = page.evaluate("""() => {
            const forms = document.querySelectorAll('form');
            return [...forms].map(f => ({
                action: f.action || '',
                method: f.method || '',
                html: f.outerHTML.slice(0, 2000),
            }));
        }""")
        findings["search_form"]["forms"] = form_html
        log.info("  Forms found: %d", len(form_html))
        for i, f in enumerate(form_html):
            log.info("  Form %d: action=%r method=%r", i, f.get("action",""), f.get("method",""))
            log.info("    HTML: %s", f.get("html","")[:400])
    except Exception as e:
        log.warning("Form dump error: %s", e)

    # Dump all inputs visible on page
    try:
        inputs = page.evaluate("""() => {
            return [...document.querySelectorAll('input, select, textarea, button[type="submit"], button[type="button"]')].map(el => ({
                tag: el.tagName,
                type: el.type || '',
                name: el.name || '',
                id: el.id || '',
                value: el.value || '',
                cls: (el.className||'').slice(0,60),
                text: (el.innerText||el.textContent||'').trim().slice(0,60),
                visible: el.offsetParent !== null,
            }));
        }""")
        findings["search_form"]["inputs"] = inputs
        log.info("  All inputs: %d", len(inputs))
        for inp in inputs:
            log.info("    <%s type=%r name=%r id=%r cls=%r text=%r visible=%s>",
                     inp["tag"], inp["type"], inp["name"], inp["id"],
                     inp["cls"], inp["text"], inp["visible"])
    except Exception as e:
        log.warning("Input dump error: %s", e)

    # --- Step 3: Find and click submit ---
    log.info("Step 3: find and click search submit")
    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button.search-submit",
        "button[class*='search']",
        "input[class*='search']",
        "form button",
        ".search-form button",
        ".search-panel button",
        "[class*='collapse'] button",
        "[class*='collapse'] input[type='submit']",
        "#collapseSearch button",
        "[id*='search'] button",
        "[id*='filter'] button",
    ]
    submitted = False
    for sel in submit_selectors:
        try:
            btns = page.query_selector_all(sel)
            if btns:
                log.info("  Submit candidate: %r -> %d elements", sel, len(btns))
                for btn in btns[:3]:
                    text = btn.evaluate("el => (el.innerText||el.textContent||el.value||'').trim().slice(0,60)")
                    visible = btn.evaluate("el => el.offsetParent !== null")
                    log.info("    text=%r visible=%s", text, visible)
                    if visible:
                        log.info("  Clicking: %r text=%r", sel, text)
                        btn.click()
                        page.wait_for_timeout(5000)
                        submitted = True
                        break
            if submitted:
                break
        except Exception as e:
            log.debug("  %r -> error: %s", sel, e)

    if not submitted:
        log.warning("No visible submit button found -- trying Enter key in search input")
        try:
            inp = page.query_selector("input[type='text'], input[type='search'], input[name*='search' i], input[placeholder*='search' i]")
            if inp:
                inp.press("Enter")
                page.wait_for_timeout(5000)
                submitted = True
        except Exception as e:
            log.warning("Enter-key fallback failed: %s", e)

    page.screenshot(path="hamilton_after_search.png")
    log.info("Screenshot: hamilton_after_search.png")

    # --- Step 4: Count meeting nodes after search ---
    main_len_after = page.evaluate(
        "() => { const m = document.querySelector('main'); return m ? m.innerHTML.length : 0; }"
    )
    n_after = _count_nodes(page, MEETING_CONTENT_SELECTORS)
    findings["meeting_nodes_after_search"] = n_after
    log.info("After search: main_html=%d chars, meeting nodes=%d", main_len_after, n_after)

    # Dump all links post-search
    try:
        all_links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80), parent_cls: a.parentElement ? (a.parentElement.className||'').slice(0,50) : ''}))"
        )
        log.info("Total links post-search: %d", len(all_links))
        # Filter to anything that looks like a meeting entry (deeper URL path than navigation)
        deep_links = [
            l for l in all_links
            if l["href"].startswith("https://www.hamiltonpsb.ca/")
            and l["href"].count("/") >= 5  # deeper than /meetings/agendas-and-materials/
        ]
        log.info("Deep links (possible meeting entries): %d", len(deep_links))
        for l in deep_links[:20]:
            log.info("  %r  text=%r  parent=%r", l["href"], l["text"], l["parent_cls"])
        findings["meeting_links_found"] = deep_links[:30]
    except Exception as e:
        log.warning("Link dump error: %s", e)

    # --- Step 5: Tag search-related XHR ---
    search_xhr = [x for x in xhr_log if any(kw in x["url"].lower() for kw in
                  ["meeting", "agenda", "search", "getmeet", "results", "filter"])]
    findings["search_xhr"] = search_xhr
    log.info("Search-related XHR: %d", len(search_xhr))
    for x in search_xhr:
        log.info("  %s  %s", x["method"], x["url"])
        if x.get("body_preview"):
            log.info("  body: %s", x["body_preview"][:200])

    # --- Step 6: Navigate to first deep link (potential meeting detail) ---
    deep = findings.get("meeting_links_found", [])
    if deep:
        detail_url = deep[0]["href"]
        log.info("Step 6: navigate to first meeting detail: %s", detail_url)
        page.goto(detail_url, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(3000)
        page.screenshot(path="hamilton_meeting_detail.png")
        doc_links = page.eval_on_selector_all(
            "a[href]",
            "els => els.filter(a => a.href.endsWith('.pdf') || a.href.includes('.pdf?') || a.href.includes('document') || a.href.includes('agenda') || a.href.includes('minutes')).map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80)}))"
        )
        log.info("Document links on detail page: %d", len(doc_links))
        for dl in doc_links[:10]:
            log.info("  %r -> %r", dl["href"], dl["text"])
        findings["doc_links_on_detail"] = doc_links[:20]
    else:
        log.info("Step 6: no deep links found to navigate to")

    findings["xhr_log"] = xhr_log
    return findings


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=[
            "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
        ])
        ctx = browser.new_context(
            user_agent=REAL_UA,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()
        findings = probe(page)
        page.close()
        browser.close()

    out = "hamilton_search_findings.json"
    with open(out, "w") as fh:
        json.dump(findings, fh, indent=2)
    log.info("Findings -> %s", out)

    print("\n=== HAMILTON SEARCH PROBE SUMMARY ===")
    print(f"Robots: {findings['robots'].get('allowed')}")
    if findings.get("error"):
        print(f"ERROR: {findings['error']}")
        return
    print(f"\nSearch-related XHR ({len(findings['search_xhr'])}):")
    for x in findings["search_xhr"]:
        print(f"  {x['method']}  {x['url']}")
        if x.get("body_preview"):
            print(f"  body: {x['body_preview'][:200]}")
    print(f"\nMeeting nodes after search: {findings['meeting_nodes_after_search']}")
    deep = findings.get("meeting_links_found", [])
    print(f"\nDeep links (meeting entries): {len(deep)}")
    for l in deep[:10]:
        print(f"  {l['href']}")
        print(f"    {l['text']!r}")
    docs = findings.get("doc_links_on_detail", [])
    print(f"\nDocument links on detail page: {len(docs)}")
    for d in docs[:10]:
        print(f"  {d['href']}  {d['text']!r}")
    forms = findings.get("search_form", {}).get("forms", [])
    print(f"\nForms ({len(forms)}):")
    for f in forms:
        print(f"  action={f.get('action')!r}  method={f.get('method')!r}")


if __name__ == "__main__":
    main()
