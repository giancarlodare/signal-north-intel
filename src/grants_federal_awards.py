"""Federal grant & contribution AWARDS collector — open.canada.ca proactive
disclosure, dataset API (not a scrape).

Design operator-approved 2026-07-11 (docs/grants-federal-awards-design.md):
awards are money already moved — the strongest 6-18-month leading indicator
of downstream procurement, often sub-threshold and invisible to tender
monitoring. One consolidated TBS dataset covers every department; the
2.26 GB CSV stays where it is and the CKAN datastore API serves filtered
rows instead.

Approved parameters, all encoded below:
  - Departments: ps-sp, rcmp-grc, dnd-mdn, cbsa-asfc (csc-scc / jus are
    later one-line reviewed config changes).
  - Window: agreement_start_date >= 2024-04-01. Records with NO start date
    cannot be placed inside a dated window, so the windowed ingest skips
    them (counted, not silently dropped) — it never fabricates a date.
  - Cap: 25 new docs per department per run, counting NEW docs only, so a
    baseline backlog pages through weekly runs without ever stalling.
  - Record URL: the award's own page on search.open.canada.ca (the
    publisher's human-readable record). RECORD_URL_TEMPLATE is verified by
    CI probe before first real run — see the design doc's question 1.

Mechanics:
  - POST datastore_search with a JSON body (CKAN's canonical action-API
    style). No query string means no collision with open.canada.ca's
    "Disallow: /*?sort*" rules under any robots interpretation; their
    Crawl-delay: 20 is honored by PoliteFetcher.
  - Newest-first sort + early stop: a page consisting entirely of
    already-stored records ends that department's scan, so the steady-state
    weekly cost is one page per department.
  - Identity = ref_number + amendment_number: an amendment is a real event
    (values change) and inserts as a fresh document; the original stays.
  - keywords.txt runs tag-only (the department filter IS the scope).
  - Failure policy mirrors the RSS collector: one department failing is
    logged and the rest continue; the run exits nonzero only when EVERY
    department fails (systemic).

    python -m src.grants_federal_awards --dry-run
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from . import supabase_client
from .board_minutes import MAX_STORED_CHARS, PoliteFetcher
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

DATASTORE_URL = "https://open.canada.ca/data/en/api/action/datastore_search"
# The consolidated grants CSV resource (datastore-active), probe-verified.
RESOURCE_ID = "1d15a62f-5656-49ad-8c88-f40ce689d831"

MIN_START_DATE = "2024-04-01"        # operator-approved first-ingest window
MAX_DOCS_PER_DEPT = 25               # per run; backlog pages through weekly
PAGE_SIZE = 100
MAX_PAGES_PER_DEPT = 40              # hard safety bound per run

DEPARTMENTS = [
    {"org": "ps-sp",     "env": "AWARDS_SOURCE_ID_PS_SP"},
    {"org": "rcmp-grc",  "env": "AWARDS_SOURCE_ID_RCMP_GRC"},
    {"org": "dnd-mdn",   "env": "AWARDS_SOURCE_ID_DND_MDN"},
    {"org": "cbsa-asfc", "env": "AWARDS_SOURCE_ID_CBSA_ASFC"},
    {"org": "csc-scc",   "env": "AWARDS_SOURCE_ID_CSC_SCC"},
    {"org": "jus",       "env": "AWARDS_SOURCE_ID_JUS"},
]

# The record's page on the publisher's search UI. Format is CI-probe-verified
# before the first real run; if the probe 404s this template, the fallback is
# the search page pinned to the ref_number
# (https://search.open.canada.ca/grants/?search_text=<ref>).
RECORD_URL_TEMPLATE = "https://search.open.canada.ca/grants/record/{org},{ref},{amd}"


def dept_search_url(org: str) -> str:
    """The department's public disclosure search page — the sources row URL."""
    return f"https://search.open.canada.ca/grants/?owner_org={org}"


def record_url(org: str, ref: str, amd) -> str:
    return RECORD_URL_TEMPLATE.format(org=org, ref=ref, amd=amd if amd not in (None, "") else 0)


