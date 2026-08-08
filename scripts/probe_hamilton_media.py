"""
Hamilton HPSB media URL pattern probe.

Operator ruling 2026-08-08: probe the /media/... URL pattern before parking.
The auth-gated listing does not necessarily mean the documents are gated.

Approach:
  1. Extract media URL structure from the publicly-accessible policies page
     (45 PDFs at /media/... confirmed by search probe)
  2. HEAD a sample of those URLs to confirm they are publicly accessible
  3. Check sitemap.xml / sitemap_index.xml for /media/ entries with
     agenda / minutes / meeting keywords
  4. Fetch the meetings listing page (1,893 chars for anon) and scan for
     any embedded media references or JS constants
  5. Try a handful of known Umbraco anonymous API paths for media content
  6. Verdict: discoverable? accessible? or park?

Read-only: no logins, no form submissions, no DB writes.
Robots discipline enforced -- aborts if robots.txt disallows the base URL.

Writes: hamilton_media_findings.json
"""
import json
import logging
import re
import sys
import os
import urllib.robotparser

import requests
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "https://www.hamiltonpsb.ca"
POLICIES_PATH = "/reports-plans-policies/policies-and-by-laws/"
MEETINGS_PATH = "/meetings/agendas-and-materials/"
REAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


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
    return rp.can_fetch("*", url), robots_url


def probe() -> dict:
    findings: dict = {
        "base_url": BASE_URL,
        "robots": {},
        "media_url_pattern": {},
        "sample_head_results": [],
        "sitemap_entries": [],
        "meetings_page_media_refs": {},
        "umbraco_api_results": {},
        "verdict": None,
        "error": None,
    }

    allowed, robots_url = _robots_allowed(BASE_URL + POLICIES_PATH)
    findings["robots"] = {"url": robots_url, "allowed": allowed}
    if not allowed:
        findings["error"] = "robots_blocked"
        log.error("robots.txt blocks %s", BASE_URL)
        return findings
    log.info("robots.txt OK")

    session = requests.Session()
    session.headers["User-Agent"] = REAL_UA

    # --- Stage 1: media URL pattern from policies page ---
    log.info("Stage 1: extract media URL pattern from policies page")
    abs_media: list[str] = []
    try:
        resp = session.get(BASE_URL + POLICIES_PATH, timeout=30)
        resp.raise_for_status()
        html = resp.text
        media_hrefs = re.findall(r'href="(/media/[^"]+)"', html)
        abs_media = [BASE_URL + h for h in media_hrefs]
        log.info("  /media/ hrefs on policies page: %d", len(media_hrefs))

        id_pattern = re.compile(r"/media/(\d+)/")
        uuid_pattern = re.compile(
            r"/media/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/", re.I
        )
        ids_int = sorted({int(m.group(1)) for h in media_hrefs if (m := id_pattern.search(h))})
        ids_uuid = [m.group(1) for h in media_hrefs if (m := uuid_pattern.search(h))]
        filenames = [h.split("/")[-1] for h in media_hrefs]

        findings["media_url_pattern"] = {
            "sample_hrefs": media_hrefs[:10],
            "total_found": len(media_hrefs),
            "id_type": "integer" if ids_int else ("uuid" if ids_uuid else "unknown"),
            "integer_ids": ids_int[:30],
            "id_range": [min(ids_int), max(ids_int)] if ids_int else None,
            "uuid_ids": ids_uuid[:5],
            "sample_filenames": filenames[:10],
        }
        for h in media_hrefs[:5]:
            log.info("  %s", h)
        if ids_int:
            log.info("  Integer IDs: min=%d max=%d count=%d", min(ids_int), max(ids_int), len(ids_int))
    except Exception as e:
        log.warning("Stage 1 error: %s", e)
        findings["error"] = str(e)

    # --- Stage 2: HEAD sample media URLs ---
    log.info("Stage 2: HEAD sample media URLs")
    for url in abs_media[:6]:
        try:
            r = session.head(url, timeout=15, allow_redirects=True)
            entry = {
                "url": url,
                "status": r.status_code,
                "content_type": r.headers.get("Content-Type", ""),
                "content_length": r.headers.get("Content-Length", ""),
            }
            findings["sample_head_results"].append(entry)
            log.info("  HEAD %s -> %d %s", url, r.status_code, entry["content_type"])
        except Exception as e:
            log.warning("  HEAD %s -> error: %s", url, e)

    # --- Stage 3: sitemap ---
    log.info("Stage 3: sitemap scan")
    for path in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap/"]:
        try:
            r = session.get(BASE_URL + path, timeout=20)
            if r.status_code != 200:
                log.info("  %s -> HTTP %d", path, r.status_code)
                continue
            log.info("  %s -> HTTP 200, %d chars", path, len(r.text))
            # Entries whose URL contains agenda/minutes/meeting
            kw_entries = re.findall(
                r"<loc>([^<]*(?:agenda|minutes|meeting)[^<]*)</loc>", r.text, re.I
            )
            # All /media/ entries
            media_entries = re.findall(r"<loc>([^<]*/media/[^<]+)</loc>", r.text)
            log.info(
                "  Keyword entries (agenda/minutes/meeting): %d, /media/ entries: %d",
                len(kw_entries), len(media_entries),
            )
            for e in kw_entries[:20]:
                log.info("    KW: %s", e)
            for e in media_entries[:5]:
                log.info("    MEDIA: %s", e)
            findings["sitemap_entries"].extend(kw_entries[:50])
            if media_entries:
                findings["sitemap_entries"].extend(media_entries[:50])
        except Exception as e:
            log.info("  %s -> error: %s", path, e)

    # --- Stage 4: meetings page source ---
    log.info("Stage 4: meetings page source for embedded media refs")
    try:
        r = session.get(BASE_URL + MEETINGS_PATH, timeout=30)
        r.raise_for_status()
        html = r.text
        media_refs = re.findall(r'["\']?(/media/[^\s"\'<>]+)', html)
        js_media = re.findall(r'["\'](/media/\d+/[^"\']+)["\']', html)
        # Look for any mention of media IDs or API endpoints in JS
        api_hints = re.findall(r'["\']([^"\']*(?:GetMeet|getAgenda|getDocument|mediaId)[^"\']*)["\']', html, re.I)
        log.info(
            "  Meetings page: %d chars, media_refs=%d, js_media=%d, api_hints=%d",
            len(html), len(media_refs), len(js_media), len(api_hints),
        )
        findings["meetings_page_media_refs"] = {
            "page_size": len(html),
            "media_refs": media_refs[:20],
            "js_media": js_media[:20],
            "api_hints": api_hints[:10],
        }
    except Exception as e:
        log.warning("Stage 4 error: %s", e)

    # --- Stage 5: Umbraco anonymous API endpoints ---
    log.info("Stage 5: Umbraco anonymous API paths")
    umbraco_paths = [
        "/umbraco/api/content/getchildren?id=1&pageSize=100",
        "/umbraco/api/media/getChildren?id=-1",
        "/umbraco/surface/MeetingsSurface/GetMeetings",
        "/umbraco/surface/MediaSurface/GetDocuments",
        "/api/meetings",
        "/api/documents",
    ]
    for path in umbraco_paths:
        try:
            r = session.get(BASE_URL + path, timeout=15)
            entry = {
                "status": r.status_code,
                "content_type": r.headers.get("Content-Type", ""),
                "body_preview": r.text[:300] if r.status_code == 200 else "",
            }
            findings["umbraco_api_results"][path] = entry
            log.info("  %s -> HTTP %d", path, r.status_code)
            if r.status_code == 200 and r.text.strip():
                log.info("    body: %s", r.text[:200])
        except Exception as e:
            log.info("  %s -> error: %s", path, e)

    # --- Verdict ---
    head_ok = [h for h in findings["sample_head_results"] if h["status"] == 200]
    pat = findings["media_url_pattern"]
    sitemap_hits = [e for e in findings["sitemap_entries"] if any(
        kw in e.lower() for kw in ("agenda", "minutes", "meeting")
    )]

    if not head_ok:
        findings["verdict"] = "media_urls_not_publicly_accessible: park with verdict"
    elif sitemap_hits:
        findings["verdict"] = (
            f"media_public ({len(head_ok)}/{len(abs_media[:6])} HEAD 200); "
            f"sitemap has {len(sitemap_hits)} agenda/minutes/meeting entries -- "
            "direct URL harvest may be feasible without the listing page"
        )
    elif pat.get("id_type") == "integer" and pat.get("id_range"):
        findings["verdict"] = (
            f"media_public ({len(head_ok)}/{len(abs_media[:6])} HEAD 200); "
            f"integer IDs, range {pat['id_range']} -- "
            "no sitemap agenda entries; URL discovery requires further work "
            "(sequential scan or Umbraco API) before harvest is viable"
        )
    else:
        findings["verdict"] = (
            f"media_public ({len(head_ok)}/{len(abs_media[:6])} HEAD 200) but "
            "no sitemap hits and ID type unknown -- park unless Umbraco API yields results"
        )

    log.info("Verdict: %s", findings["verdict"])
    return findings


