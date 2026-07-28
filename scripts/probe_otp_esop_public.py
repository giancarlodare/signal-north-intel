"""OTP Jaggaer eSOP public-opportunity probe, pass 8 (operator 2026-07-28):
the operator found what look like LIVE public opportunity lists at
/esop/toolkit/opportunity/{current,past,global}/list.si, which would
contradict the standing "/esop robots-disallowed" verdict if robots
actually permits those specific paths.

STRICTLY ROBOTS-GATED: this script prints robots.txt VERBATIM, evaluates
can_fetch for each exact URL, and fetches ONLY paths robots permits. If
robots disallows them, the honest verdict is human-research-only no matter
how public the pages look in a browser, and this script fetches nothing.

Read-only, 2s politeness. CI only.
"""
import re
import sys
import time
import urllib.robotparser

import requests

UA = "SignalNorthCollector/1.0"
BASE = "https://ontariotenders.app.jaggaer.com"
CANDIDATES = [
    "/esop/toolkit/opportunity/current/list.si",
    "/esop/toolkit/opportunity/past/list.si",
    "/esop/toolkit/opportunity/global/list.si",
    "/esop/guest/go/opportunity/current",
]


def main() -> int:
    r = requests.get(f"{BASE}/robots.txt", headers={"User-Agent": UA},
                     timeout=30)
    print(f"=== {BASE}/robots.txt\n    status={r.status_code} "
          f"bytes={len(r.content)}\n--- VERBATIM ---")
    print(r.text)
    print("--- END ---")

    rp = urllib.robotparser.RobotFileParser()
    rp.parse(r.text.splitlines())
    allowed = []
    for path in CANDIDATES:
        ok = rp.can_fetch(UA, BASE + path)
        star = rp.can_fetch("*", BASE + path)
        print(f"    can_fetch({path}): UA={ok} wildcard={star}")
        if ok:
            allowed.append(path)

    if not allowed:
        print("\nVERDICT: robots disallows every candidate path. The pages "
              "stay human-research-only; nothing was fetched. The wall "
              "holds for collectors even if a browser sees live lists.")
        return 0

    for path in allowed:
        time.sleep(2)
        r = requests.get(BASE + path, headers={"User-Agent": UA}, timeout=30,
                         allow_redirects=True)
        html = r.text
        print(f"\n=== {BASE}{path}\n    status={r.status_code} "
              f"final={r.url[:90]} bytes={len(r.content)} "
              f"type={r.headers.get('content-type', '?')[:40]}")
        scripts = len(re.findall(r"<script\b", html, re.IGNORECASE))
        login = bool(re.search(r"login|sign\s*in|password", html, re.IGNORECASE))
        rows = len(re.findall(r"<tr\b", html, re.IGNORECASE))
        print(f"    scripts={scripts} table-rows={rows} "
              f"login-markers={login}")
        for m in list(re.finditer(
                r"<(?:td|a|span)[^>]*>([^<]{12,110})</", html))[:20]:
            t = m.group(1).strip()
            if t and not t.isspace():
                print(f"      {t[:100]}")
        for m in sorted(set(re.findall(
                r'["\'](/esop/[^"\']*(?:json|api|ajax|data)[^"\']*)["\']',
                html)))[:8]:
            print(f"      endpoint-ish: {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
