"""City of Toronto tender + award collector on the CKAN open-data API.

Source: the City of Toronto CKAN open-data catalogue at
ckan0.cf.opendata.inter.prod-toronto.ca (docs/toronto-ckan-design.md,
2026-07-25). Toronto's SAP Ariba supplier portal is closed to automation
and irrelevant: the city publishes its bids, awards, and non-competitive
contracts as public open data, the same publisher-open-data route the
Windsor collector rides. Provenance is publisher-published by definition
(the city's own catalogue).

IMPORTANT host note: the API host is ckan0.cf.opendata.inter.prod-toronto.ca.
The human-facing catalogue open.toronto.ca is NOT the API host and 404s
every package_show / datastore call; querying it caused the earlier false
"Toronto has no procurement dataset" 404. Recorded so no future change
regresses to the wrong host.

Three datasets, each read via the CKAN action API (POST datastore_search,
the same canonical pattern as grants_federal_awards):

  - tobids-all-open-solicitations   -> tender_notice (published_on = close)
  - tobids-awarded-contracts        -> award_notice  (published_on = award)
  - tobids-non-competitive-contracts-> award_notice, marked non-competitive
    (sole-source awards: demand signal we collect from no other source)

COLUMN PINNING (docs/toronto-ckan-design.md section 2, operator instruction
2026-07-25): the probe enumerated the datasets but did not dump rows, so the
literal column names for the reference / date / vendor / description / url
fields are resolved at run time from the live datastore `fields` by
_resolve_columns, which LOGS the mapping it chose per dataset. The design
fixes the semantics (what each field must carry); this resolver + the CI
validation dry-run pin the literal names against real data and hold them to
the >= 90% bar before enablement. A field the resolver cannot map logs
loudly and the validation bar catches it; nothing is enabled on a guess.

Politeness is the board-minutes pattern (shared PoliteFetcher: robots per
host, 2s delay, SignalNorthCollector UA). CKAN calls go through post_json so
parameters ride in the JSON body, not the query string. A per-dataset
NEW-row cap drains the multi-year history over successive days; unlike MERX
each row arrives whole in the page (no per-row fetch), so the cap costs
Toronto nothing and only paces our own writes.

LOUD-FAILURE GUARDS: a datastore_search that returns 0 rows for the open
solicitations dataset raises (Toronto always carries active opportunities);
a package_show with no datastore-active resource raises; per-row failures
count toward an error budget and then raise. Silence is never recorded as
truth.

    python -m src.tenders_toronto --dry-run   # fetch + parse, write nothing
    python -m src.tenders_toronto             # collect for real
"""
import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from . import supabase_client
from .board_minutes import PoliteFetcher
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

CKAN_BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
ACTION = f"{CKAN_BASE}/api/3/action"
# The sources-row key (URL-guarded migration). The catalogue host itself, so
# one row covers all three datasets on one publisher.
SOURCE_URL = CKAN_BASE
BUYER_NAME = "City of Toronto"      # must match a resolve_orgs ORG_SEED canonical
# Human-facing dataset page, used as the publisher-artifact URL fallback when
# a row carries no per-solicitation notice link. open.toronto.ca serves these
# HTML pages even though it is not the API host.
PORTAL_DATASET = "https://open.toronto.ca/dataset/{slug}/"

MAX_STORED_CHARS = 20000
PAGE_LIMIT = 100        # rows per datastore_search page
# Per-run cap on NEW rows per dataset. award_notice rows never touch the daily
# forward-extraction budget (they drain via extract-backfill.yml), and each row
# arrives whole in the page (no per-row fetch), so this only paces our own DB
# writes. Steady state at 100 is plenty; a one-time backfill raises it via
# TORONTO_NEW_PER_DATASET to drain the multi-year awarded history (7500+ rows)
# in a few runs. Collection is free (CKAN reads); the awarded extraction cost
# is separate and controlled by the extract-backfill cap.
NEW_PER_DATASET = 100
PAGE_MAX = 60           # safety page ceiling for the steady-state cap
KNOWN_PAGE_STOP = 2     # stop paging after this many all-known pages (steady state)
ERROR_BUDGET = 25       # per-row failures tolerated before loud abort


