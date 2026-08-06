"""Diagnostic probe for Hamilton PSB (hamiltonpsb.ca) agendas listing.

The listing page is JS-rendered (Umbraco CMS). This probe renders it with
Playwright and dumps the raw HTML structure and all links so we can write
accurate selectors for the Playwright adapter.

    python scripts/probe_hamiltonpsb.py
"""
import logging
import re
import sys
import os

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

MEETING_URL_RE = re.compile(
    r'href=["\']([^"\']*(?:meeting|agenda|minutes|board)[^"\']*)["\']', re.I
)
PDF_URL_RE = re.compile(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', re.I)
LINK_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)


def probe(page) -> None:
    log.info("Loading %s", LISTING_URL)
    page.goto(LISTING_URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    html = page.content()
    log.info("Page loaded: %d chars of HTML", len(html))

    # All <a> links on the page
    all_links = page.eval_on_selector_all("a[href]", "els => els.map(a => [a.href, (a.innerText||'').trim().slice(0,80)])")
    log.info("Total <a> tags: %d", len(all_links))
    for href, text in all_links[:30]:
        log.info("  LINK: %r -> %r", href, text)
    if len(all_links) > 30:
        log.info("  ... (%d more links)", len(all_links) - 30)

    # PDF links specifically
    pdf_links = [(h, t) for h, t in all_links if h.lower().endswith(".pdf") or ".pdf?" in h.lower()]
    log.info("PDF links found: %d", len(pdf_links))
    for href, text in pdf_links[:10]:
        log.info("  PDF: %r -> %r", href, text)

    # Try common listing selectors
    for sel in [
        "ul.listing li a", ".meetings-list a", ".agendas-list a",
        ".content-list a", "article a", ".document-list a",
        "table a", ".accordion a", ".panel a", ".list-group-item a",
    ]:
        try:
            found = page.eval_on_selector_all(sel, "els => els.map(a => [a.href, (a.innerText||'').trim().slice(0,60)])")
            if found:
                log.info("Selector %r matched %d items:", sel, len(found))
                for href, text in found[:5]:
                    log.info("    %r -> %r", href, text)
        except Exception:
            pass

    # Dump a condensed DOM outline (tag + class + first 80 chars of text for elements with links)
    structure = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('main *').forEach(el => {
            if (el.querySelectorAll('a').length > 0) {
                out.push({
                    tag: el.tagName,
                    cls: el.className,
                    text: (el.innerText || '').trim().slice(0, 80)
                });
            }
        });
        return out.slice(0, 40);
    }""")
    log.info("DOM elements containing links (first 40):")
    for item in structure:
        log.info("  <%s class=%r> %r", item["tag"], item["cls"], item["text"])

    # Check if a year selector / filter exists
    selects = page.eval_on_selector_all("select", "els => els.map(s => [s.name||s.id, [...s.options].map(o => o.value).slice(0,6)])")
    if selects:
        log.info("SELECT elements found: %r", selects)

    log.info("Probe complete.")


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(user_agent=REAL_UA, viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        probe(page)
        page.close()
        browser.close()


if __name__ == "__main__":
    main()
