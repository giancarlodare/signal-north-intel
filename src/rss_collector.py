"""Government newsroom RSS/Atom collector.

Official government newsrooms ONLY — the publisher's own feed on the
publisher's own domain. No Google News, no aggregators, no search-query feeds.
(This rebuilds the concept from the quarantined first-generation collector,
whose Google News rows were provenance-broken and whose empty filter_terms
collected everything.)

Standards applied:
  - Keyword filtering is ON for every feed, no exceptions: an entry must pass
    the same keywords.txt relevance filter the CanadaBuys collector uses.
    Broad multi-ministry feeds additionally carry per-feed scope terms.
  - Publisher URLs only: an entry is dropped unless its link is on the feed's
    allowed domains — a feed that syndicates or redirects elsewhere can't
    smuggle in third-party URLs.
  - Full-body fetch where the feed truncates: if an entry's summary is cut
    short, the article page is fetched (robots.txt + polite delay via the
    shared PoliteFetcher) and its text stored in documents.content so
    extraction reads the real release, not a teaser.
  - content_hash dedupe identical to the other collectors.
  - Feeds are hardcoded configuration — nothing auto-adds a source
    (discovery is a separate propose-then-approve job).

Verify feed configs with a zero-write run:  python -m src.rss_collector --dry-run
"""
import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from . import supabase_client
from .board_minutes import PoliteFetcher, html_to_text
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

MAX_ENTRIES_PER_FEED = 50
MAX_STORED_CHARS = 400_000
# A summary this short (or ending in an ellipsis) is treated as truncated and
# triggers a full-body fetch of the article page.
TRUNCATION_MIN_CHARS = 400
_ELLIPSES = ("...", "…", "[...]", "[…]", "(...)", "Read more", "read more")

# Canada.ca department news feeds come from the Canada News Centre API — the
# documented custom-feed mechanism. CI probe 2026-07-11 confirmed these return
# valid Atom XML, while the previously-configured
# https://www.canada.ca/en/<dept>.atom.xml URLs return an HTML "Not Found"
# page with HTTP 200, which is what broke every feed on the first live run.
_GC_NEWS_API = ("https://api.io.canada.ca/io-server/gc/news/en/v2"
                "?dept={dept}&sort=publishedDate&orderBy=desc&pick=50"
                "&format=atom&atomtitle={title}")