def _cap() -> int:
    """Effective per-run NEW-row cap: the TORONTO_NEW_PER_DATASET env override
    (one-time backfill) or the steady-state default. Guards against a garbage
    override silently disabling the cap."""
    raw = os.environ.get("TORONTO_NEW_PER_DATASET", "").strip()
    if raw:
        try:
            v = int(raw)
            if v > 0:
                return v
        except ValueError:
            log.warning("TORONTO_NEW_PER_DATASET=%r is not a positive int; "
                        "using default %d", raw, NEW_PER_DATASET)
    return NEW_PER_DATASET

# Each dataset: slug, doc_type, which date the row's published_on carries,
# and whether it is the sole-source (non-competitive) feed.
DATASETS = [
    {"slug": "tobids-all-open-solicitations", "doc_type": "tender_notice",
     "date_role": "close", "non_competitive": False},
    {"slug": "tobids-awarded-contracts", "doc_type": "award_notice",
     "date_role": "award", "non_competitive": False},
    {"slug": "tobids-non-competitive-contracts", "doc_type": "award_notice",
     "date_role": "award", "non_competitive": True},
]

# Semantic-role -> ordered candidate substrings matched case-insensitively
# against the live datastore field names. Longer / more specific phrases come
# first so "solicitation document number" wins over a bare "number", and
# "closing date" wins over a bare "date". The resolver logs its picks.
COLUMN_CANDIDATES = {
    # Toronto's own solicitation / call reference: the procurement CLUSTERING
    # key (the proposer clusters awards to their solicitation on it). It is NOT
    # the row identity: awarded-contracts carries many rows per Document Number
    # (one per successful supplier), so identity keys on this plus supplier +
    # date (see build_payload). Non-competitive contracts have no solicitation
    # reference (sole-source); their per-row key is Workspace Number, mapped to
    # the 'workspace' role below, and reference_number stays NULL for them.
    "reference": ["solicitation document number", "solicitation number",
                  "document number", "notice reference", "reference number",
                  "call number", "rfx number"],
    # Non-competitive contracts' stable per-contract identifier.
    "workspace": ["workspace number", "workspace"],
    "close": ["submission deadline", "closing date", "close date",
              "bid closing", "deadline", "closing"],
    # "award authority obtained date" is the awarded-contracts date field (the
    # date the award authority was obtained); "contract date" is the
    # non-competitive award date. Specific phrases first.
    "award": ["award authority obtained date", "award date", "awarded date",
              "date awarded", "contract date", "date of award"],
    "issue": ["issue date", "issued date", "posting date", "posted date",
              "published date", "start date", "publication date"],
    "vendor": ["awarded supplier", "successful supplier", "supplier name",
               "awarded to", "vendor name", "recipient", "supplier", "vendor"],
    # "reason" is the non-competitive sole-source justification: the signal
    # this dataset uniquely carries, so it stands in as the description there.
    "description": ["solicitation document description", "document description",
                    "solicitation name", "description", "title", "subject",
                    "commodity", "name of solicitation", "reason"],
    "division": ["client division", "buyer division", "division", "client",
                 "buyer name", "buyer", "department"],
    "category": ["high level category", "category", "commodity type"],
    "value": ["total awarded amount", "awarded amount", "contract amount",
              "total value", "award value", "value", "amount"],
    "url": ["notice url", "solicitation url", "url", "link", "web address",
            "href"],
}

# _id / _full_text are CKAN internals, never business columns.
_CKAN_INTERNAL = {"_id", "_full_text", "rank"}