# ---------------------------------------------------------------------------
# Record → document text
# ---------------------------------------------------------------------------
def _first(value) -> str:
    """Bilingual pipe fields ('British Columbia|Colombie-Britannique') → the
    English half; plain values pass through."""
    return str(value).split("|")[0].strip() if value not in (None, "") else ""


def _en(rec: dict, field: str) -> str:
    """English field with French fallback when English is empty."""
    return (rec.get(f"{field}_en") or rec.get(f"{field}_fr") or "").strip()


def award_title(rec: dict) -> str:
    what = _en(rec, "agreement_title") or _en(rec, "prog_name") or "Grant/contribution award"
    who = _first(rec.get("recipient_legal_name"))
    title = f"{what} — {who}" if who else what
    amd = rec.get("amendment_number")
    if amd not in (None, 0, "0", ""):
        title += f" (amendment {amd})"
    return title[:500]


def award_text(rec: dict) -> str:
    lines: list = []

    def add(label: str, value) -> None:
        if value not in (None, ""):
            lines.append(f"{label}: {value}")

    add("Reference number", rec.get("ref_number"))
    amd = rec.get("amendment_number")
    if amd not in (None, 0, "0", ""):
        add("Amendment", f"{amd} ({rec.get('amendment_date') or 'date not disclosed'})")
    add("Agreement type", {"G": "Grant", "C": "Contribution"}.get(
        rec.get("agreement_type"), rec.get("agreement_type")))
    recipient = _first(rec.get("recipient_legal_name"))
    operating = _first(rec.get("recipient_operating_name"))
    if operating and operating != recipient:
        recipient += f" (operating as {operating})"
    add("Recipient", recipient)
    add("Recipient location", ", ".join(x for x in (
        _first(rec.get("recipient_city")), _first(rec.get("recipient_province")),
        _first(rec.get("recipient_country"))) if x))
    add("Program", _en(rec, "prog_name"))
    add("Program purpose", _en(rec, "prog_purpose"))
    add("Agreement title", _en(rec, "agreement_title"))
    value = rec.get("agreement_value")
    if value not in (None, ""):
        try:
            add("Value", f"${float(value):,.2f} CAD")
        except (TypeError, ValueError):
            add("Value", value)
    if rec.get("foreign_currency_value") not in (None, ""):
        add("Foreign currency", f"{rec.get('foreign_currency_value')} "
                                f"{rec.get('foreign_currency_type') or ''}".strip())
    add("Start date", rec.get("agreement_start_date"))
    add("End date", rec.get("agreement_end_date"))
    add("Coverage", _first(rec.get("coverage")))
    add("Description", _en(rec, "description"))
    add("Expected results", _en(rec, "expected_results"))
    add("Additional information", _en(rec, "additional_information"))
    add("NAICS", rec.get("naics_identifier"))
    add("Department", _first(rec.get("owner_org_title")))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
def fetch_page(fetcher: PoliteFetcher, org: str, offset: int) -> list:
    resp = fetcher.post_json(DATASTORE_URL, {
        "resource_id": RESOURCE_ID,
        "filters": {"owner_org": org},
        "sort": "agreement_start_date desc",
        "limit": PAGE_SIZE,
        "offset": offset,
    })
    if resp is None:
        raise RuntimeError(f"datastore disallowed or unreachable for {org}")
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"datastore_search unsuccessful for {org}: {data.get('error')}")
    return data["result"].get("records") or []