FEEDS = [
    {
        "name": "Ontario Newsroom",
        # PARKED 2026-07-11: news.ontario.ca is a JS single-page app; every
        # candidate feed path (newsroom/en/rss, en/rss, mcscs/en/rss, en/feed —
        # CI probe) returns the app's HTML shell, not a feed. Unpark once a
        # real feed URL is found (operator browser check) or an API adapter
        # for their JSON backend is built as a reviewed follow-up.
        "enabled": False,
        "parked_reason": "SPA shell at every candidate feed path (probe 2026-07-11)",
        "feed_url": "https://news.ontario.ca/newsroom/en/rss",
        "allowed_hosts": ["news.ontario.ca", "www.ontario.ca"],
        # Multi-ministry firehose: scope to public-safety business first,
        # then the keywords.txt filter applies on top.
        "scope_terms": ["solicitor general", "public safety", "police",
                        "corrections", "community safety", "fire", "emergency",
                        "justice", "opp"],
        "source_name_candidates": ["Ontario Newsroom — Solicitor General",
                                   "Ontario Newsroom"],
        "source_id_env": "ONTARIO_NEWSROOM_SOURCE_ID",
    },
    {
        "name": "Public Safety Canada — News",
        "feed_url": _GC_NEWS_API.format(dept="publicsafetycanada",
                                        title="Public%20Safety%20Canada"),
        "allowed_hosts": ["www.canada.ca", "canada.ca"],
        "scope_terms": [],   # single-department feed; keywords.txt still applies
        "source_name_candidates": ["Public Safety Canada — News",
                                   "Public Safety Canada News"],
        "source_id_env": "PS_CANADA_NEWS_SOURCE_ID",
    },
    {
        "name": "Department of National Defence — News",
        # No working dept= code exists for DND (probes 2026-07-11: every
        # candidate returns an empty feed; entries carry no department field
        # to learn the code from). The unfiltered GC News Centre feed DOES
        # carry DND items, and their publisher URLs identify the department —
        # so pull unfiltered and keep only /department-national-defence/ links.
        "feed_url": ("https://api.io.canada.ca/io-server/gc/news/en/v2"
                     "?sort=publishedDate&orderBy=desc&pick=100&format=atom"
                     "&atomtitle=GC%20News"),
        "link_path_contains": "/department-national-defence/",
        "allowed_hosts": ["www.canada.ca", "canada.ca", "www.forces.gc.ca"],
        "scope_terms": [],
        "source_name_candidates": ["Department of National Defence — News",
                                   "DND News", "Canada.ca — Department of National Defence News"],
        "source_id_env": "DND_NEWS_SOURCE_ID",
    },
    {
        "name": "RCMP — News",
        # PARKED 2026-07-11: no functioning feed found anywhere. The GC News
        # Centre carries no RCMP items in the recent window (unfiltered probe),
        # every dept= candidate returns empty, and rcmp-grc.gc.ca serves HTML
        # at every feed-shaped path. Unpark path: an HTML collector for
        # rcmp-grc.gc.ca/en/news (reviewed follow-up; see docs/ROADMAP.md).
        "enabled": False,
        "parked_reason": "no functioning RSS/Atom feed found (probes 2026-07-11)",
        "feed_url": _GC_NEWS_API.format(dept="royalcanadianmountedpolice",
                                        title="RCMP"),
        "allowed_hosts": ["www.canada.ca", "canada.ca", "www.rcmp-grc.gc.ca", "rcmp-grc.gc.ca"],
        "scope_terms": [],
        "source_name_candidates": ["RCMP — News", "RCMP News",
                                   "Canada.ca — RCMP News"],
        "source_id_env": "RCMP_NEWS_SOURCE_ID",
    },
]


def _norm(name: str) -> str:
    return " ".join((name or "").split()).lower()


def resolve_source_id(feed: dict, sources: list) -> Optional[str]:
    import os
    override = os.environ.get(feed["source_id_env"], "").strip()
    if override:
        return override
    candidates = {_norm(c) for c in feed["source_name_candidates"]}
    for row in sources:
        if _norm(row.get("name", "")) in candidates:
            return row["id"]
    return None


def entry_date(entry) -> Optional[str]:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc).date().isoformat()
            except (ValueError, TypeError):
                continue
    return None


def is_publisher_url(url: str, allowed_hosts: list) -> bool:
    host = urlparse(url).netloc.lower()
    return host in {h.lower() for h in allowed_hosts}


def matches_scope(entry_text: str, scope_terms: list) -> bool:
    if not scope_terms:
        return True
    lower = entry_text.lower()
    return any(term.lower() in lower for term in scope_terms)


def looks_truncated(summary: str) -> bool:
    s = (summary or "").strip()
    if len(s) < TRUNCATION_MIN_CHARS:
        return True
    return any(s.endswith(e) or s.lower().endswith(e.lower()) for e in _ELLIPSES)