def _resolve_columns(field_ids: list[str]) -> dict:
    """Map semantic roles to the live datastore column names. Returns
    {role: column_name_or_None}. Logged by the caller so the CI dry-run
    reveals exactly which columns were pinned per dataset."""
    lowered = [(f.lower(), f) for f in field_ids if f not in _CKAN_INTERNAL]
    resolved: dict[str, Optional[str]] = {}
    used: set[str] = set()
    for role, cands in COLUMN_CANDIDATES.items():
        picked = None
        for cand in cands:
            for low, orig in lowered:
                if cand in low and orig not in used:
                    picked = orig
                    break
            if picked:
                break
        resolved[role] = picked
        if picked:
            used.add(picked)
    return resolved


# Date shapes Toronto open data has been seen to print. Normalized to
# YYYY-MM-DD at day precision; an unrecognized or empty value returns None
# (never fabricate a date, none beats a wrong date).
_ISO_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})")
_NUM_RE = re.compile(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})")
_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}
_MONTHS.update({m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
     "Nov", "Dec"], 1)})
_TEXT_RE = re.compile(r"^([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})")


def normalize_date(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    m = _ISO_RE.match(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = _TEXT_RE.match(s)
        if m and m.group(1).lower() in _MONTHS:
            y, mo, d = int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2))
        else:
            m = _NUM_RE.match(s)
            if m:
                # Ambiguous MM/DD vs DD/MM: Toronto open data publishes
                # month-first. Guard the ranges and bail on impossible values
                # rather than guess a wrong date.
                mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            else:
                return None
    if not (1 <= mo <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _clean(value) -> str:
    return " ".join(str(value).split()) if value not in (None, "") else ""


def _row_reference(rec: dict, cols: dict) -> Optional[str]:
    if cols.get("reference"):
        ref = _clean(rec.get(cols["reference"]))
        return ref or None
    return None


def _row_date(rec: dict, cols: dict, date_role: str) -> Optional[str]:
    """The event date for this dataset: close for solicitations, award for
    awards, with issue/start as a documented fallback when the primary date
    column is absent or empty (still a real published date, never invented)."""
    primary = cols.get(date_role)
    if primary and normalize_date(rec.get(primary)):
        return normalize_date(rec.get(primary))
    fallback = cols.get("issue")
    if fallback and normalize_date(rec.get(fallback)):
        return normalize_date(rec.get(fallback))
    return None


def _primary_key(rec: dict, cols: dict, ds: dict) -> Optional[str]:
    """The row's stable per-record business key: the solicitation Document
    Number for open and awarded rows, the Workspace Number for non-competitive
    rows (which have no solicitation). Used for the identity hash and the
    validation coverage metric; never the CKAN _id (unstable across refreshes)."""
    col = cols.get("workspace") if ds["non_competitive"] else cols.get("reference")
    val = _clean(rec.get(col)) if col else ""
    return val or None


def _row_body(rec: dict, cols: dict, ds: dict) -> str:
    """Human-readable content assembled from the mapped columns, plus any
    unmapped columns appended as labeled lines so nothing meaningful is
    silently dropped (keep-all discipline extends to the field level)."""
    lines: list[str] = []
    if ds["non_competitive"]:
        lines.append("NON-COMPETITIVE (sole-source) contract.")
    ordered = ["description", "division", "category", "vendor", "value",
               "reference", "workspace", "close", "award", "issue", "url"]
    labels = {"description": "Description", "division": "Division",
              "category": "Category", "vendor": "Supplier", "value": "Value",
              "reference": "Reference", "workspace": "Contract ref",
              "close": "Closing date", "award": "Award date",
              "issue": "Issue date", "url": "Notice"}
    shown: set[str] = set()
    for role in ordered:
        col = cols.get(role)
        if col and _clean(rec.get(col)):
            lines.append(f"{labels[role]}: {_clean(rec.get(col))}")
            shown.add(col)
    for k, v in rec.items():
        if k in _CKAN_INTERNAL or k in shown:
            continue
        cv = _clean(v)
        if cv:
            lines.append(f"{k}: {cv}")
    return "\n".join(lines)[:MAX_STORED_CHARS]


def build_payload(rec: dict, cols: dict, ds: dict, source_id: Optional[str],
                  keywords: Keywords) -> dict:
    ref = _row_reference(rec, cols)
    desc = _clean(rec.get(cols["description"])) if cols.get("description") else ""
    div = _clean(rec.get(cols["division"])) if cols.get("division") else ""
    title_bits = [b for b in (ref, desc or div) if b]
    title = " - ".join(title_bits) if title_bits else f"City of Toronto {ds['doc_type']}"
    if ds["non_competitive"]:
        title = f"Non-competitive: {title}"
    body = _row_body(rec, cols, ds)
    published_on = _row_date(rec, cols, ds["date_role"])
    key = _primary_key(rec, cols, ds)
    vendor = _clean(rec.get(cols["vendor"])) if cols.get("vendor") else ""

    # Identity (content_hash), namespaced per doc_type, never the CKAN _id
    # (unstable across dataset refreshes):
    #  - tender_notice: the solicitation Document Number is unique per row and
    #    is the whole identity, excluding the close date on purpose so an
    #    amended Submission Deadline refreshes the same row (Windsor pattern).
    #  - award_notice: awarded-contracts carries MANY rows per Document Number
    #    (one per successful supplier), so the identity is the key PLUS supplier
    #    PLUS award date; keying on the Document Number alone would collapse
    #    every award under a solicitation into one row. Non-competitive rows key
    #    on Workspace Number the same way, in their own namespace.
    if ds["doc_type"] == "tender_notice":
        identity = f"toronto:{key or (desc + '|' + (published_on or ''))}"
    else:
        ns = "toronto-nc" if ds["non_competitive"] else "toronto-award"
        identity = f"{ns}:" + "|".join([key or "", vendor, published_on or ""])

    url = _clean(rec.get(cols["url"])) if cols.get("url") else ""
    if not url:
        base = PORTAL_DATASET.format(slug=ds["slug"])
        url = f"{base}#{quote(key)}" if key else base

    result = evaluate(title, body, "", keywords)
    return {
        "source_id": source_id,
        "url": url,
        "title": title[:500],
        "doc_type": ds["doc_type"],
        # status is the processing_status ENUM (captured -> extracted/failed),
        # not a business marker, so every row is 'captured'. The sole-source
        # signal rides in the title ("Non-competitive: ...") and the content's
        # first line ("NON-COMPETITIVE (sole-source) contract."), both
        # machine-readable, so downstream can isolate it without a schema change.
        "status": "captured",
        "published_on": published_on,
        # documents.date_precision is NOT NULL (day|month); a row with no
        # parsed date still needs a valid value, and published_on=None carries
        # the null-date signal. Matches board_minutes and the #103 fix.
        "date_precision": "day",
        "reference_number": ref,
        "content_hash": content_hash(identity, ds["doc_type"]),
        "content": body or None,
        "defence_relevant": result.defence_relevant,
        "buyer_name": BUYER_NAME,
    }


def resolve_resource_id(fetcher: PoliteFetcher, slug: str) -> Optional[str]:
    """The datastore-active resource id for a dataset slug, via package_show.
    None only if the dataset has no datastore-active resource (the caller
    raises: we do not silently skip a dataset that should carry rows)."""
    resp = fetcher.get(f"{ACTION}/package_show?id={slug}")
    if resp is None:
        raise RuntimeError(f"[toronto {slug}] robots.txt disallows package_show; "
                           f"refusing to record silence")
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"[toronto {slug}] package_show unsuccessful: {data.get('error')}")
    resources = data["result"].get("resources") or []
    active = [r for r in resources if r.get("datastore_active")]
    if not active:
        raise RuntimeError(
            f"[toronto {slug}] no datastore-active resource "
            f"(formats seen: {[r.get('format') for r in resources]}); "
            f"refusing to record silence")
    return active[0]["id"]


