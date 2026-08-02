"""Roster-index ingest: enumeration completion (operator 2026-08-02).

"Stop resolving hosts individually, ingest the rosters instead. Parse them,
cross-reference against the coverage table, and tell me what's genuinely
missing after that rather than what you couldn't resolve by guessing a
domain."

Fetches each canonical index in coverage_probe.ROSTER_INDEXES (HTML pages
and the OACP/OAPSB PDFs), extracts candidate domains, cross-references
against the coverage rosters AND the live sources table, and reports the
domains an index carries that we do not yet hold. Read-only: index GETs plus
corpus reads, honest UA, polite delay. PDFs are parsed with pypdf (already a
dependency); a domain regex over extracted text.

This is CONFIRMATION now, not the only path (the deep-crawl already lifted
enumeration from 9 to 37 tenants); the rosters close the residual 98.
"""
import io
import os
import re
import sys
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from src import supabase_client as sc  # noqa: E402
from scripts.coverage_probe import (  # noqa: E402
    ROSTER_INDEXES, POLICE, POLICE_FN, FIRE, EMS, ADVOCACY, UA, TIMEOUT)

DELAY = 1.5
DOMAIN_RE = re.compile(
    r'\b([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:ca|com|org|net|gov\.on\.ca))\b',
    re.I)
# Domains that are index infrastructure or aggregators, not service sites.
IGNORE = {"oacp.ca", "oacpcertificate.ca", "oapsb.ca", "oapc.ca",
          "policegovernanceontario.ca", "wikipedia.org", "en.wikipedia.org",
          "cacp.ca", "cpa-acp.ca", "google.com", "facebook.com", "twitter.com",
          "x.com", "linkedin.com", "youtube.com", "annexbusinessmedia.com",
          "instagram.com", "gov.on.ca", "ontario.ca", "canada.ca"}

_session = requests.Session()
_session.headers["User-Agent"] = UA


def robots_ok(host: str, path: str = "/") -> bool:
    try:
        r = _session.get(f"https://{host}/robots.txt", timeout=TIMEOUT)
        if r.status_code != 200:
            return True
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        return rp.can_fetch(UA, f"https://{host}{path}")
    except Exception:  # noqa: BLE001
        return True


def fetch_domains(label: str, url: str) -> set:
    """Domains referenced by one index page or PDF. Honors robots."""
    if not url.startswith("http"):
        url = "https://" + url
    host = urlparse(url).netloc
    path = urlparse(url).path or "/"
    if not robots_ok(host, path):
        print(f"  [{label}] robots DISALLOW on {host}{path} -- skipped (boundary)")
        return set()
    try:
        r = _session.get(url, timeout=TIMEOUT)
    except Exception as e:  # noqa: BLE001
        print(f"  [{label}] unreachable: {type(e).__name__}")
        return set()
    ctype = r.headers.get("content-type", "")
    text = ""
    if "pdf" in ctype or url.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(r.content))
            text = " ".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:  # noqa: BLE001
            print(f"  [{label}] PDF parse failed: {type(e).__name__}")
            return set()
    else:
        text = r.text
    doms = {d.lower().lstrip("www.") for d in DOMAIN_RE.findall(text)}
    doms = {d for d in doms if d not in IGNORE and "." in d}
    print(f"  [{label}] {len(doms)} candidate domains")
    return doms


def known_domains() -> set:
    known = set()
    for _, roster in (("police", POLICE), ("fn", POLICE_FN), ("fire", FIRE),
                      ("ems", EMS), ("adv", ADVOCACY)):
        for _, host in roster:
            if host:
                known.add(host.lower().lstrip("www."))
    for s in sc.fetch_rows("sources", "url"):
        u = (s.get("url") or "").lower()
        m = re.match(r"https?://([^/]+)/?", u)
        if m:
            known.add(m.group(1).lstrip("www."))
    return known


def main() -> int:
    print("ROSTER-INDEX INGEST -- read-only, honest UA, robots honored\n")
    all_candidates: set = set()
    for label, url in ROSTER_INDEXES:
        all_candidates |= fetch_domains(label, url)
        time.sleep(DELAY)

    known = known_domains()
    missing = sorted(d for d in all_candidates if d not in known)
    print(f"\n{'='*66}")
    print(f"candidate domains across all indexes: {len(all_candidates)}")
    print(f"already in roster or sources:        {len(all_candidates) - len(missing)}")
    print(f"GENUINELY MISSING (in an index, not held): {len(missing)}\n")
    for d in missing:
        print(f"  {d}")
    print("\nNOTE: candidate domains are index-referenced hosts, some of which "
          "are not services (vendors, media, partners). The seeding pass "
          "confirms each; this list is the enumeration residue to work, not a "
          "seed list to trust blind.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
