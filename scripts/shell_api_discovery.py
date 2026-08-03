"""eScribe JS-shell API discovery -- the manual look, mechanized. Read-only.

Operator ruling 2026-08-02: proceed with the eScribe runtime API (terms
read; neither privacy policy nor terms of use address automated access;
robots permits; statutory public records). This finds the endpoint the
shell calls, by fetching the shell page and its SAME-ORIGIN script bundles
and surfacing every URL/path literal that looks like a data endpoint. It
does NOT call any discovered endpoint -- reading a public JS bundle is not
calling the API; wiring the endpoint into collection (with the loud-failure
guard) is the next, separate step.

Runs on the CI runner because the sandbox egress is allowlisted and does not
include escribemeetings.com; the runner reaches it (fleet_discovery did).

Default targets: the two first-wave shell tenants the ruling brings in
(pub-ottawa, pub-niagarapolice). Extra tenants via argv.
"""
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from scripts.coverage_probe import UA  # noqa: E402

TIMEOUT = 20
DELAY = 1.0
TARGETS = ["pub-ottawa.escribemeetings.com", "pub-niagarapolice.escribemeetings.com"]

SRC_RE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)
# Endpoint-shaped literals: paths ending in the ASP.NET/eScribe handlers, or
# containing meeting/service tokens, or an api/odata segment.
PATH_LIT_RE = re.compile(
    r'["\'](/?[A-Za-z0-9_./-]*'
    r'(?:\.aspx|\.ashx|\.svc|\.json|/api/|/odata/'
    r'|Meeting[A-Za-z]*|GetMeetings|CalendarView|FileStream)'
    r'[A-Za-z0-9_./?=&-]*)["\']', re.I)
# A config base URL assignment (apiUrl: "...", serviceUrl = '...').
BASE_RE = re.compile(
    r'(?:api|service|data|base)Url\s*[:=]\s*["\']([^"\']+)["\']', re.I)


def scan(text: str) -> tuple:
    paths = sorted({m for m in PATH_LIT_RE.findall(text)})
    bases = sorted({m for m in BASE_RE.findall(text)})
    return paths, bases


def discover(host: str, session: requests.Session) -> None:
    base = f"https://{host}"
    print(f"\n### {host}")
    try:
        r = session.get(base + "/", timeout=TIMEOUT)
    except Exception as e:  # noqa: BLE001
        print(f"  homepage unreachable: {type(e).__name__}: {str(e)[:120]}")
        return
    print(f"  homepage {r.status_code}, {len(r.text)} bytes")
    hp_paths, hp_bases = scan(r.text)
    if hp_bases:
        print(f"  inline base URLs: {hp_bases}")
    if hp_paths:
        print(f"  inline path literals: {hp_paths[:12]}")

    srcs = [s for s in SRC_RE.findall(r.text)]
    same = [urljoin(r.url, s) for s in srcs
            if urlparse(urljoin(r.url, s)).netloc == host]
    print(f"  same-origin scripts: {len(same)}")
    all_paths, all_bases = set(hp_paths), set(hp_bases)
    for surl in same[:12]:
        time.sleep(DELAY)
        try:
            s = session.get(surl, timeout=TIMEOUT)
        except Exception as e:  # noqa: BLE001
            print(f"    {surl.rsplit('/',1)[-1]}: {type(e).__name__}")
            continue
        p, b = scan(s.text)
        if p or b:
            print(f"    {surl.rsplit('/',1)[-1]} ({len(s.text)}b): "
                  f"bases={b[:4]} paths={p[:10]}")
        all_paths |= set(p)
        all_bases |= set(b)

    print(f"  --- CANDIDATE ENDPOINTS ({host}) ---")
    for b in sorted(all_bases):
        print(f"    base: {b}")
    # Rank meeting-list-ish paths to the top.
    ranked = sorted(all_paths,
                    key=lambda p: (0 if re.search(r'meeting|calendar|getmeetings',
                                                  p, re.I) else 1, p))
    for p in ranked[:20]:
        print(f"    path: {p}")


def main() -> int:
    targets = sys.argv[1:] or TARGETS
    session = requests.Session()
    session.headers["User-Agent"] = UA
    print("SHELL API DISCOVERY -- read-only, honest UA, no endpoint calls")
    for host in targets:
        discover(host, session)
        time.sleep(DELAY)
    print("\nNEXT: identify the meeting-list endpoint from the candidates, "
          "wire it as the tenant's clean_endpoint in the adapter (api mode), "
          "and the loud-failure guard covers it from the first call.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
