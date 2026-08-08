"""
Hamilton PSB agendas-and-minutes probe.

Operator question (2026-08-08): Does hamiltonpsb.ca/meetings/agendas-and-minutes/
host direct PDFs (London pattern) or does it link out to the eScribe JS-shell?
If PDFs are directly hosted, Hamilton can collect without a render adapter.

Reports:
  - robots.txt status
  - Whether page is static HTML or JS-rendered
  - Document candidate count
  - PDF links (href, HEAD status, resolved URL)
  - eScribe links (escribemeetings.com)
  - URL structure of any PDF or document links

Read-only. Robots discipline enforced.
Writes: hamilton_agendas_minutes_findings.json
"""
import json
import logging
import re
import sys
import os
import urllib.robotparser

import requests
from urllib.parse import urlparse, urljoin

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TARGET_URL = "https://hamiltonpsb.ca/meetings/agendas-and-minutes/"
REAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

ESCRIBE_PATTERNS = ["escribemeetings.com", "eScribe", "Meeting.aspx", "civicweb.net"]
PDF_PATTERNS = [r'\.pdf$', r'\.pdf\?', r'\.pdf#']


def _robots_allowed(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as e:
        log.warning("robots.txt unreachable (%s) -- treating as allowed", e)
        return True, robots_url
    allowed = rp.can_fetch("*", url)
    return allowed, robots_url


def _is_pdf_link(href: str) -> bool:
    return bool(re.search(r'\.pdf($|\?|#)', href, re.I))


def _is_escribe(href: str) -> bool:
    return any(p.lower() in href.lower() for p in ESCRIBE_PATTERNS)


def _head_check(session: requests.Session, url: str) -> dict:
    try:
        r = session.head(url, timeout=15, allow_redirects=True)
        return {
            "status": r.status_code,
            "content_type": r.headers.get("Content-Type", ""),
            "content_length": r.headers.get("Content-Length", ""),
            "final_url": r.url,
        }
    except Exception as e:
        return {"status": None, "error": str(e)}


def probe_static(session: requests.Session) -> dict | None:
    """Try fetching with plain requests. Returns None if page looks JS-rendered."""
    try:
        r = session.get(TARGET_URL, timeout=30)
        r.raise_for_status()
        html = r.text
        log.info("Static fetch: HTTP %d, %d chars", r.status_code, len(html))

        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.S | re.I)
        body_text = body_match.group(1) if body_match else html
        text_len = len(re.sub(r'<[^>]+>', '', body_text))
        log.info("  Body text length (tags stripped): %d chars", text_len)

        return {"html": html, "html_len": len(html), "text_len": text_len, "status": r.status_code}
    except Exception as e:
        log.warning("Static fetch error: %s", e)
        return None


def extract_links(html: str, base_url: str) -> dict:
    """Extract all hrefs, classify as PDF / eScribe / other."""
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
    abs_hrefs = []
    for h in hrefs:
        if h.startswith("http"):
            abs_hrefs.append(h)
        elif h.startswith("/"):
            parsed = urlparse(base_url)
            abs_hrefs.append(f"{parsed.scheme}://{parsed.netloc}{h}")

    pdf_links = [h for h in abs_hrefs if _is_pdf_link(h)]
    escribe_links = [h for h in abs_hrefs if _is_escribe(h)]
    doc_links = [h for h in abs_hrefs if any(kw in h.lower() for kw in
                  ["agenda", "minutes", "document", "report", "bylaw"])]

    return {
        "total_hrefs": len(abs_hrefs),
        "pdf_links": pdf_links,
        "escribe_links": escribe_links,
        "doc_keyword_links": doc_links[:40],
    }


def probe_playwright(findings: dict) -> None:
    """Playwright fallback for JS-rendered pages."""
    log.info("Falling back to Playwright (JS-rendered page suspected)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("Playwright not available")
        findings["playwright_error"] = "not_installed"
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(args=[
            "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
        ])
        ctx = browser.new_context(
            user_agent=REAL_UA,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()

        xhr_log: list[dict] = []

        def on_request(req):
            if req.resource_type in ("xhr", "fetch"):
                xhr_log.append({"url": req.url, "method": req.method})
                log.info("XHR %s %s", req.method, req.url)

        page.on("request", on_request)

        log.info("Playwright: loading %s", TARGET_URL)
        page.goto(TARGET_URL, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(4000)

        html = page.content()
        main_len = page.evaluate(
            "() => { const m = document.querySelector('main,#main,.main-content'); "
            "return m ? m.innerHTML.length : document.body.innerHTML.length; }"
        )
        log.info("  main_html=%d chars after networkidle+4s", main_len)

        page.screenshot(path="hamilton_agendas_minutes.png")

        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,100)}))"
        )
        log.info("  Total links in rendered DOM: %d", len(links))

        pdf_links = [l for l in links if _is_pdf_link(l["href"])]
        escribe_links = [l for l in links if _is_escribe(l["href"])]
        doc_links = [l for l in links if any(kw in l["href"].lower() for kw in
                      ["agenda", "minutes", "document", "report", "/media/"])]

        log.info("  PDF links: %d", len(pdf_links))
        log.info("  eScribe links: %d", len(escribe_links))
        log.info("  Doc-keyword links: %d", len(doc_links))

        for l in pdf_links[:10]:
            log.info("    PDF: %s  %r", l["href"], l["text"])
        for l in escribe_links[:10]:
            log.info("    eScribe: %s  %r", l["href"], l["text"])
        for l in doc_links[:10]:
            log.info("    Doc: %s  %r", l["href"], l["text"])

        findings["playwright"] = {
            "main_html_len": main_len,
            "total_links": len(links),
            "pdf_links": [l["href"] for l in pdf_links],
            "pdf_links_with_text": pdf_links[:20],
            "escribe_links": [l["href"] for l in escribe_links],
            "doc_keyword_links": doc_links[:30],
            "xhr_log": xhr_log,
        }

        page.close()
        browser.close()


