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
from .canadabuys import fetch_csv_rows, find_column
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash
from .vendors import extract_contract_terms

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _clean(value: str | None) -> str:
    return (value or "").strip()


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


def process_tender_notices(source_id: str, keywords: Keywords) -> dict:
    stats = {"seen": 0, "kept": 0, "inserted": 0, "skipped_duplicate": 0}
    rows = fetch_csv_rows(config.NEW_TENDER_NOTICES_URL)
    if not rows:
        return stats

    fields = list(rows[0].keys())
    title_col = find_column(fields, "title")
    desc_col = find_description_column(fields)
    ref_col = find_column(fields, "reference", "number") or find_column(fields, "solicitation", "number")
    pub_date_col = find_column(fields, "publication", "date")
    unspsc_col = find_column(fields, "unspsc", "code") or find_column(fields, "unspsc")

    for row in rows:
        stats["seen"] += 1
        title = _clean(row.get(title_col)) if title_col else ""
        description = _clean(row.get(desc_col)) if desc_col else ""
        reference = _clean(row.get(ref_col)) if ref_col else ""
        published_on = _parse_date(row.get(pub_date_col)) if pub_date_col else None
        unspsc_code = _clean(row.get(unspsc_col)) if unspsc_col else ""

        result = evaluate(title, description, unspsc_code, keywords)
        if not result.kept:
            continue
        stats["kept"] += 1

        url = config.TENDER_NOTICE_URL_TEMPLATE.format(reference=reference or title)
        chash = content_hash(reference or url, "tender_notice")

        if supabase_client.get_document_by_hash(chash):
            stats["skipped_duplicate"] += 1
            continue

        supabase_client.insert_document({
            "source_id": source_id,
            "url": url,
            "title": title,
            "doc_type": "tender_notice",
            "published_on": published_on,
            "jurisdiction": config.JURISDICTION,
            "content_hash": chash,
            "defence_relevant": result.defence_relevant,
        })
        stats["inserted"] += 1

    return stats


def process_award_notices(source_id: str, keywords: Keywords) -> dict:
    stats = {"seen": 0, "kept": 0, "inserted": 0, "skipped_duplicate": 0}
    rows = fetch_csv_rows(config.AWARD_NOTICES_URL)
    if not rows:
        return stats

    fields = list(rows[0].keys())
    title_col = find_column(fields, "title")
    desc_col = find_description_column(fields)
    ref_col = find_column(fields, "reference", "number") or find_column(fields, "solicitation", "number")
    contract_date_col = find_column(fields, "contract", "date") or find_column(fields, "award", "date")
    unspsc_col = find_column(fields, "unspsc", "code") or find_column(fields, "unspsc")
    vendor_col = find_column(fields, "vendor", "name") or find_column(fields, "supplier", "name")
    comments_col = find_column(fields, "comments")

    for row in rows:
        stats["seen"] += 1
        title = _clean(row.get(title_col)) if title_col else ""
        description = _clean(row.get(desc_col)) if desc_col else ""
        reference = _clean(row.get(ref_col)) if ref_col else ""
        published_on = _parse_date(row.get(contract_date_col)) if contract_date_col else None
        unspsc_code = _clean(row.get(unspsc_col)) if unspsc_col else ""
        vendor_name = _clean(row.get(vendor_col)) if vendor_col else ""
        comments = _clean(row.get(comments_col)) if comments_col else ""

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
            "published_on": published_on,
            "jurisdiction": config.JURISDICTION,
            "content_hash": chash,
            "defence_relevant": result.defence_relevant,
        })
        stats["inserted"] += 1

        terms = extract_contract_terms(f"{description} {comments}")
        vendor_id = supabase_client.find_or_create_vendor(vendor_name) if vendor_name else None

        supabase_client.insert_contract_award({
            "document_id": document["id"],
            "vendor_id": vendor_id,
            "start_on": terms.start_on,
            "end_on": terms.end_on,
            "option_years": terms.option_years,
            "final_end_on": terms.final_end_on,
        })

    return stats


def run() -> int:
    keywords = load_keywords()
    log.info(
        "Loaded %d general keywords, %d defence keywords",
        len(keywords.general), len(keywords.defence),
    )

    tender_stats = process_tender_notices(config.TENDER_SOURCE_ID, keywords)
    log.info("Tender notices: %s", tender_stats)

    award_stats = process_award_notices(config.AWARD_SOURCE_ID, keywords)
    log.info("Award notices: %s", award_stats)

    now = datetime.now(timezone.utc)
    supabase_client.update_source_last_collected(config.TENDER_SOURCE_ID, now)
    supabase_client.update_source_last_collected(config.AWARD_SOURCE_ID, now)
    log.info("Updated sources.last_collected_at for both source rows")

    return 0


if __name__ == "__main__":
    sys.exit(run())