def main():
    findings = probe()
    out = "hamilton_media_findings.json"
    with open(out, "w") as fh:
        json.dump(findings, fh, indent=2)
    log.info("Findings -> %s", out)

    print("\n=== HAMILTON MEDIA PROBE SUMMARY ===")
    print(f"Robots: {findings['robots'].get('allowed')}")
    if findings.get("error"):
        print(f"ERROR: {findings['error']}")
        return

    pat = findings.get("media_url_pattern", {})
    print(f"\nMedia URL pattern (from policies page):")
    print(f"  ID type    : {pat.get('id_type')}")
    print(f"  ID range   : {pat.get('id_range')}")
    print(f"  Total found: {pat.get('total_found')}")
    for h in pat.get("sample_hrefs", [])[:5]:
        print(f"  {h}")

    print(f"\nSample HEAD results:")
    for h in findings.get("sample_head_results", []):
        print(f"  HTTP {h['status']}  {h['url']}  [{h.get('content_type','')}]")

    sitemap = findings.get("sitemap_entries", [])
    print(f"\nSitemap entries (agenda/minutes/meeting): {len([e for e in sitemap if any(k in e.lower() for k in ('agenda','minutes','meeting'))])}")
    print(f"Sitemap /media/ entries total: {len(sitemap)}")
    for e in sitemap[:10]:
        print(f"  {e}")

    mp = findings.get("meetings_page_media_refs", {})
    print(f"\nMeetings page media refs: {len(mp.get('media_refs', []))}")
    print(f"API hints in page source: {mp.get('api_hints', [])}")

    print(f"\nVerdict: {findings.get('verdict')}")


if __name__ == "__main__":
    main()