def collect_feed(feed: dict, entries: list, source_id: str, keywords: Keywords,
                 fetcher: PoliteFetcher, limit: int, dry_run: bool) -> dict:
    stats = {"seen": 0, "kept": 0, "inserted": 0, "skipped_duplicate": 0,
             "dropped_offsite": 0, "dropped_filter": 0, "bodies_fetched": 0,
             "errors": 0}

    for entry in entries[:limit]:
        stats["seen"] += 1
        title = (getattr(entry, "title", "") or "").strip()
        summary = html_to_text(getattr(entry, "summary", "") or "")
        link = (getattr(entry, "link", "") or "").strip()

        # Provenance rule: the publisher's own URL or nothing.
        if not link or not is_publisher_url(link, feed["allowed_hosts"]):
            stats["dropped_offsite"] += 1
            continue

        # Department scoping by publisher URL path, for feeds pulled from a
        # multi-department upstream (DND has no working dept= code).
        path_filter = feed.get("link_path_contains")
        if path_filter and path_filter not in link:
            stats["dropped_filter"] += 1
            continue

        # Keyword filtering ON for every feed: scope terms (if any) AND the
        # shared keywords.txt relevance filter. No empty-filter passthrough.
        result = evaluate(title, summary, "", keywords)
        if not matches_scope(f"{title} {summary}", feed["scope_terms"]) or not result.kept:
            stats["dropped_filter"] += 1
            continue
        stats["kept"] += 1

        chash = content_hash(link, "news_release")
        if supabase_client.get_document_by_hash(chash):
            stats["skipped_duplicate"] += 1
            continue

        try:
            body = summary
            if looks_truncated(summary):
                resp = fetcher.get(link)
                if resp is not None:
                    body = html_to_text(resp.text)
                    stats["bodies_fetched"] += 1

            payload = {
                "source_id": source_id,
                "url": link,
                "title": title[:500] or None,
                "doc_type": "news_release",
                "status": "captured",
                "published_on": entry_date(entry),
                "content_hash": chash,
                "content": body[:MAX_STORED_CHARS] or None,
                "defence_relevant": result.defence_relevant,
            }
            if dry_run:
                log.info("[dry-run] would insert: %r (%s, %d chars body)",
                         title[:80], link, len(body))
            else:
                supabase_client.insert_document(payload)
            stats["inserted"] += 1
        except Exception:   # noqa: BLE001 - one bad entry must not kill the feed
            log.exception("Error collecting %s", link)
            stats["errors"] += 1

    return stats


def _parse_feed(url: str):
    import feedparser  # lazy so the module imports without the dependency

    return feedparser.parse(url)


def run(limit: int = MAX_ENTRIES_PER_FEED, dry_run: bool = False) -> int:
    keywords = load_keywords()
    fetcher = PoliteFetcher()
    now = datetime.now(timezone.utc)
    sources = supabase_client.fetch_rows("sources", "id,name")
    successes = 0
    failures = []

    for feed in FEEDS:
        if not feed.get("enabled", True):
            log.info("Feed %s is PARKED (%s); skipping",
                     feed["name"], feed.get("parked_reason", "no reason recorded"))
            continue
        source_id = resolve_source_id(feed, sources)
        if not source_id:
            log.error(
                "No sources row found for %s (tried names: %s). Run the sources "
                "seed migration or set %s.",
                feed["name"], feed["source_name_candidates"], feed["source_id_env"],
            )
            failures.append(feed["name"])
            continue
        try:
            parsed = _parse_feed(feed["feed_url"])
            if parsed.bozo and not parsed.entries:
                raise RuntimeError(f"feed parse error: {parsed.bozo_exception}")
            stats = collect_feed(feed, parsed.entries, source_id, keywords,
                                 fetcher, limit, dry_run)
            log.info("Feed %s: %s%s", feed["name"], stats, " (DRY RUN)" if dry_run else "")
            if stats["errors"]:
                failures.append(feed["name"])
            else:
                successes += 1
                if not dry_run:
                    supabase_client.update_source_last_collected(source_id, now)
        except Exception:
            log.exception("Feed collection failed for %s", feed["name"])
            failures.append(feed["name"])

    # Failure policy: one rotten feed must not fail the run (and page the
    # dead-man's switch) while the others collected fine — feed rot is
    # publisher churn, not a broken pipeline, and it stays loud in this log.
    # But if EVERY enabled feed failed, that's systemic (bad URLs, network,
    # auth) and SHOULD page.
    if failures and successes == 0:
        log.error("ALL enabled feeds failed (%s) — systemic; failing the run",
                  ", ".join(failures))
        return 1
    if failures:
        log.warning("Continuing despite failed feeds (%d ok): %s",
                    successes, ", ".join(failures))
    log.info("Newsroom RSS run finished (%d feeds ok, %d failed)",
             successes, len(failures))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Government newsroom RSS collector")
    parser.add_argument("--limit", type=int, default=MAX_ENTRIES_PER_FEED,
                        help=f"max entries per feed per run (default {MAX_ENTRIES_PER_FEED})")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and filter but write nothing (verify feed configs)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(limit=args.limit, dry_run=args.dry_run))