def collect_department(dept: dict, source_id: str, fetcher: PoliteFetcher,
                       keywords: Keywords, limit: int, dry_run: bool) -> dict:
    stats = {"pages": 0, "records": 0, "inserted": 0, "skipped_duplicate": 0,
             "skipped_undated": 0, "skipped_no_ref": 0, "errors": 0}
    org = dept["org"]
    offset = 0
    done = False

    while not done and stats["pages"] < MAX_PAGES_PER_DEPT:
        records = fetch_page(fetcher, org, offset)
        if not records:
            break
        stats["pages"] += 1
        offset += PAGE_SIZE
        dups_on_page = 0

        for rec in records:
            stats["records"] += 1
            start = rec.get("agreement_start_date")
            if not start:
                # DESC sort surfaces NULL dates first; a dated window cannot
                # honestly place them, so they're counted and skipped.
                stats["skipped_undated"] += 1
                continue
            if str(start) < MIN_START_DATE:
                # Newest-first: everything from here on is older than the
                # window — this department is finished.
                done = True
                break
            ref = (rec.get("ref_number") or "").strip()
            if not ref:
                stats["skipped_no_ref"] += 1
                continue
            amd = rec.get("amendment_number")
            chash = content_hash(ref, "grant_award", str(amd or 0))
            if supabase_client.get_document_by_hash(chash):
                stats["skipped_duplicate"] += 1
                dups_on_page += 1
                continue
            if stats["inserted"] >= limit:
                log.info("[%s] per-run cap (%d) reached; backlog continues next run",
                         org, limit)
                done = True
                break
            try:
                title = award_title(rec)
                body = award_text(rec)
                result = evaluate(title, body[:20000], "", keywords)  # tag-only
                payload = {
                    "source_id": source_id,
                    "url": record_url(org, ref, amd),
                    "title": title,
                    "doc_type": "grant_award",
                    "status": "captured",
                    "published_on": str(start)[:10],
                    "date_precision": "day",
                    "content_hash": chash,
                    "content": body[:MAX_STORED_CHARS] or None,
                    "defence_relevant": result.defence_relevant,
                }
                if dry_run:
                    log.info("[dry-run] would insert: %r (%s, start %s, %d chars)",
                             title[:90], ref, start, len(body))
                else:
                    supabase_client.insert_document(payload)
                stats["inserted"] += 1
            except Exception:   # noqa: BLE001 - one bad record must not kill the dept
                log.exception("[%s] error collecting %s", org, ref)
                stats["errors"] += 1

        if not done and dups_on_page == len(records):
            # A full page of already-stored records: the scan has reached
            # known ground (steady-state early stop).
            done = True

    return stats


def resolve_source_id(dept: dict, sources: list) -> Optional[str]:
    """URL-keyed (ASCII, stable) — the em-dash lesson, kept."""
    override = os.environ.get(dept["env"], "").strip()
    if override:
        return override
    target = dept_search_url(dept["org"]).rstrip("/")
    for row in sources:
        if (row.get("url") or "").strip().rstrip("/") == target:
            return row["id"]
    return None


def run(limit: int = MAX_DOCS_PER_DEPT, dry_run: bool = False) -> int:
    keywords = load_keywords()
    fetcher = PoliteFetcher()
    now = datetime.now(timezone.utc)
    sources = supabase_client.fetch_rows("sources", "id,name,url")
    failures, successes = [], 0

    for dept in DEPARTMENTS:
        source_id = resolve_source_id(dept, sources)
        if not source_id:
            log.error("[%s] no sources row with url=%s (run the federal awards "
                      "seed migration, or set %s)", dept["org"],
                      dept_search_url(dept["org"]), dept["env"])
            failures.append(dept["org"])
            continue
        try:
            stats = collect_department(dept, source_id, fetcher, keywords,
                                       limit, dry_run)
            log.info("[%s] %s%s", dept["org"], stats, " (DRY RUN)" if dry_run else "")
            if stats["errors"]:
                failures.append(dept["org"])
            else:
                successes += 1
                if not dry_run:
                    supabase_client.update_source_last_collected(source_id, now)
        except Exception:
            log.exception("[%s] collection failed", dept["org"])
            failures.append(dept["org"])

    if failures:
        log.error("Federal awards run finished with failures in: %s",
                  ", ".join(failures))
        return 1 if successes == 0 else 0
    log.info("Federal awards run finished successfully")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Federal grant/contribution awards collector (open.canada.ca)")
    parser.add_argument("--limit", type=int, default=MAX_DOCS_PER_DEPT,
                        help=f"max NEW documents per department per run "
                             f"(default {MAX_DOCS_PER_DEPT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and parse but write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(limit=args.limit, dry_run=args.dry_run))
