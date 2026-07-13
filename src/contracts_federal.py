"""Federal CONTRACT awards collector: open.canada.ca proactive disclosure.

The awarded-rung source. Grants gave the leading indicator (commitment /
intent); federal contracts give the outcome (awarded), the strongest
reconciliation evidence and the rung the corpus is starved for. Design
operator-approved 2026-07-13 (docs/contracts-federal-design.md).

A near-clone of grants_federal_awards. Two things make it distinct:
  - doc_type is 'award_notice' (a contract award), which floors at grade 5
    (awarded) in the taxonomy, distinct from grant_award's commitment floor.
    A grant is upstream of procurement; a contract award IS the procurement
    outcome.
  - Each record's procurement_id (the solicitation identifier) is written into
    documents.reference_number, a first-class indexed field the procurement
    proposer hard-keys on. So an award and its originating tender cluster into
    one procurement, closing the loop the spine was built for.

Approved parameters:
  - Departments: ps-sp, rcmp-grc, dnd-mdn, cbsa-asfc, csc-scc, jus.
  - Value floor: contract_value >= $100,000. Unlike grants (where
    sub-threshold is the point), a contract award is only prediction-relevant
    if it is a material procurement, and the floor also tames DND's volume
    (353k all-time records).
  - Window: contract_date >= 2024-04-01, newest-first, with a steady-state
    early stop on a fully-known page.
  - Cap: 50 new docs per department per run (double the grants cap; volume is
    higher even floored). Backlog pages through weekly.

    python -m src.contracts_federal --dry-run
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
# "Contracts over $10,000" resource (datastore-active), probe-verified.
RESOURCE_ID = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"

MIN_CONTRACT_DATE = "2024-04-01"     # operator-approved window
MIN_CONTRACT_VALUE = 100_000.0       # operator-approved value floor
MAX_DOCS_PER_DEPT = 50               # per run; backlog pages through weekly
PAGE_SIZE = 100
MAX_PAGES_PER_DEPT = 60              # hard safety bound per run

DEPARTMENTS = [
    {"org": "ps-sp",     "env": "CONTRACTS_SOURCE_ID_PS_SP"},
    {"org": "rcmp-grc",  "env": "CONTRACTS_SOURCE_ID_RCMP_GRC"},
    {"org": "dnd-mdn",   "env": "CONTRACTS_SOURCE_ID_DND_MDN"},
    {"org": "cbsa-asfc", "env": "CONTRACTS_SOURCE_ID_CBSA_ASFC"},
    {"org": "csc-scc",   "env": "CONTRACTS_SOURCE_ID_CSC_SCC"},
    {"org": "jus",       "env": "CONTRACTS_SOURCE_ID_JUS"},
]

# The record's page on the publisher's search UI. Format CI-probe-verified
# before the first real run; fallback is the search page pinned to the
# reference number (https://search.open.canada.ca/contracts/?search_text=<ref>).
RECORD_URL_TEMPLATE = "https://search.open.canada.ca/contracts/record/{org},{ref}"


def dept_search_url(org: str) -> str:
    """The department's public contracts search page, the sources row URL."""
    return f"https://search.open.canada.ca/contracts/?owner_org={org}"


def record_url(org: str, ref: str) -> str:
    return RECORD_URL_TEMPLATE.format(org=org, ref=ref)


# ---------------------------------------------------------------------------
# Record -> document text
# ---------------------------------------------------------------------------
def _first(value) -> str:
    """Bilingual pipe fields -> the English half; plain values pass through."""
    return str(value).split("|")[0].strip() if value not in (None, "") else ""


def _en(rec: dict, field: str) -> str:
    """English field with French fallback when English is empty."""
    return (rec.get(f"{field}_en") or rec.get(f"{field}_fr") or "").strip()


def contract_value(rec: dict) -> Optional[float]:
    """Numeric contract_value, or None when unparseable."""
    raw = rec.get("contract_value")
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def award_title(rec: dict) -> str:
    what = _en(rec, "description") or "Contract award"
    who = _first(rec.get("vendor_name"))
    title = f"{what} - {who}" if who else what
    return title[:500]


