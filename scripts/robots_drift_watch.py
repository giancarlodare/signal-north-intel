"""Weekly robots-drift watch (operator 2026-07-28): the Ontario Tenders
Portal's opportunity lists are collectable the day its robots disallow
narrows or lifts. This watch checks the walled hosts weekly and goes LOUD
(non-zero exit, so the workflow step turns red and pages attention) the
week a wall changes, so the collector build starts immediately.

Quiet (exit 0) while the walls stand unchanged. Read-only: fetches only
robots.txt, never the walled paths themselves.
"""
import sys
import urllib.robotparser

import requests

UA = "SignalNorthIntel/1.0"

# (base host, path that is currently DISALLOWED and would be collectable)
WATCHES = [
    ("https://ontariotenders.app.jaggaer.com",
     "/esop/toolkit/opportunity/current/list.si"),
]


def main() -> int:
    lifted = []
    for base, path in WATCHES:
        try:
            r = requests.get(f"{base}/robots.txt", headers={"User-Agent": UA},
                             timeout=30)
        except requests.RequestException as e:
            print(f"{base}: robots fetch failed ({type(e).__name__}); "
                  "treating as unchanged (walled)")
            continue
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        ok = rp.can_fetch(UA, base + path)
        print(f"{base}{path}: can_fetch={ok}")
        if ok:
            lifted.append((base, path, r.text.strip()))

    if lifted:
        print("\n" + "!" * 66)
        for base, path, robots in lifted:
            print(f"ROBOTS WALL LIFTED: {base}{path} is now fetchable.")
            print(f"robots.txt now reads:\n{robots}")
        print("Start the collector design-first build per the standing "
              "provincial plan (docs/opp-provincial-procurement-design.md).")
        print("!" * 66)
        return 2
    print("All watched walls unchanged; staying quiet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