def main():
    findings: dict = {
        "url": TARGET_URL,
        "robots": {},
        "static_fetch": {},
        "links": {},
        "pdf_head_checks": [],
        "verdict": None,
        "error": None,
    }

    allowed, robots_url = _robots_allowed(TARGET_URL)
    findings["robots"] = {"url": robots_url, "allowed": allowed}
    log.info("robots.txt %s -> can_fetch=%s", robots_url, allowed)
    if not allowed:
        findings["error"] = "robots_blocked"
        findings["verdict"] = "robots_blocked -- stop"
        _save_and_print(findings)
        return

    session = requests.Session()
    session.headers["User-Agent"] = REAL_UA

    static = probe_static(session)
    if static:
        findings["static_fetch"] = {
            "status": static["status"],
            "html_len": static["html_len"],
            "text_len": static["text_len"],
        }

        links = extract_links(static["html"], TARGET_URL)
        findings["links"] = links

        log.info("Links: total=%d pdf=%d escribe=%d doc_kw=%d",
                 links["total_hrefs"], len(links["pdf_links"]),
                 len(links["escribe_links"]), len(links["doc_keyword_links"]))
        for h in links["pdf_links"][:10]:
            log.info("  PDF: %s", h)
        for h in links["escribe_links"][:10]:
            log.info("  eScribe: %s", h)
        for h in links["doc_keyword_links"][:10]:
            log.info("  DocKW: %s", h)

        if static["text_len"] < 500 and not links["pdf_links"] and not links["escribe_links"]:
            log.info("Page text very short (%d chars), likely JS-rendered", static["text_len"])
            probe_playwright(findings)
        elif not links["pdf_links"] and not links["escribe_links"]:
            log.info("No PDF or eScribe links in static HTML, trying Playwright")
            probe_playwright(findings)
    else:
        probe_playwright(findings)

    all_pdf = (
        findings.get("links", {}).get("pdf_links", []) or
        findings.get("playwright", {}).get("pdf_links", [])
    )
    log.info("HEAD-checking up to 5 PDF links")
    for url in all_pdf[:5]:
        result = _head_check(session, url)
        result["url"] = url
        findings["pdf_head_checks"].append(result)
        log.info("  HEAD %s -> %s %s", url, result.get("status"), result.get("content_type", ""))

    pw = findings.get("playwright", {})
    lk = findings.get("links", {})
    pdf_count = len(all_pdf)
    escribe_count = len(lk.get("escribe_links", [])) + len(pw.get("escribe_links", []))
    head_ok = [h for h in findings["pdf_head_checks"] if h.get("status") == 200]

    if pdf_count > 0 and head_ok:
        findings["verdict"] = (
            f"DIRECT_PDFS: {pdf_count} PDF links found, "
            f"{len(head_ok)}/{len(findings['pdf_head_checks'])} HEAD 200. "
            "London pattern -- collect without render adapter."
        )
    elif pdf_count > 0:
        findings["verdict"] = (
            f"PDF_LINKS_FOUND ({pdf_count}) but HEAD checks failed or not run. "
            "Investigate URL accessibility."
        )
    elif escribe_count > 0:
        findings["verdict"] = (
            f"ESCRIBE_SHELL: {escribe_count} eScribe links found, zero direct PDFs. "
            "Render adapter required."
        )
    else:
        main_len = pw.get("main_html_len", findings["static_fetch"].get("html_len", 0))
        findings["verdict"] = (
            f"NO_DOCS: zero PDF and zero eScribe links. "
            f"main_html={main_len} chars. "
            "Page may be empty / auth-gated / wrong URL."
        )

    log.info("VERDICT: %s", findings["verdict"])
    _save_and_print(findings)


def _save_and_print(findings: dict) -> None:
    out = "hamilton_agendas_minutes_findings.json"
    with open(out, "w") as fh:
        json.dump(findings, fh, indent=2)
    log.info("Findings -> %s", out)

    print("\n=== HAMILTON AGENDAS-AND-MINUTES PROBE ===")
    print(f"URL    : {findings['url']}")
    print(f"Robots : {findings['robots']}")
    if findings.get("error"):
        print(f"ERROR  : {findings['error']}")
        return

    sf = findings.get("static_fetch", {})
    if sf:
        print(f"Static : HTTP {sf.get('status')}, html={sf.get('html_len')} chars, "
              f"text={sf.get('text_len')} chars")

    lk = findings.get("links", {})
    pw = findings.get("playwright", {})
    pdf_links = lk.get("pdf_links", []) or pw.get("pdf_links", [])
    escribe_links = lk.get("escribe_links", []) or pw.get("escribe_links", [])
    doc_links = lk.get("doc_keyword_links", []) or pw.get("doc_keyword_links", [])

    print(f"\nPDF links  ({len(pdf_links)}):")
    for h in pdf_links[:15]:
        print(f"  {h}")

    print(f"\neScribe links ({len(escribe_links)}):")
    for h in escribe_links[:10]:
        print(f"  {h}")

    print(f"\nDoc-keyword links ({len(doc_links)}):")
    for d in doc_links[:10]:
        if isinstance(d, dict):
            print(f"  {d.get('href','')}  {d.get('text','')!r}")
        else:
            print(f"  {d}")

    print(f"\nHEAD checks:")
    for h in findings.get("pdf_head_checks", []):
        print(f"  HTTP {h.get('status')}  {h.get('url')}  [{h.get('content_type','')}]")

    print(f"\nVERDICT: {findings.get('verdict')}")


if __name__ == "__main__":
    main()
