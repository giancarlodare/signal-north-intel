"""Google News RSS collector for coverage wave detection.

Google News provides free RSS feeds for any search query. We use this to
monitor topic-region pairs that matter to Signal North's Pressure Index:
  - "auto theft Brampton"
  - "police body worn cameras Canada"
  - "PSBN public safety broadband"
  - "drone pilot police Ontario"

Each feed returns recent headlines. We track volume over time to detect
"coverage waves" — sustained media attention that precedes government action.

This collector does NOT scrape article content (no paywall issues). It only
captures headline + source + date, which is sufficient for volume tracking.
"""
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import feedparser

from .hashing import content_hash
from . import supabase_client

log = logging.getLogger(__name__)

# Topic-region pairs for coverage wave monitoring.
# Each becomes a Google News RSS query. The engine should eventually
# generate these dynamically based on what's in the signals table.
MONITORING_QUERIES = [
    # Crime/policing topics that precede procurement
    {"query": "auto theft Canada police", "category": "fleet", "region": "Canada"},
    {"query": "auto theft Brampton Peel", "category": "fleet", "region": "ON"},
    {"query": "gun violence Toronto police", "category": "use-of-force", "region": "ON"},
    {"query": "rural crime RCMP Alberta", "category": "radios-comms", "region": "AB"},
    {"query": "cybersecurity attack Canada government", "category": "cyber", "region": "Canada"},
    
    # Technology/procurement topics
    {"query": "body worn camera police Canada", "category": "body-worn-cameras", "region": "Canada"},
    {"query": "police drone program Canada", "category": "drones-rpas", "region": "Canada"},
    {"query": "PSBN public safety broadband network", "category": "radios-comms", "region": "Canada"},
    {"query": "police radio interoperability Canada", "category": "radios-comms", "region": "Canada"},
    {"query": "ALPR licence plate recognition Canada", "category": "alpr", "region": "Canada"},
    {"query": "next generation 911 Canada", "category": "records-cad", "region": "Canada"},
    
    # Defence/dual-use
    {"query": "Canada defence procurement", "category": "c4isr", "region": "Canada"},
    {"query": "Canadian military drone UAV", "category": "uncrewed-defence", "region": "Canada"},
    {"query": "Mark Carney defence spending", "category": "c4isr", "region": "Canada"},
    {"query": "NATO Canada defence investment", "category": "c4isr", "region": "Canada"},
    {"query": "NORAD modernization Canada", "category": "c4isr", "region": "Canada"},
    
    # Political pressure signals
    {"query": "police funding Canada budget", "category": "technology", "region": "Canada"},
    {"query": "community safety funding Ontario", "category": "technology", "region": "ON"},
    {"query": "bail reform Canada police", "category": "ai-analytics", "region": "Canada"},
    
    # Events that could trigger procurement
    {"query": "FIFA World Cup 2026 security Canada", "category": "radios-comms", "region": "Canada"},
    {"query": "G7 security Canada", "category": "surveillance", "region": "Canada"},
]


def _google_news_rss_url(query: str) -> str:
    """Build a Google News RSS URL for a search query."""
    encoded = urllib.parse.quote_plus(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-CA&gl=CA&ceid=CA:en"


def _parse_entry_date(entry) -> Optional[str]:
    """Extract date from RSS entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                return dt.date().isoformat()
            except (ValueError, TypeError):
                continue
    return None


def collect_news_for_query(query_config: dict, news_source_id: str) -> dict:
    """Collect Google News results for a single query."""
    stats = {"seen": 0, "inserted": 0, "skipped_duplicate": 0}
    
    query = query_config["query"]
    url = _google_news_rss_url(query)
    
    feed = feedparser.parse(url)
    
    if feed.bozo and not feed.entries:
        log.warning("Feed error for query '%s': %s", query, feed.bozo_exception)
        return stats
    
    for entry in feed.entries:
        stats["seen"] += 1
        
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        source_name = getattr(entry, "source", {})
        if hasattr(source_name, "title"):
            source_name = source_name.title
        else:
            source_name = ""
        published_on = _parse_entry_date(entry)
        
        # Deduplicate
        chash = content_hash(link or title, "media_article")
        existing = supabase_client.get_document_by_hash(chash)
        if existing:
            stats["skipped_duplicate"] += 1
            continue
        
        # Insert as a media_article document
        doc_payload = {
            "source_id": news_source_id,
            "url": link,
            "title": f"[{source_name}] {title}"[:500] if source_name else title[:500],
            "doc_type": "media_article",
            "status": "captured",
            "published_on": published_on,
            "content_hash": chash,
        }
        
        try:
            supabase_client.insert_document(doc_payload)
            stats["inserted"] += 1
        except Exception as e:
            log.warning("Failed to insert news doc '%s': %s", title[:40], e)
    
    return stats


def run_news_collection(news_source_id: str = None) -> int:
    """Run Google News collection for all monitoring queries.
    
    Args:
        news_source_id: The source ID to use for news documents.
                       If None, will create/find a 'Google News — Coverage Monitor' source.
    """
    now = datetime.now(timezone.utc)
    total_stats = {"queries": 0, "seen": 0, "inserted": 0, "skipped_duplicate": 0}
    
    for qconfig in MONITORING_QUERIES:
        try:
            stats = collect_news_for_query(qconfig, news_source_id)
            total_stats["queries"] += 1
            total_stats["seen"] += stats["seen"]
            total_stats["inserted"] += stats["inserted"]
            total_stats["skipped_duplicate"] += stats["skipped_duplicate"]
            log.info("News '%s': seen=%d, inserted=%d", 
                     qconfig["query"], stats["seen"], stats["inserted"])
        except Exception:
            log.exception("News collection failed for query: %s", qconfig["query"])
    
    log.info("News collection complete: %s", total_stats)
    return 0


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Requires a news_source_id to be passed or created
    sys.exit(run_news_collection())
