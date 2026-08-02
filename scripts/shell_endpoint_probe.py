"""eScribe JS-shell endpoint probe. Read-only, terms-and-robots FIRST.

The 15 C-bucket tenants (fleet_discovery) serve a JS shell with no
server-side meetings; the shell fetches meetings from an internal API. The
operator's ruling (2026-08-02): an endpoint a page CALLS is not
automatically an endpoint we are invited to CALL. So this probe, for each
shell tenant:

  1. robots.txt FIRST -- fetch it, and test can_fetch() for every candidate
     API path we discover. A Disallow on the API path is a boundary, full
     stop.
  2. Terms -- look for a published terms/legal/privacy link on the portal
     and report whether one exists to read. This probe does NOT interpret
     legal text; it reports presence so the operator can rule.
  3. Endpoint discovery -- fetch the shell HTML and its referenced scripts,
     and surface URL-shaped strings that look like data endpoints
     (/api/, .svc, OData, MeetingService, GetMeetings...). Discovery only:
     the probe never CALLS a discovered data endpoint. Reading robots and a
     public JS bundle is not calling the API.

Verdict per tenant:
  CLEAN      robots allows the discovered path AND terms are absent or a
             plain robots/none -- collection may proceed (operator's "if
             terms are clean, proceed").
  AMBIGUOUS  a terms/legal document exists to read, OR robots is silent on
             a path that is clearly an internal API -- STOP this tenant and
             surface to the operator (operator's "if ambiguous, tell me").
  DISALLOW   robots forbids the API path -- a reported boundary, never
             worked around.

Honest UA, no endpoint calls, no evasion.
"""
import os
import re
import sys
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from scripts.coverage_probe import UA  # noqa: E402

TIMEOUT = 15
DELAY = 1.5

# The C-bucket tenants from fleet_discovery run 30757910418, plus the three
# first-wave tenants the launch names. Extra tenants may be passed as argv.
SHELL_TENANTS = [
    "pub-ottawa.escribemeetings.com",
    "pub-niagarapolice.escribemeetings.com",
    "pub-london.escribemeetings.com",
    "pub-cornwall.escribemeetings.com",
    "pub-cobourg.escribemeetings.com",
    "bm-public-markham.escribemeetings.com",
    "bm-public-guelph.escribemeetings.com",
    "pub-milton.escribemeetings.com",
    "pub-middlesexcounty.escribemeetings.com",
    "coe-pub.escribemeetings.com",
    "pub-wellington.escribemeetings.com",
    "pub-grey.escribemeetings.com",
    "pub-uclg.escribemeetings.com",
    "pub-ucpr.escribemeetings.com",
    "msdsb.escribemeetings.com",
]

SCRIPT_SRC_RE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)
# Data-endpoint shapes: eScribe/iCompass REST + generic API URL fragments.
ENDPOINT_RE = re.compile(
    r'["\'](/(?:api|odata|services?|meetingservice|meetings?service)'
    r'[^"\'\s]*|[^"\'\s]*(?:GetMeetings|MeetingService|/api/)[^"\'\s]*)["\']',
    re.I)
TERMS_RE = re.compile(
    r'href=["\']([^"\']*(?:terms|legal|privacy|conditions|disclaimer)[^"\']*)["\']',
    re.I)

_session = requests.Session()
_session.headers["User-Agent"] = UA


def get(url: str):
    return _session.get(url, timeout=TIMEOUT)


def probe(tenant: str) -> dict:
    base = f"https://{tenant}"
    out = {"tenant": tenant, "robots": "?", "terms": [], "endpoints": [],
           "robots_on_endpoints": {}, "verdict": "?", "note": ""}

    # 1. robots FIRST.
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = get(f"{base}/robots.txt")
        if r.status_code == 200:
            rp.parse(r.text.splitlines())
            out["robots"] = "present"
        elif r.status_code == 404:
            out["robots"] = "none(404)"
        else:
            out["robots"] = f"http{r.status_code}"
    except Exception as e:  # noqa: BLE001
        out["robots"] = f"unreachable({type(e).__name__})"
        out["verdict"] = "AMBIGUOUS"
        out["note"] = "robots.txt unreachable -- cannot clear the gate"
        return out

    # 2 + 3. Shell HTML: terms links + script srcs. Then discover endpoint
    # strings from the referenced scripts (public bundles, not API calls).
    try:
        h = get(f"{base}/")
        out["terms"] = sorted(set(TERMS_RE.findall(h.text)))[:5]
        scripts = SCRIPT_SRC_RE.findall(h.text)[:8]
        found: set = set(ENDPOINT_RE.findall(h.text))
        for src in scripts:
            surl = urljoin(h.url, src)
            if urlparse(surl).netloc != tenant:
                continue  # only same-tenant bundles
            try:
                s = get(surl)
                found |= set(ENDPOINT_RE.findall(s.text))
            except Exception:  # noqa: BLE001
                continue
        out["endpoints"] = sorted({e if e.startswith("/") else "/" + e.lstrip("/")
                                   for e in found})[:8]
    except Exception as e:  # noqa: BLE001
        out["note"] = f"shell fetch: {type(e).__name__}"

    # robots verdict per discovered endpoint (no calls -- can_fetch only).
    for ep in out["endpoints"]:
        allowed = rp.can_fetch(UA, urljoin(base, ep)) if out["robots"] == "present" \
            else True
        out["robots_on_endpoints"][ep] = "ALLOW" if allowed else "DISALLOW"

    # Classify.
    if any(v == "DISALLOW" for v in out["robots_on_endpoints"].values()):
        out["verdict"] = "DISALLOW"
        out["note"] = "robots forbids a discovered API path -- boundary"
    elif out["terms"]:
        out["verdict"] = "AMBIGUOUS"
        out["note"] = f"terms/legal document(s) present to read: {out['terms'][:2]}"
    elif not out["endpoints"]:
        out["verdict"] = "AMBIGUOUS"
        out["note"] = ("no endpoint surfaced from the public shell -- the API "
                       "may be injected at runtime; needs a manual look")
    else:
        out["verdict"] = "CLEAN"
        out["note"] = "robots allows discovered path(s); no terms document found"
    return out


def main() -> int:
    import time
    tenants = sys.argv[1:] or SHELL_TENANTS
    print("SHELL-ENDPOINT PROBE -- read-only, terms+robots FIRST, no API calls")
    print(f"honest UA {UA}; {len(tenants)} tenants\n")
    verdicts = {}
    for t in tenants:
        p = probe(t)
        verdicts[t] = p["verdict"]
        print(f"{t}")
        print(f"  robots={p['robots']}  terms={p['terms'] or 'none'}")
        print(f"  endpoints={p['endpoints'] or 'none surfaced'}")
        if p["robots_on_endpoints"]:
            print(f"  robots-on-endpoints={p['robots_on_endpoints']}")
        print(f"  VERDICT: {p['verdict']} -- {p['note']}\n")
        time.sleep(DELAY)

    from collections import Counter
    tally = Counter(verdicts.values())
    print("=" * 68)
    print(f"SUMMARY: CLEAN={tally.get('CLEAN', 0)} "
          f"AMBIGUOUS={tally.get('AMBIGUOUS', 0)} "
          f"DISALLOW={tally.get('DISALLOW', 0)}")
    if tally.get("CLEAN"):
        print("  CLEAN tenants -> adapter shell path may proceed for these.")
    if tally.get("AMBIGUOUS") or tally.get("DISALLOW"):
        print("  AMBIGUOUS/DISALLOW -> STOP those tenants; operator rules. "
              "Per discipline: rather lose Ottawa than get this wrong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
