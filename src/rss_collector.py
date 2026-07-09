"""RSS feed collector for government newsrooms and other RSS-based sources.

Collects from:
  - Ontario Newsroom (Solicitor General)
  - Public Safety Canada News
  - Any future RSS source added to the sources table with collector='rss'

Each entry becomes a document row. Defence-relevance tagging uses the same
keyword filter as the CanadaBuys collector.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import feedparser

from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash
from . import config, supabase_client

log = logging.getLogger(__name__)

# RSS feed URLs mapped to source IDs (from the sources table)
RSS_FEEDS = {
    "cd9828f5-4b45-4c71-9b6d-9963c490415a": {
        "name": "Ontario Newsroom — Solicitor General",
        "url": "https://news.ontario.ca/newsroom/en/rss",
        "filter_terms": ["solicitor general", "public safety", "police", "corrections",
                         "community safety", "fire", "emergency", "justice"],
    },
    "a4ea7d3a-857a-41df-8ea9-379281f152a9": {
        "name": "Public Safety Canada — News",
        "url": "https://www.canada.ca/en/public-safety-canada.atom.xml",
        "filter_terms": [],  # All entries from PS Canada are relevant
    },
}

# Additional newsroom feeds to register as new sources
ADDITIONAL_FEEDS = [
    {
        "name": "Canada.ca — Department of National Defence News",
        "url": "https://www.canada.ca/en/department-national-defence.atom.xml",
        "source_type": "newsroom",
        "jurisdiction": "federal",
        "province": None,
        "collector": "rss",
        "cadence": "daily",
        "filter_terms": [],
    },
    {
        "name": "Canada.ca — RCMP News",
        "url": "https://www.canada.ca/en/royal-canadian-mounted-police.atom.xml",
        "source_type": "newsroom",
        "jurisdiction": "federal",
        "province": None,
        "collector": "rss",
        "cadence": "daily",
        "filter_terms": [],
    },
    {
        "name": "BC Government — Public Safety News",
        "url": "https://news.gov.bc.ca/ministries/public-safety-solicitor-general/atom",
        "source_type": "newsroom",
        "jurisdiction": "provincial",
        "province": "BC",
        "collector": "rss",
        "cadence": "daily",
        "filter_terms": [],
    },
    {
        "name": "Alberta Government News — Public Safety",
        "url": "https://www.alberta.ca/news.rss",
        "source_type": "newsroom",
        "jurisdiction": "provincial",
        "province": "AB",
        "collector": "rss",
        "cadence": "daily",
        "filter_terms": ["police", "public safety", "rcmp", "corrections", "emergency",
                         "fire", "justice", "security"],
    },
]


def _parse_entry_date(entry) -> Optional[str]:
    """Extract a date from an RSS/Atom entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                return dt.date().isoformat()
            except (ValueError, TypeError):
                continue
    return None


def _entry_matches_filter(entry, filter_terms: list) -> bool:
    """Check if an RSS entry matches any of the filter terms."""
    if not filter_terms:
        return True  # No filter = keep everything
    text = f"{getattr(entry, 'title', '')} {getattr(entry, 'summary', '')}".lower()
    return any(term.lower() in text for term in filter_terms)


def collect_feed(source_id: str, feed_config: dict, keywords: Keywords) -> dict:
    """Collect a single RSS feed and insert new documents."""
    stats = {"seen": 0, "kept": 0, "inserted": 0, "skipped_duplicate": 0}
    
    feed_url = feed_config["url"]
    filter_terms = feed_config.get("filter_terms", [])
    
    log.info("Fetching RSS feed: %s", feed_config["name"])
    feed = feedparser.parse(feed_url)
    
    if feed.bozo and not feed.entries:
        log.warning("Feed parse error for %s: %s", feed_url, feed.bozo_exception)
        return stats
    
    for entry in feed.entries:
        stats["seen"] += 1
        
        title = getattr(entry, "title", "").strip()
        summary = getattr(entry, "summary", "").strip()
        link = getattr(entry, "link", "").strip()
        published_on = _parse_entry_date(entry)
        
        # Apply source-specific filter first
        if not _entry_matches_filter(entry, filter_terms):
            continue
        
        # Apply keyword relevance filter (same as CanadaBuys)
        result = evaluate(title, summary, "", keywords)
        if not result.kept:
            # Even if keywords don't match, keep it if source-specific filter passed
            # and the source has no filter_terms (meaning everything is relevant)
            if filter_terms:
                continue
        
        stats["kept"] += 1
        
        # Deduplicate
        chash = content_hash(link or title, "news_release")
        existing = supabase_client.get_document_by_hash(chash)
        if existing:
            stats["skipped_duplicate"] += 1
            continue
        
        # Insert document
        doc_payload = {
            "source_id": source_id,
            "url": link,
            "title": title[:500] if title else None,
            "doc_type": "news_release",
            "status": "captured",
            "published_on": published_on,
            "content_hash": chash,
        }
        
        # Add defence_relevant flag if the document table supports it
        if result.defence_relevant:
            doc_payload["defence_relevant"] = True
        
        try:
            supabase_client.insert_document(doc_payload)
            stats["inserted"] += 1
        except Exception as e:
            log.warning("Failed to insert document '%s': %s", title[:50], e)
    
    return stats


def run_rss_collection() -> int:
    """Run collection for all configured RSS feeds."""
    keywords = load_keywords()
    now = datetime.now(timezone.utc)
    failures = []
    
    for source_id, feed_config in RSS_FEEDS.items():
        try:
            stats = collect_feed(source_id, feed_config, keywords)
            log.info("RSS %s: %s", feed_config["name"], stats)
            supabase_client.update_source_last_collected(source_id, now)
        except Exception:
            log.exception("RSS collection failed for %s", feed_config["name"])
            failures.append(feed_config["name"])
    
    if failures:
        log.error("RSS run finished with failures: %s", ", ".join(failures))
        return 1
    
    log.info("RSS collection finished successfully")
    return 0


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run_rss_collection())
