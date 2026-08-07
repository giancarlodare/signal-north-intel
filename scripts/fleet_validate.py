"""Fleet validation harness (read-only dry-run) for the eScribe/CivicWeb
adapter's HTML shape. Emits the ONE validation table the operator approves:
host, meetings found, docs on a sampled meeting, parse-ok, sample URL.

Exercises the REAL adapter parsers (src.escribe_adapter) against live
listing + meeting pages, writing nothing. This is the batch-validation
discipline applied to the board fleet: below-bar hosts become flagged ROWS,
never batch blockers, and per-host isolation means one dead tenant is a row,
not a stop. The loud-failure guard is exercised here too -- a bucket-A
tenant that parses zero meetings is flagged, which is the shape-change
signal surfacing in the dry-run before any seeded run.

Default set is the server-rendered (bucket A) first-wave + sample tenants
from fleet_discovery; extra tenants may be passed as argv. Shell (bucket C)
tenants are NOT here: their api path is inert pending the operator's eScribe
terms ruling, so validating them would mean calling an endpoint we have not
been cleared to call.
"""
import os
import sys
import time

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from src import escribe_adapter as ea          # noqa: E402
from scripts.coverage_probe import UA          # noqa: E402

TIMEOUT = 15
DELAY = 1.5

# (host, body, body_type, year_path) -- the bucket-A first wave + samples.
# Hamilton is the first-wave board that closes on the server-rendered path.
FIRST_WAVE = [
    ("pub-hamilton.escribemeetings.com", "Hamilton (board+council)", "council",
     "/?Year={year}"),
    ("pub-kitchener.escribemeetings.com", "Kitchener", "council", "/?Year={year}"),
    ("pub-oakville.escribemeetings.com", "Oakville", "council", "/?Year={year}"),
    ("stcatharines.civicweb.net", "St. Catharines", "council",
     "/Portal/MeetingSchedule.aspx"),
    ("simcoe.civicweb.net", "Simcoe County (paramedics)", "council",
     "/Portal/MeetingSchedule.aspx"),
    ("bruce.civicweb.net", "Bruce County (paramedics)", "council",
     "/Portal/MeetingSchedule.aspx"),
]

_session = requests.Session()
_session.headers["User-Agent"] = UA


# Alternate year-listing paths tried when the primary year_path returns 0.
# Police-board eScribe tenants may use different URL conventions than councils.
_ALT_PATHS = [
    "/MeetingsCalendarView.aspx?Year=2026",
    "/?Year=2025",
    "/",
]


def validate(host: str, body: str, body_type: str, year_path: str) -> dict:
    t = ea.Tenant(host, body, body_type, mode="html", year_path=year_path)
    row = {"host": host, "meetings": 0, "docs_sample": 0, "parse": "?",
           "sample": "", "flag": ""}
    try:
        lu = ea.listing_url(t, 2026)
        r = _session.get(lu, timeout=TIMEOUT)
        meetings = ea.parse_meeting_links(r.text, r.url)
        row["meetings"] = len(meetings)
        if not meetings:
            # Try alternate paths so we can diagnose the correct year_path
            # for tenants where the default fails.
            for alt in _ALT_PATHS:
                time.sleep(DELAY)
                try:
                    alt_r = _session.get(f"https://{host}{alt}", timeout=TIMEOUT)
                    alt_m = ea.parse_meeting_links(alt_r.text, alt_r.url)
                    if alt_m:
                        row["meetings"] = len(alt_m)
                        row["parse"] = "flag"
                        row["flag"] = (
                            f"zero on '{year_path}'; "
                            f"found {len(alt_m)} meetings at '{alt}' -- "
                            f"set escribe_year_path to '{alt}' in config")
                        return row
                except Exception:  # noqa: BLE001
                    pass
            row["parse"] = "flag"
            row["flag"] = (
                f"zero meetings on '{year_path}' and all alt paths "
                f"({', '.join(_ALT_PATHS)})")
            return row
        time.sleep(DELAY)
        mr = _session.get(meetings[0], timeout=TIMEOUT)
        docs = ea.parse_document_links(mr.text, mr.url)
        row["docs_sample"] = len(docs)
        row["sample"] = docs[0][0][:70] if docs else ""
        row["parse"] = "ok" if docs else "flag"
        if not docs:
            row["flag"] = "meetings parse but no documents on sampled meeting"
    except Exception as e:  # noqa: BLE001 -- per-host isolation
        row["parse"] = "flag"
        row["flag"] = f"{type(e).__name__}"
    return row


def main() -> int:
    extra = [(h, h, "council", "/?Year={year}") for h in sys.argv[1:]]
    fleet = FIRST_WAVE + extra
    print("FLEET VALIDATION (read-only dry-run, HTML shape) -- adapter parsers "
          "against live pages, writing nothing\n")
    print(f"{'host':44s} {'mtgs':>5s} {'docs':>5s} {'parse':6s} sample")
    rows = []
    for host, body, bt, yp in fleet:
        row = validate(host, body, bt, yp)
        rows.append(row)
        print(f"{host:44s} {row['meetings']:5d} {row['docs_sample']:5d} "
              f"{row['parse']:6s} {row['sample']}")
        if row["flag"]:
            print(f"    FLAG: {row['flag']}")
        time.sleep(DELAY)

    ok = sum(1 for r in rows if r["parse"] == "ok")
    flagged = [r["host"] for r in rows if r["parse"] == "flag"]
    print(f"\nVALIDATION TABLE: {ok}/{len(rows)} parse clean; "
          f"flagged rows: {flagged or 'none'}")
    print("Below-bar hosts are FLAGGED rows, not batch blockers (operator "
          "discipline). Shell/api tenants excluded pending the eScribe terms "
          "ruling.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