def award_text(rec: dict) -> str:
    lines: list = []

    def add(label: str, value) -> None:
        if value not in (None, ""):
            lines.append(f"{label}: {value}")

    add("Reference number", rec.get("reference_number"))
    add("Procurement ID", rec.get("procurement_id"))
    add("Vendor", _first(rec.get("vendor_name")))
    add("Vendor country", rec.get("country_of_vendor"))
    add("Buyer", rec.get("buyer_name"))
    add("Contract date", rec.get("contract_date"))
    add("Contract period start", rec.get("contract_period_start"))
    add("Delivery date", rec.get("delivery_date"))
    val = contract_value(rec)
    if val is not None:
        add("Contract value", f"${val:,.2f} CAD")
    if rec.get("original_value") not in (None, ""):
        add("Original value", rec.get("original_value"))
    if rec.get("amendment_value") not in (None, "", "0.0", "0"):
        add("Amendment value", rec.get("amendment_value"))
    add("Description", _en(rec, "description"))
    add("Commodity type", rec.get("commodity_type"))
    add("Commodity code", rec.get("commodity_code"))
    add("Economic object code", rec.get("economic_object_code"))
    # Competition context (feeds the Phase D neighbouring questions later).
    add("Solicitation procedure", rec.get("solicitation_procedure"))
    add("Number of bids", rec.get("number_of_bids"))
    add("Limited-tendering reason", rec.get("limited_tendering_reason"))
    add("Award criteria", rec.get("award_criteria"))
    add("Standing offer number", rec.get("standing_offer_number"))
    add("Instrument type", rec.get("instrument_type"))
    add("Comments", _en(rec, "comments"))
    add("Additional comments", _en(rec, "additional_comments"))
    add("Department", _first(rec.get("owner_org_title")))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
def fetch_page(fetcher: PoliteFetcher, org: str, offset: int) -> list:
    resp = fetcher.post_json(DATASTORE_URL, {
        "resource_id": RESOURCE_ID,
        "filters": {"owner_org": org},
        "sort": "contract_date desc",
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
             "skipped_undated": 0, "skipped_below_floor": 0, "skipped_no_ref": 0,
             "errors": 0}
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
            cdate = rec.get("contract_date")
            if not cdate:
                # DESC sort surfaces NULL dates first; a dated window cannot
                # honestly place them.
                stats["skipped_undated"] += 1
                continue
            if str(cdate) < MIN_CONTRACT_DATE:
                # Newest-first: everything from here on predates the window.
                done = True
                break
            val = contract_value(rec)
            if val is None or val < MIN_CONTRACT_VALUE:
                # Below the material-procurement floor. Not a duplicate and not
                # end-of-window, so the scan continues past it.
                stats["skipped_below_floor"] += 1
                continue
            ref = (rec.get("reference_number") or "").strip()
            if not ref:
                stats["skipped_no_ref"] += 1
                continue
            # Identity: reference + value, so a re-disclosed amendment (changed
            # value) inserts as a fresh document while the original stays.
            chash = content_hash(ref, "contract_award", str(val))
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
                    "url": record_url(org, ref),
                    "title": title,
                    "doc_type": "award_notice",     # floors at awarded (grade 5)
                    "status": "captured",
                    "published_on": str(cdate)[:10],
                    "date_precision": "day",
                    # The procurement_id is the solicitation identifier the
                    # procurement proposer hard-keys on. Written to the
                    # first-class column so the proposer reads it directly.
                    "reference_number": (rec.get("procurement_id") or "").strip() or None,
                    "content_hash": chash,
                    "content": body[:MAX_STORED_CHARS] or None,
                    "defence_relevant": result.defence_relevant,
                }
                if dry_run:
                    log.info("[dry-run] would insert: %r ($%.0f, %s, proc_id=%s)",
                             title[:80], val, cdate, rec.get("procurement_id"))
                else:
                    supabase_client.insert_document(payload)
                stats["inserted"] += 1
            except Exception:   # noqa: BLE001 - one bad record must not kill the dept
                log.exception("[%s] error collecting %s", org, ref)
                stats["errors"] += 1

        if not done and dups_on_page == len(records):
            # A full page of already-stored records: known ground reached.
            done = True

    return stats


def resolve_source_id(dept: dict, sources: list) -> Optional[str]:
    """URL-keyed (ASCII, stable); the em-dash lesson, kept."""
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
            log.error("[%s] no sources row with url=%s (run the contracts seed "
                      "migration, or set %s)", dept["org"],
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
        log.error("Federal contracts run finished with failures in: %s",
                  ", ".join(failures))
        return 1 if successes == 0 else 0
    log.info("Federal contracts run finished successfully")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Federal contract awards collector (open.canada.ca)")
    parser.add_argument("--limit", type=int, default=MAX_DOCS_PER_DEPT,
                        help=f"max NEW documents per department per run "
                             f"(default {MAX_DOCS_PER_DEPT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and parse but write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(limit=args.limit, dry_run=args.dry_run))
