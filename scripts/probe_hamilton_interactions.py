"""
Hamilton HPSB interaction probe.

The static DOM probe (probe_escribe_render.py, run 2026-08-08) showed that
the meeting list on hamiltonpsb.ca/meetings/agendas-and-materials/ does NOT
render passively after networkidle. The only XHR captured was a member-auth
check (GOVMemberSurface/GetMemberValue). This probe tries common Umbraco
listing interaction patterns to find what triggers the data to load:

  Stage 0 -- initial load + XHR intercept
  Stage 1 -- scroll to bottom (lazy-load)
  Stage 2 -- click any year/filter/tab/accordion buttons
  Stage 3 -- interact with <select> elements
  Stage 4 -- dump all links + Umbraco API refs from page source

Findings written to hamilton_interaction_findings.json.
Screenshot written to hamilton_final_state.png.
Run with: python scripts/probe_hamilton_interactions.py
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

# Selectors that would indicate meeting list content is present
MEETING_CONTENT_SELECTORS = [
    "ul.listing li a",
    ".meetings-list a",
    ".agendas-list a",
    ".content-list a",
    "article a",
    ".document-list a",
    "table tbody tr a",
    ".accordion .panel a",
    ".list-group-item a",
    "[data-meeting] a",
    "[class*='meeting'] a",
    "[class*='agenda'] a",
    "li[class*='item'] a",
    ".node-item a",
    ".umbraco-list-item",
    "a[href*='/meetings/'][href*='.ca/meetings/']",
    "a[href*='meeting-']",
]

# Selectors to probe for interactive controls that might trigger a load
CONTROL_SELECTORS = [
    "button[data-year]",
    "a[data-year]",
    "[class*='year'] button",
    "[class*='year'] a",
    "[class*='filter'] button",
    "[class*='filter'] a",
    "nav.tabs a",
    ".tab-nav a",
    ".nav-tabs a",
    "[role='tab']",
    "[aria-label*='year' i]",
    "[aria-controls*='year' i]",
    "button[class*='tab']",
    ".accordion-toggle",
    ".panel-heading a",
    "[data-toggle='collapse']",
    "[data-toggle='tab']",
    "[data-bs-toggle='tab']",
    "[data-bs-toggle='collapse']",
    "button[class*='filter']",
    "a[class*='filter']",
    ".btn-group button",
    # Broader fallbacks
    "main button",
    "main [role='button']",
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
    allowed = rp.can_fetch("*", url)
    return allowed, robots_url


def _count_meeting_nodes(page) -> int:
    total = 0
    for sel in MEETING_CONTENT_SELECTORS:
        try:
            count = page.eval_on_selector_all(sel, "els => els.length")
            if count:
                total += count
        except Exception:
            pass
    return total


def _dom_snapshot(page, label: str) -> dict:
    try:
        main_len = page.evaluate(
            "() => { const m = document.querySelector('main'); return m ? m.innerHTML.length : document.body.innerHTML.length; }"
        )
        interactive = page.evaluate("""() => {
            const out = [];
            const root = document.querySelector('main') || document.body;
            root.querySelectorAll('a, button, [role="tab"], [role="button"], select').forEach(el => {
                const text = (el.innerText || el.textContent || el.value || '').trim().slice(0, 100);
                if (!text) return;
                out.push({
                    tag: el.tagName,
                    cls: (el.className || '').slice(0, 80),
                    href: el.href || null,
                    text: text,
                    role: el.getAttribute('role'),
                    'data-year': el.getAttribute('data-year'),
                    'data-filter': el.getAttribute('data-filter'),
                    'data-toggle': el.getAttribute('data-toggle') || el.getAttribute('data-bs-toggle'),
                });
            });
            return out.slice(0, 120);
        }""")
        selects = page.eval_on_selector_all(
            "select",
            "els => els.map(s => ({name: s.name||s.id||'', options: [...s.options].map(o => ({val: o.value, text: o.text.trim()})).slice(0,10)}))"
        )
        return {
            "label": label,
            "main_html_len": main_len,
            "interactive_nodes": interactive,
            "select_elements": selects,
        }
    except Exception as e:
        return {"label": label, "error": str(e)}


def probe_hamilton(page) -> dict:
    findings: dict = {
        "url": LISTING_URL,
        "robots": {},
        "xhr_requests": [],
        "stages": [],
        "meeting_nodes_by_stage": {},
        "all_links_count": 0,
        "meeting_links": [],
        "umbraco_api_refs": [],
        "error": None,
    }

    # --- robots.txt ---
    allowed, robots_url = _robots_allowed(LISTING_URL)
    findings["robots"] = {"url": robots_url, "allowed": allowed}
    if not allowed:
        log.error("robots.txt BLOCKS %s -- halting", LISTING_URL)
        findings["error"] = "robots_blocked"
        return findings
    log.info("robots.txt OK for %s", LISTING_URL)

    # --- XHR intercept ---
    xhr_log: list[dict] = []

    def on_request(req):
        if req.resource_type in ("xhr", "fetch"):
            entry = {"url": req.url, "method": req.method, "type": req.resource_type}
            xhr_log.append(entry)
            log.info("XHR  %s  %s", req.method, req.url)

    page.on("request", on_request)

    # ------------------------------------------------------------------ #
    # Stage 0: initial load
    # ------------------------------------------------------------------ #
    log.info("=== Stage 0: initial load ===")
    page.goto(LISTING_URL, wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(5000)
    snap0 = _dom_snapshot(page, "stage0_initial")
    findings["stages"].append(snap0)
    n0 = _count_meeting_nodes(page)
    findings["meeting_nodes_by_stage"]["stage0_initial"] = n0
    log.info("Stage 0: %d meeting nodes  main_html=%d chars", n0, snap0.get("main_html_len", 0))

    # ------------------------------------------------------------------ #
    # Stage 1: scroll to bottom (lazy-load trigger)
    # ------------------------------------------------------------------ #
    log.info("=== Stage 1: scroll to bottom ===")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(4000)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(3000)
    snap1 = _dom_snapshot(page, "stage1_scroll_bottom")
    findings["stages"].append(snap1)
    n1 = _count_meeting_nodes(page)
    findings["meeting_nodes_by_stage"]["stage1_scroll"] = n1
    log.info("Stage 1: %d meeting nodes  main_html=%d chars", n1, snap1.get("main_html_len", 0))

    # ------------------------------------------------------------------ #
    # Stage 2: click interactive controls (year tabs, filters, accordions)
    # ------------------------------------------------------------------ #
    log.info("=== Stage 2: click controls ===")
    best_n = n1
    for sel in CONTROL_SELECTORS:
        try:
            els = page.query_selector_all(sel)
            if not els:
                continue
            log.info("  %r -> %d elements", sel, len(els))
            # Log what we found
            for el in els[:4]:
                try:
                    text = el.evaluate("el => (el.innerText || el.textContent || '').trim().slice(0, 60)")
                    log.info("    text=%r", text)
                except Exception:
                    pass
            # Click the first (or second if first is a nav header)
            target = els[1] if len(els) > 1 and sel in ("main button", "main [role='button']") else els[0]
            target.scroll_into_view_if_needed()
            target.click()
            page.wait_for_timeout(4000)
            n = _count_meeting_nodes(page)
            snap = _dom_snapshot(page, f"stage2_{sel[:50]}")
            findings["stages"].append(snap)
            findings["meeting_nodes_by_stage"][f"stage2_{sel[:50]}"] = n
            log.info("  After click %r: %d meeting nodes  main_html=%d", sel, n, snap.get("main_html_len", 0))
            if n > best_n:
                log.info("  *** IMPROVEMENT: %d -> %d nodes after clicking %r ***", best_n, n, sel)
                best_n = n
            if n > 5:
                log.info("  *** THRESHOLD MET: %d nodes. Stopping control search. ***", n)
                break
        except Exception as e:
            log.debug("  %r -> error: %s", sel, e)

    # ------------------------------------------------------------------ #
    # Stage 3: interact with <select> elements
    # ------------------------------------------------------------------ #
    log.info("=== Stage 3: select elements ===")
    try:
        selects = page.query_selector_all("select")
        log.info("  Found %d <select> elements", len(selects))
        for sel_el in selects[:3]:
            name = sel_el.evaluate("s => s.name || s.id || '(unnamed)'")
            opts = sel_el.evaluate("s => [...s.options].map(o => o.value)")
            log.info("  SELECT %r opts=%r", name, opts[:8])
            if len(opts) > 1:
                choice = opts[1]
                sel_el.select_option(choice)
                page.wait_for_timeout(4000)
                n = _count_meeting_nodes(page)
                snap = _dom_snapshot(page, f"stage3_select_{name[:30]}")
                findings["stages"].append(snap)
                findings["meeting_nodes_by_stage"][f"stage3_select_{name[:30]}"] = n
                log.info("  After select %r=%r: %d nodes", name, choice, n)
    except Exception as e:
        log.warning("Stage 3 error: %s", e)

    # ------------------------------------------------------------------ #
    # Stage 4: link dump + Umbraco API ref extraction
    # ------------------------------------------------------------------ #
    log.info("=== Stage 4: link dump + page source analysis ===")
    try:
        all_links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(a => ({href: a.href, text: (a.innerText||'').trim().slice(0,80), parent_cls: a.parentElement ? (a.parentElement.className||'').slice(0,50) : ''}))"
        )
        findings["all_links_count"] = len(all_links)
        log.info("Total <a href> links: %d", len(all_links))

        # Meeting links: URL contains meeting-related keywords AND is not same-page anchor
        meeting_links = [
            l for l in all_links
            if any(kw in l["href"].lower() for kw in ["meeting", "agenda", "minutes", "board"])
            and not l["href"].endswith("#")
            and "#" not in l["href"].split("hamiltonpsb.ca")[-1]
        ]
        findings["meeting_links"] = meeting_links[:30]
        log.info("Meeting-like links: %d", len(meeting_links))
        for l in meeting_links[:15]:
            log.info("  %r  text=%r  parent=%r", l["href"], l["text"], l["parent_cls"])
    except Exception as e:
        log.warning("Stage 4 link dump error: %s", e)

    try:
        page_source = page.content()
        umbraco_refs = sorted(set(re.findall(r'/umbraco/[^\s"\'\'<>?#]+', page_source)))
        findings["umbraco_api_refs"] = umbraco_refs[:40]
        log.info("Umbraco API refs in page source: %d unique", len(umbraco_refs))
        for r in umbraco_refs[:20]:
            log.info("  %s", r)
    except Exception as e:
        log.warning("Stage 4 source analysis error: %s", e)

    findings["xhr_requests"] = xhr_log
    log.info("XHR total: %d", len(xhr_log))
    return findings


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ])
        ctx = browser.new_context(
            user_agent=REAL_UA,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()
        findings = probe_hamilton(page)
        page.screenshot(path="hamilton_final_state.png")
        page.close()
        browser.close()

    out_path = "hamilton_interaction_findings.json"
    with open(out_path, "w") as fh:
        json.dump(findings, fh, indent=2)
    log.info("Findings -> %s", out_path)

    # Compact terminal summary
    print("\n=== HAMILTON INTERACTION PROBE SUMMARY ===")
    print(f"Robots allowed: {findings['robots'].get('allowed')}")
    if findings.get("error"):
        print(f"ERROR: {findings['error']}")
        return

    print(f"\nXHR requests ({len(findings['xhr_requests'])}):")
    for x in findings["xhr_requests"]:
        print(f"  {x['method']}  {x['url']}")

    print("\nMeeting nodes by stage:")
    for stage, count in findings["meeting_nodes_by_stage"].items():
        mark = " <-- CONTENT FOUND" if count > 0 else ""
        print(f"  {stage}: {count}{mark}")

    links = findings.get("meeting_links", [])
    print(f"\nMeeting-like links ({len(links)}):")
    for l in links[:15]:
        print(f"  {l['href']}")
        print(f"    text={l['text']!r}  parent={l['parent_cls']!r}")

    refs = findings.get("umbraco_api_refs", [])
    print(f"\nUmbraco API refs in page source ({len(refs)}):")
    for r in refs[:20]:
        print(f"  {r}")


if __name__ == "__main__":
    main()
