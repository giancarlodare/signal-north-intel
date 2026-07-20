"""Daily CanadaBuys collector entry point.

Downloads the new-tender-notices and current-award-notices open-data CSVs,
keeps only public-safety / security / dual-use-defence relevant rows, and
writes them into Supabase (documents + contract_awards + vendors), skipping
anything already inserted in a previous run.
"""
import logging
import sys
from datetime import datetime, timezone

from dateutil import parser as dateparser

from . import config, supabase_client
from .canadabuys import (build_tender_content, fetch_csv_rows, find_column,
                         parse_unspsc_codes)
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash
from .vendors import extract_contract_terms

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _parse_value(value: str | None):
    """Parse a contract value like '$1,234,567.00' into a float, or None."""
    value = _clean(value).replace("$", "").replace(",", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_date(value: str | None):
    value = _clean(value)
    if not value:
        return None
    try:
        return dateparser.parse(value, fuzzy=True).date()
    except (ValueError, OverflowError):
        log.warning("Could not parse date %r", value)
        return None


def find_description_column(fieldnames):
    candidates = [
        f for f in fieldnames
        if "description" in f.lower() and "unspsc" not in f.lower() and "gsin" not in f.lower()
    ]
    if not candidates:
        return None
    for c in candidates:
        if c.lower().endswith("-eng"):
            return c
    return candidates[0]


def parse_tender_row(row: dict, fields: list) -> dict:
    """Extract every enrichment field from one tender CSV row (pure).

    The event date is the CLOSE date (docs/canadabuys-enrichment-design.md):
    the brief labels tender dates "Tender closes ...", so the publication
    date as published_on rendered a false date and locked federal tenders
    out of the imminent window. A notice with no close date gets
    published_on=None (the standing rule: never silently substitute another
    date), with the publication date preserved in the content header.
    """
    def col(*subs):
        return find_column(fields, *subs)

    def val(*subs):
        c = col(*subs)
        return _clean(row.get(c)) if c else ""

    title = val("title")
    description = _clean(row.get(find_description_column(fields) or "", ""))
    cb_reference = val("reference", "number")     # cb-... row id, drives the URL
    solicitation = val("solicitation", "number")  # the procurement-spine hard key
    publication = _parse_date(val("publication", "date"))
    closing = _parse_date(val("closing", "date"))
    amendment_no = val("amendment", "number")
    amendment_date = val("amendment", "date")
    buyer = val("contractingentityname") or val("contracting", "entity", "name")
    end_user = val("enduserentitiesname") or val("end", "user", "entities", "name")
    # The code column is literally named "unspsc"; a substring match would
    # prefer unspscDescription-eng (the -eng suffix wins ties), so match the
    # bare name exactly and only then fall back to a substring search.
    unspsc_col = next((f for f in fields if f.strip().lower() == "unspsc"), None) \
        or col("unspsc", "code")
    unspsc_raw = row.get(unspsc_col, "") if unspsc_col else ""
    unspsc_codes = parse_unspsc_codes(unspsc_raw)
    unspsc_desc = val("unspscdescription")

    facts = {
        "Solicitation number": solicitation,
        "Buyer": buyer,
        "End user": end_user,
        "Published": publication.isoformat() if publication else "",
        "Closing date": val("closing", "date"),
        "Status": val("tenderstatus") or val("tender", "status"),
        "Notice type": val("noticetype") or val("notice", "type"),
        "Procurement method": val("procurementmethod") or val("procurement", "method"),
        "Expected contract start": val("expectedcontractstart") or val("contract", "start"),
        "Expected contract end": val("expectedcontractend") or val("contract", "end"),
        "Regions of delivery": val("regionsofdelivery") or val("regions", "delivery"),
        "Amendment": (f"{amendment_no} ({amendment_date})" if amendment_date
                      else (amendment_no if amendment_no not in ("", "000") else "")),
        "UNSPSC": "; ".join(
            f"{c} {d}".strip() for c, d in zip(
                unspsc_codes,
                [s.strip() for s in unspsc_desc.replace("\n", "*").split("*") if s.strip()]
                + [""] * len(unspsc_codes))) or "; ".join(unspsc_codes),
    }
    return {
        "title": title,
        "description": description,
        "cb_reference": cb_reference,
        "solicitation": solicitation,
        "published_on": closing,
        "unspsc_codes": unspsc_codes,
        "unspsc_raw": unspsc_raw or "",
        "buyer_name": buyer or (end_user or None),
        "amendment_no": amendment_no,
        "content": build_tender_content(facts, description),
    }


def process_tender_notices(source_id: str, keywords: Keywords) -> dict:
    stats = {"seen": 0, "kept": 0, "inserted": 0, "skipped_duplicate": 0,
             "refreshed_amendment": 0}
    rows = fetch_csv_rows(config.NEW_TENDER_NOTICES_URL)
    if not rows:
        return stats
    fields = list(rows[0].keys())

    for row in rows:
        stats["seen"] += 1
        t = parse_tender_row(row, fields)

        result = evaluate(t["title"], t["description"], t["unspsc_raw"], keywords)
        if not result.kept:
            continue
        stats["kept"] += 1

        reference = t["cb_reference"]
        url = config.TENDER_NOTICE_URL_TEMPLATE.format(reference=reference or t["title"])
        chash = content_hash(reference or url, "tender_notice")

        payload = {
            "title": t["title"],
            "published_on": t["published_on"],
            "reference_number": t["solicitation"] or None,
            "content": t["content"],
            "unspsc_codes": t["unspsc_codes"] or None,
            "buyer_name": t["buyer_name"],
        }

        existing = supabase_client.get_document_by_hash(chash)
        if existing:
            # One solicitation, one document. An amendment row (number > 000)
            # refreshes the stored notice in place: amendments move close
            # dates, and a stale close date is a false date shown to a
            # reader. A plain re-listing (amendment 000) stays a skip.
            if t["amendment_no"] not in ("", "000"):
                supabase_client.update_row("documents", existing["id"], payload)
                stats["refreshed_amendment"] += 1
            else:
                stats["skipped_duplicate"] += 1
            continue

        supabase_client.insert_document({
            "source_id": source_id,
            "url": url,
            "doc_type": "tender_notice",
            "status": "captured",
            "content_hash": chash,
            "defence_relevant": result.defence_relevant,
            **payload,
        })
        stats["inserted"] += 1

    return stats


def process_award_notices(source_id: str, keywords: Keywords) -> dict:
    stats = {"seen": 0, "kept": 0, "inserted": 0, "skipped_duplicate": 0}
    # Usually just the current fiscal year's file; during the post-April-1
    # grace window this also includes the previous year's file so late-posted
    # prior-year awards aren't lost. Dedupe by content_hash makes any overlap
    # between the files (or with earlier runs) harmless.
    for url in config.award_notice_urls():
        rows = fetch_csv_rows(url)
        if rows:
            _process_award_rows(rows, source_id, keywords, stats)
    return stats


def _process_award_rows(rows: list, source_id: str, keywords: Keywords, stats: dict) -> None:
    fields = list(rows[0].keys())
    title_col = find_column(fields, "title")
    desc_col = find_description_column(fields)
    ref_col = find_column(fields, "reference", "number") or find_column(fields, "solicitation", "number")
    award_date_col = (
        find_column(fields, "award", "date")
        or find_column(fields, "contract", "date")
        or find_column(fields, "publication", "date")
    )
    unspsc_col = find_column(fields, "unspsc", "code") or find_column(fields, "unspsc")
    vendor_col = find_column(fields, "vendor", "name") or find_column(fields, "supplier", "name")
    value_col = (
        find_column(fields, "contract", "value")
        or find_column(fields, "total", "value")
        or find_column(fields, "value")
    )

    for row in rows:
        stats["seen"] += 1
        title = _clean(row.get(title_col)) if title_col else ""
        description = _clean(row.get(desc_col)) if desc_col else ""
        reference = _clean(row.get(ref_col)) if ref_col else ""
        awarded_on = _parse_date(row.get(award_date_col)) if award_date_col else None
        unspsc_code = _clean(row.get(unspsc_col)) if unspsc_col else ""
        vendor_name = _clean(row.get(vendor_col)) if vendor_col else ""
        value_cad = _parse_value(row.get(value_col)) if value_col else None

        result = evaluate(title, description, unspsc_code, keywords)
        if not result.kept:
            continue
        stats["kept"] += 1

        url = config.AWARD_NOTICE_URL_TEMPLATE.format(reference=reference or title)
        chash = content_hash(reference or url, "award_notice")

        existing = supabase_client.get_document_by_hash(chash)
        if existing:
            stats["skipped_duplicate"] += 1
            continue

        document = supabase_client.insert_document({
            "source_id": source_id,
            "url": url,
            "title": title,
            "doc_type": "award_notice",
            "status": "captured",
            "published_on": awarded_on,
            "content_hash": chash,
            "defence_relevant": result.defence_relevant,
        })
        stats["inserted"] += 1

        # Register/match the vendor in the vendors table and link the award
        # to it. contract_awards keeps both the raw vendor_name (as reported
        # on the notice) and vendor_id (the normalized vendors row), so we
        # capture the returned id here rather than discarding it.
        vendor_id = None
        if vendor_name:
            vendor_id = supabase_client.find_or_create_vendor(vendor_name)

        # Contract length / option years aren't in the CSV columns; they're
        # stated in the notice free text, so extract what we can from the
        # description to fill start_on/end_on/option_years/final_end_on.
        terms = extract_contract_terms(description)

        # organization_id, category_id, and recompete_opportunity_id are
        # intentionally left unset here: the raw collector only writes what it
        # can observe directly on the notice. Organization and category
        # resolution happens in the extraction step, and
        # recompete_opportunity_id is populated later by the Recompete Radar
        # backfill job.
        supabase_client.insert_contract_award({
            "document_id": document["id"],
            "vendor_name": vendor_name or None,
            "vendor_id": vendor_id,
            "description": description or None,
            "value_cad": value_cad,
            "awarded_on": awarded_on,
            "reference_no": reference or None,
            "start_on": terms.start_on,
            "end_on": terms.end_on,
            "option_years": terms.option_years,
            "final_end_on": terms.final_end_on,
        })


def run() -> int:
    keywords = load_keywords()
    log.info(
        "Loaded %d general keywords, %d defence keywords",
        len(keywords.general), len(keywords.defence),
    )

    now = datetime.now(timezone.utc)
    failures = []

    # Tender and award feeds are processed independently so a problem with
    # one (e.g. a bad URL or a schema mismatch) never discards the other's
    # progress. Each feed's last_collected_at is only updated if it succeeded.
    try:
        tender_stats = process_tender_notices(config.TENDER_SOURCE_ID, keywords)
        log.info("Tender notices: %s", tender_stats)
        supabase_client.update_source_last_collected(config.TENDER_SOURCE_ID, now)
    except Exception:
        log.exception("Tender notice collection failed")
        failures.append("tender notices")

    try:
        award_stats = process_award_notices(config.AWARD_SOURCE_ID, keywords)
        log.info("Award notices: %s", award_stats)
        supabase_client.update_source_last_collected(config.AWARD_SOURCE_ID, now)
    except Exception:
        log.exception("Award notice collection failed")
        failures.append("award notices")

    if failures:
        log.error("Run finished with failures in: %s", ", ".join(failures))
        return 1

    log.info("Run finished successfully")
    return 0


if __name__ == "__main__":
    sys.exit(run())
