"""eScribe shell api-mode validation (operator ruling 2026-08-02: proceed).

Calls ONLY the read WebMethods the shell uses to list meetings --
/MeetingsCalendarView.aspx/GetCalendarMeetings and .../PastMeetings -- to
validate the api path live and reveal the JSON shape so the adapter parser
can be finalized. NEVER calls the subscription/OTP write-methods
(SaveEmailAndSendOtp, SubmitEnterOtp, AddNewSubscriber, UpdateSubscriptions):
those mutate and are out of scope. Documents come from FileStream.ashx, the
same handler the HTML shape already reads.

This is authorized collection, not diagnosis: bringing Ottawa and Niagara
into the first wave. The loud-failure guard applies -- a tenant that yields
zero meetings is FLAGGED, the shape-change signal surfacing before any
seeded run. Runs on the CI runner (sandbox egress excludes escribemeetings).
"""
import json
import os
import sys
import time

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from scripts.coverage_probe import UA  # noqa: E402

TIMEOUT = 25
DELAY = 1.5
API_TENANTS = ["pub-ottawa.escribemeetings.com",
               "pub-niagarapolice.escribemeetings.com"]
READ_METHODS = ["/MeetingsCalendarView.aspx/GetCalendarMeetings",
                "/MeetingsCalendarView.aspx/PastMeetings"]


def _unwrap(payload):
    """ASP.NET PageMethods wrap the result in {"d": ...}. The d value may be
    a JSON string (double-encoded) or already an object/list."""
    d = payload.get("d", payload) if isinstance(payload, dict) else payload
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except (ValueError, TypeError):
            pass
    return d


def _meeting_list(d):
    """Find the list of meetings in whatever shape came back."""
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in ("Meetings", "meetings", "Results", "Data", "d"):
            if isinstance(d.get(k), list):
                return d[k]
        # single dict with meeting-ish keys -> treat as one
        if any("meeting" in str(k).lower() for k in d):
            return [d]
    return []


def call_method(session, host, method, body) -> dict:
    url = f"https://{host}{method}"
    out = {"method": method, "status": None, "meetings": 0, "keys": [],
           "sample": "", "note": ""}
    try:
        r = session.post(url, data=json.dumps(body), timeout=TIMEOUT,
                         headers={"Content-Type": "application/json",
                                  "Accept": "application/json"})
        out["status"] = r.status_code
        if r.status_code != 200:
            out["note"] = r.text[:120].replace("\n", " ")
            return out
        d = _unwrap(r.json())
        meetings = _meeting_list(d)
        out["meetings"] = len(meetings)
        if meetings and isinstance(meetings[0], dict):
            out["keys"] = sorted(meetings[0].keys())[:16]
            # a document/meeting id sample, whatever the field is called
            for k in ("Id", "MeetingId", "ID", "DocumentId"):
                if k in meetings[0]:
                    out["sample"] = f"{k}={meetings[0][k]}"
                    break
    except Exception as e:  # noqa: BLE001 -- per-host isolation
        out["note"] = f"{type(e).__name__}: {str(e)[:100]}"
    return out


def main() -> int:
    tenants = sys.argv[1:] or API_TENANTS
    session = requests.Session()
    session.headers["User-Agent"] = UA
    print("API VALIDATE -- eScribe read WebMethods only, honest UA "
          "(operator ruling 2026-08-02)\n")
    flagged = []
    for host in tenants:
        print(f"### {host}")
        got_meetings = 0
        for method in READ_METHODS:
            # Empty body first; the response reveals whether params are needed.
            res = call_method(session, host, method, {})
            print(f"  {method}")
            print(f"    status={res['status']} meetings={res['meetings']} "
                  f"{res['sample']}")
            if res["keys"]:
                print(f"    meeting keys: {res['keys']}")
            if res["note"]:
                print(f"    note: {res['note']}")
            got_meetings += res["meetings"]
            time.sleep(DELAY)
        if got_meetings == 0:
            flagged.append(host)
            print(f"  FLAG: zero meetings from both read methods -- shape "
                  f"change or params required; api path stays inert for this "
                  f"tenant (loud-failure discipline)")
        print()

    print("=" * 66)
    print(f"api-mode validation: {len(tenants) - len(flagged)}/{len(tenants)} "
          f"yielded meetings; flagged: {flagged or 'none'}")
    print("Only read methods called; subscription/OTP write-methods never "
          "touched. Endpoint wiring proceeds only for tenants that yielded "
          "meetings, under the loud-failure guard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