def datastore_page(fetcher: PoliteFetcher, resource_id: str, offset: int,
                   limit: int) -> dict:
    resp = fetcher.post_json(f"{ACTION}/datastore_search", {
        "resource_id": resource_id, "limit": limit, "offset": offset})
    if resp is None:
        raise RuntimeError("[toronto] robots.txt disallows datastore_search; "
                           "refusing to record silence")
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"[toronto] datastore_search unsuccessful: {data.get('error')}")
    return data["result"]


def collect_dataset(ds: dict, fetcher: PoliteFetcher, source_id: Optional[str],
                    keywords: Keywords, dry_run: bool, stats: dict,
                    cap: int) -> dict:
    """Collect one dataset. Returns a per-dataset validation dict."""
    slug = ds["slug"]
    resource_id = resolve_resource_id(fetcher, slug)
    # The page ceiling must cover the cap: a large backfill cap needs to page
    # past the steady-state PAGE_MAX to reach the full history (awarded is 7500+
    # rows). +5 pages of headroom past the cap.
    page_ceiling = max(PAGE_MAX, cap // PAGE_LIMIT + 5)
    tval = {"rows_seen": 0, "new": 0, "date_parsed": 0, "ref_parsed": 0,
            "key_parsed": 0, "pages": 0, "total": None, "cols": {},
            "non_competitive_marked": 0}
    # The row's identity-key role: Workspace Number for non-competitive
    # (sole-source, no solicitation reference), else the solicitation reference.
    key_role = "workspace" if ds["non_competitive"] else "reference"

    offset = 0
    known_pages = 0
    cols: dict = {}
    sample_logged = 0   # cap the per-row dry-run print (first few rows suffice)
    while offset < page_ceiling * PAGE_LIMIT:
        result = datastore_page(fetcher, resource_id, offset, PAGE_LIMIT)
        tval["pages"] += 1
        if tval["total"] is None:
            tval["total"] = result.get("total")
        if not cols:
            field_ids = [f["id"] for f in result.get("fields", [])]
            cols = _resolve_columns(field_ids)
            tval["cols"] = {k: v for k, v in cols.items() if v}
            log.info("[toronto %s] fields=%s", slug, field_ids)
            log.info("[toronto %s] resolved columns: %s", slug, tval["cols"])
            missing = [r for r in (key_role, ds["date_role"], "description")
                       if not cols.get(r)]
            if missing:
                log.warning("[toronto %s] UNMAPPED semantic roles: %s "
                            "(validation bar will catch it)", slug, missing)
        records = result.get("records") or []
        # LOUD FAILURE: the open solicitations dataset always carries active
        # opportunities, so an empty first page means the host or dataset
        # changed, not truth.
        if offset == 0 and not records and not ds["non_competitive"] \
                and ds["date_role"] == "close":
            raise RuntimeError(
                f"[toronto {slug}] datastore_search returned 0 rows on page 1: "
                f"host or dataset changed. Refusing to record silence.")
        if not records:
            break

        page_new = 0
        for rec in records:
            tval["rows_seen"] += 1
            payload = build_payload(rec, cols, ds, source_id, keywords)
            if payload["reference_number"]:
                tval["ref_parsed"] += 1
            if _primary_key(rec, cols, ds):
                tval["key_parsed"] += 1
            if payload["published_on"]:
                tval["date_parsed"] += 1
            if ds["non_competitive"]:
                tval["non_competitive_marked"] += 1
            chash = payload["content_hash"]
            if supabase_client.get_document_by_hash(chash):
                stats["skipped_duplicate"] += 1
                continue
            page_new += 1
            if tval["new"] >= cap:
                continue
            tval["new"] += 1
            try:
                if dry_run:
                    if sample_logged < 3:
                        log.info("[dry-run] %-13s ref=%-18s date=%s :: %s",
                                 ds["doc_type"], payload["reference_number"],
                                 payload["published_on"], payload["title"][:60])
                        sample_logged += 1
                else:
                    supabase_client.insert_document(payload)
                stats["inserted"] += 1
            except Exception:
                stats["errors"] += 1
                log.exception("[toronto %s] row insert failed (ref=%s); continuing",
                              slug, payload.get("reference_number"))
                if stats["errors"] > ERROR_BUDGET:
                    raise RuntimeError(
                        f"[toronto] exceeded the error budget ({stats['errors']} "
                        f"failures): systemic, not transient. Aborting.")

        known_pages = known_pages + 1 if page_new == 0 else 0
        if known_pages >= KNOWN_PAGE_STOP or tval["new"] >= cap:
            break
        if tval["total"] is not None and offset + PAGE_LIMIT >= tval["total"]:
            break
        offset += PAGE_LIMIT

    n = tval["rows_seen"] or 1
    log.info("[toronto %s] rows=%d total=%s new=%d key=%d (%d%%) date=%d (%d%%)",
             slug, tval["rows_seen"], tval["total"], tval["new"],
             tval["key_parsed"], round(100 * tval["key_parsed"] / n),
             tval["date_parsed"], round(100 * tval["date_parsed"] / n))
    return tval


def collect(dry_run: bool = True) -> dict:
    keywords = load_keywords()
    fetcher = PoliteFetcher()
    sources = supabase_client.fetch_rows("sources", "id,url")
    source_id = next((s["id"] for s in sources
                      if (s.get("url") or "").rstrip("/") == SOURCE_URL.rstrip("/")), None)
    if not source_id and not dry_run:
        raise RuntimeError(
            f"no sources row for {SOURCE_URL}; apply the Toronto CKAN sources seed first")

    cap = _cap()
    if cap != NEW_PER_DATASET:
        log.info("[toronto] one-time backfill cap in effect: %d new rows/dataset "
                 "(default %d)", cap, NEW_PER_DATASET)
    stats = {"inserted": 0, "skipped_duplicate": 0, "errors": 0, "per_dataset": {}}
    for ds in DATASETS:
        tval = collect_dataset(ds, fetcher, source_id, keywords, dry_run, stats, cap)
        stats["per_dataset"][ds["slug"]] = tval

    # The enablement bar reads this line (docs/toronto-ckan-design.md section
    # 5). One VALIDATION line per dataset: identity-key + date parse rates
    # against the 90% bar, plus the resolved column mapping so the pin is
    # visible. key_parsed is the row's identity key (solicitation Document
    # Number, or Workspace Number for non-competitive); ref_parsed is the
    # solicitation reference specifically (0% for non-competitive by nature).
    for ds in DATASETS:
        tval = stats["per_dataset"][ds["slug"]]
        n = tval["rows_seen"] or 1
        extra = ""
        if ds["non_competitive"]:
            extra = f" non_competitive_marked={tval['non_competitive_marked']}"
        log.info("VALIDATION [toronto:%s]: rows=%d total=%s key_parsed=%d (%d%%) "
                 "ref_parsed=%d (%d%%) date_parsed=%d (%d%%) columns=%s%s",
                 ds["slug"], tval["rows_seen"], tval["total"],
                 tval["key_parsed"], round(100 * tval["key_parsed"] / n),
                 tval["ref_parsed"], round(100 * tval["ref_parsed"] / n),
                 tval["date_parsed"], round(100 * tval["date_parsed"] / n),
                 tval["cols"], extra)
    log.info("toronto: %s%s", {k: v for k, v in stats.items() if k != "per_dataset"},
             " (DRY RUN)" if dry_run else "")
    if not dry_run and source_id:
        supabase_client.update_source_last_collected(
            source_id, datetime.now(timezone.utc))
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="City of Toronto CKAN open-data tender/award collector")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and parse but write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    collect(dry_run=args.dry_run)
    sys.exit(0)
