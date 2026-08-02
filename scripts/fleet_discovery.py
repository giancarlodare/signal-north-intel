"""eScribe / CivicWeb fleet discovery. Read-only; the pass that decides the
board-seeding schedule (operator 2026-08-02: "the bucket table and the intake
projection decide the schedule").

For every rostered public-safety host (police, boards-via-service-sites,
fire, EMS), find its meeting-platform tenant from the homepage, then probe
the TENANT's server-side surface:

  bucket A  works unchanged  -- year listing serves Meeting links AND a
                                sampled meeting page serves document links,
                                all in raw HTML (no JS needed)
  bucket B  config value     -- meetings visible server-side but documents
                                need a per-tenant path/variant
  bucket C  genuinely different -- tenant found but nothing server-side
                                (JS/API shell), needs adapter work
  no-tenant                  -- no eScribe/CivicWeb tenant on the homepage

Intake projection: for A/B tenants, meetings on the current-year listing x
documents on one sampled meeting page -> docs/year -> docs/day, summed over
the fleet. Cost is reported at the measured Peel seed rate ($0.019023/doc)
as a floor, with the caveat that board PDFs run longer than portal pages;
the binding envelope uses the measured board rate before any seeded run.

Politeness: every tenant shares escribemeetings.com / civicweb.net backend
infrastructure, so ONE shared delay between every request, sequential, and
per-host isolation (one dead tenant never stops the sweep).
"""
import os
import re
import sys
import time
from urllib.parse import urljoin

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from scripts.coverage_probe import EMS, FIRE, POLICE, POLICE_FN, UA  # noqa: E402

TIMEOUT = 15
DELAY = 1.5  # shared, every request, fleet-polite

TENANT_RE = re.compile(
    r"https?://([a-z0-9.-]+\.(?:escribemeetings\.com|civicweb\.net))", re.I)
MEETING_RE = re.compile(r"Meeting\.aspx\?Id=[0-9a-f-]+", re.I)
DOC_RE = re.compile(
    r"FileStream\.ashx|/filepro/|/document/|Download\.aspx|\.pdf\b", re.I)
# Depth-2 crawl (operator 2026-08-02): boards link their tenants from
# meetings pages, not homepages, so when the homepage carries no tenant we
# follow up to three links whose HREF looks meetings-shaped and read those.
LINK_RE = re.compile(r"href=[\"']([^\"'#]+)[\"']", re.I)
MEET_WORDS = re.compile(r"meeting|agenda|minute|board|council", re.I)
MAX_DEEP_LINKS = 3

_last = 0.0


def get(url: str):
    global _last
    wait = DELAY - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.monotonic()
    return requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)


def find_tenants(host: str) -> set:
    try:
        r = get(f"https://{host}/")
    except Exception:  # noqa: BLE001 -- isolation: a dead host is a row, not a stop
        return set()
    tenants = {t.lower() for t in TENANT_RE.findall(r.text)}
    if tenants:
        return tenants
    # One level deeper. HREF-shape matching only (no HTML parsing); links may
    # leave the host -- board sites often live on their own domains.
    followed = 0
    for m in LINK_RE.finditer(r.text):
        if followed >= MAX_DEEP_LINKS or tenants:
            break
        href = m.group(1)
        if not MEET_WORDS.search(href):
            continue
        followed += 1
        try:
            r2 = get(urljoin(r.url, href))
            tenants |= {t.lower() for t in TENANT_RE.findall(r2.text)}
        except Exception:  # noqa: BLE001
            continue
    return tenants


def probe_escribe(tenant: str) -> dict:
    base = f"https://{tenant}"
    out = {"platform": "escribe", "meetings": 0, "docs_sample": 0,
           "bucket": "C", "note": ""}
    best_page = None
    for path in ("/?Year=2026", "/", "/MeetingsCalendarView.aspx?Year=2026"):
        try:
            r = get(base + path)
            n = len(set(MEETING_RE.findall(r.text)))
            if n > out["meetings"]:
                out["meetings"], best_page = n, r
        except Exception as e:  # noqa: BLE001
            out["note"] = f"{type(e).__name__}"
    if not out["meetings"]:
        return out
    m = MEETING_RE.search(best_page.text)
    try:
        mr = get(urljoin(best_page.url, m.group(0)))
        out["docs_sample"] = len(set(DOC_RE.findall(mr.text)))
    except Exception as e:  # noqa: BLE001
        out["note"] = f"meeting page: {type(e).__name__}"
    out["bucket"] = "A" if out["docs_sample"] else "B"
    return out


def probe_civicweb(tenant: str) -> dict:
    out = {"platform": "civicweb", "meetings": 0, "docs_sample": 0,
           "bucket": "C", "note": ""}
    for path in ("/Portal/MeetingSchedule.aspx", "/filepro/documents/", "/"):
        try:
            r = get(f"https://{tenant}" + path)
            docs = len(set(DOC_RE.findall(r.text)))
            meets = len(re.findall(r"MeetingInformation|/Portal/Meeting", r.text))
            out["meetings"] = max(out["meetings"], meets)
            out["docs_sample"] = max(out["docs_sample"], docs)
        except Exception as e:  # noqa: BLE001
            out["note"] = f"{type(e).__name__}"
    if out["docs_sample"]:
        out["bucket"] = "A"
    elif out["meetings"]:
        out["bucket"] = "B"
    return out


def main() -> int:
    print("FLEET DISCOVERY -- eScribe/CivicWeb tenants, read-only")
    print(f"shared delay {DELAY}s between every request, sequential\n")

    rows = []
    seen_tenants: dict[str, dict] = {}
    roster = [("police", n, h) for n, h in POLICE if h] + \
             [("police-fn", n, h) for n, h in POLICE_FN if h] + \
             [("fire", n, h) for n, h in FIRE if h] + \
             [("ems", n, h) for n, h in EMS if h]
    n_requests = 0
    # argv entries that ARE tenant hosts are probed directly -- this is how
    # the first-wave tenants (pub-ottawa, pub-niagarapolice, pub-london) get
    # bucketed by name without waiting on enumeration.
    for h in [a.lower() for a in sys.argv[1:]]:
        if "escribemeetings" in h or "civicweb" in h:
            p = probe_escribe(h) if "escribemeetings" in h else probe_civicweb(h)
            n_requests += 4
            seen_tenants[h] = p
            rows.append(("argv", h, h, h, p["bucket"],
                         p["meetings"], p["docs_sample"], p["note"]))
        else:
            roster.append(("argv", h, h))
    for domain, name, host in roster:
        tenants = find_tenants(host)
        n_requests += 1
        if not tenants:
            rows.append((domain, name, host, "-", "no-tenant", 0, 0, ""))
            continue
        for t in sorted(tenants):
            if t in seen_tenants:
                p = seen_tenants[t]
                rows.append((domain, name, host, t, p["bucket"] + " (shared)",
                             p["meetings"], p["docs_sample"], p["note"]))
                continue
            p = probe_escribe(t) if "escribemeetings" in t else probe_civicweb(t)
            n_requests += 4
            seen_tenants[t] = p
            rows.append((domain, name, host, t, p["bucket"],
                         p["meetings"], p["docs_sample"], p["note"]))

    print(f"{'domain':10s} {'org':40s} {'tenant':44s} "
          f"{'bucket':12s} {'mtgs':>4s} {'docs':>4s}")
    for domain, name, host, t, bucket, meets, docs, note in rows:
        if t == "-" and bucket == "no-tenant":
            continue  # tallied below; keep the table to tenant rows
        print(f"{domain:10s} {name[:40]:40s} {t[:44]:44s} "
              f"{bucket:12s} {meets:4d} {docs:4d}  {note}")

    from collections import Counter
    tally = Counter(p["bucket"] for p in seen_tenants.values())
    no_tenant = sum(1 for r in rows if r[4] == "no-tenant")
    print(f"\nBUCKETS (distinct tenants): A={tally.get('A', 0)} "
          f"B={tally.get('B', 0)} C={tally.get('C', 0)}; "
          f"rostered hosts with no tenant on homepage: {no_tenant}")

    # Intake projection over A+B tenants: current-year meetings x sampled
    # docs/meeting. Stated as measured-so-far, not a promise.
    year_meetings = sum(p["meetings"] for p in seen_tenants.values()
                        if p["bucket"] in "AB")
    weighted_docs = sum(p["meetings"] * max(p["docs_sample"], 1)
                        for p in seen_tenants.values() if p["bucket"] in "AB")
    per_day = weighted_docs / 365
    print(f"\nINTAKE PROJECTION (A+B tenants, 2026 listings): "
          f"{year_meetings} meetings/yr, ~{weighted_docs} docs/yr, "
          f"~{per_day:.1f} docs/day forward")
    print(f"  extraction floor at Peel seed rate $0.019023/doc: "
          f"~${per_day * 0.019023:.2f}/day forward; historical backlog is a "
          f"separate measured envelope BEFORE any seeded run (cost gate)")
    print(f"\nrequest profile this run: ~{n_requests} requests, "
          f"{DELAY}s spacing, ~{n_requests * DELAY / 60:.0f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
