"""Infrastructure Ontario newsroom collector (publisher-official award and
project announcements).

docs/merx-windsor-design.md section 9 (approved 2026-07-21). IO's own site
publishes "Contract Awarded for ..." announcements across provincial
infrastructure projects (subway extensions, hospital redevelopments, the
OnSat satellite program), plus occasional tender-stage ("Request for
Proposals Closes for ...") and milestone items. This is the proxy-coverage
leg for the PARKED IO MERX buyer page (section 8): awards become visible via
the newsroom; the tender feed stays parked pending provenance. IO's
proxy-coverage line: "awards via newsroom live, tender feed parked pending
provenance."

Requests-based on the shared board-minutes PoliteFetcher (robots per host,
2s delay, one UA). Discovery is PUBLISHER-INDEXED: IO's own /en/sitemap.xml
filtered to /news-and-media/news/ article URLs (CI probe 2026-07-21 job
88649903849: 1618 locs, 227 procurement-flavoured, all sampled pages 200).
A per-run NEW-item cap drains the multi-year archive over successive days,
board-minutes style; already-collected articles are skipped WITHOUT a fetch
(the content_hash is computable from the URL).

Mapping to the spine (no schema change): doc_type news_release, status
captured. An announcement whose prose names a contract award extracts as a
grade-5 contract_award signal by the SAME mechanism that lifts board
resolutions out of board_minutes documents (taxonomy contract_award = 5;
grade() takes max(signal_type grade, doc_type floor)), and news_release is
already in the daily forward extraction path, so no extractor change is
needed. published_on is the page's own publication date at day precision
(none beats a wrong date). The client organization varies per announcement
(CAMH, Metrolinx, hospitals), so buyer attribution is left to extraction to
resolve from the prose; IO itself is seeded in ORG_SEED so the agency
resolves when named.

LOUD FAILURE: an empty sitemap (zero article URLs) raises rather than
recording silence; a live publisher newsroom always has years of history.

    python -m src.io_newsroom --dry-run   # fetch + parse, write nothing
    python -m src.io_newsroom             # collect for real
"""
import argparse
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from . import supabase_client
from .board_minutes import PoliteFetcher, html_to_text
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

SITEMAP_URLS = ["https://www.infrastructureontario.ca/en/sitemap.xml"]
NEWS_SEGMENT = "/news-and-media/news/"
# The sources-row key (URL-guarded migration): the newsroom section itself.
SOURCE_URL = "https://www.infrastructureontario.ca/en/news-and-media/news/"
MAX_NEW_PER_RUN = 25           # per run; the archive drains over days
MAX_STORED_CHARS = 400_000
ERROR_BUDGET = 25              # per-article failures tolerated before loud abort
MAX_SUBSITEMAPS = 15           # cap sitemap-index expansion

LOC_RE = re.compile(r"<loc>\s*([^<]+?)\s*</loc>", re.IGNORECASE)

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}

# Publication date from the page's own machine-readable markup, tried in this
# order. Every modern CMS emits at least one of these; the visible-text form is
# the last resort. Day precision throughout (never a fabricated time).
_META_DATE = re.compile(
    r"""<meta[^>]+?(?:property|name)\s*=\s*["'](?:article:published_time|"""
    r"""article:published|og:updated_time|datePublished|dcterms\.date|"""
    r"""dc\.date(?:\.issued)?)["'][^>]+?content\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE)
_META_DATE_REV = re.compile(
    r"""<meta[^>]+?content\s*=\s*["']([^"']+)["'][^>]+?(?:property|name)\s*=\s*"""
    r"""["'](?:article:published_time|og:updated_time|datePublished)["']""",
    re.IGNORECASE)
_JSONLD_DATE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"', re.IGNORECASE)
_TIME_TAG = re.compile(r"""<time[^>]+?datetime\s*=\s*["']([^"']+)["']""",
                       re.IGNORECASE)
_ISO_IN = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_TEXT_DATE = re.compile(r"\b([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})")

_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

AWARD_TITLE_RE = re.compile(r"award", re.IGNORECASE)


def is_news_article(url: str) -> bool:
    """True for a news ARTICLE URL (project/article under the news section),
    not the section index or a project landing page. The sampled award URLs
    all carry at least a project segment plus an article slug."""
    path = urlparse(url).path
    if NEWS_SEGMENT not in path:
        return False
    after = path.split(NEWS_SEGMENT, 1)[1].strip("/")
    return after.count("/") >= 1 and bool(after)


def _valid_iso(y: int, mo: int, d: int) -> Optional[str]:
    if 1 <= mo <= 12 and 1 <= d <= 31:
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def extract_date(html: str) -> Optional[str]:
    """Publication date (YYYY-MM-DD) from the page's own markup, or None.
    Machine-readable markup first (meta/JSON-LD/<time>), visible text last."""
    for pat in (_META_DATE, _META_DATE_REV, _JSONLD_DATE, _TIME_TAG):
        for raw in pat.findall(html or ""):
            m = _ISO_IN.search(raw)
            if m:
                iso = _valid_iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if iso:
                    return iso
    m = _TEXT_DATE.search(html or "")
    if m:
        mo = MONTHS.get(m.group(1).lower())
        if mo:
            return _valid_iso(int(m.group(3)), mo, int(m.group(2)))
    return None


def extract_title(html: str) -> str:
    """The article heading: the first <h1>, falling back to <title> with any
    trailing site-name suffix trimmed."""
    m = _H1_RE.search(html or "")
    if m:
        text = " ".join(_TAG_RE.sub(" ", m.group(1)).split())
        if text:
            return text
    m = _TITLE_RE.search(html or "")
    if m:
        text = " ".join(_TAG_RE.sub(" ", m.group(1)).split())
        # Trim a "... | Infrastructure Ontario" style suffix.
        return re.split(r"\s[|–\-]\s", text, maxsplit=1)[0].strip()
    return ""


def build_payload(url: str, html: str, source_id: Optional[str],
                  keywords: Keywords) -> dict:
    title = extract_title(html) or urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    body = html_to_text(html).replace("\x00", "")
    published_on = extract_date(html)
    # Keep-all with defence tagging: IO infrastructure announcements are
    # in-scope by construction (provincial capital demand); the keyword
    # filter only sets defence_relevant, it never drops.
    result = evaluate(title, body[:20000], "", keywords)
    return {
        "source_id": source_id,
        "url": url,
        "title": title[:500] or None,
        "doc_type": "news_release",
        "status": "captured",
        "published_on": published_on,
        "date_precision": "day" if published_on else None,
        "content_hash": content_hash(url, "news_release"),
        "content": body[:MAX_STORED_CHARS] or None,
        "defence_relevant": result.defence_relevant,
        # buyer_name deliberately unset: the client varies per announcement
        # and extraction resolves it from the prose.
    }


def discover_article_urls(fetcher: PoliteFetcher) -> list:
    """All news-article URLs from IO's own sitemap (handling a sitemap index
    one level deep). Order is the sitemap's; the per-run cap drains it over
    days regardless of order."""
    seen: set[str] = set()
    articles: list[str] = []
    queue = list(SITEMAP_URLS)
    fetched_maps = 0
    while queue and fetched_maps < MAX_SUBSITEMAPS:
        sm = queue.pop(0)
        resp = fetcher.get(sm)
        if resp is None:
            log.warning("sitemap %s unreachable/robots-disallowed", sm)
            continue
        fetched_maps += 1
        for loc in LOC_RE.findall(resp.text):
            if loc.lower().endswith(".xml"):
                if loc not in queue and fetched_maps < MAX_SUBSITEMAPS:
                    queue.append(loc)
            elif is_news_article(loc) and loc not in seen:
                seen.add(loc)
                articles.append(loc)
    return articles


def collect(dry_run: bool = True, limit: int = MAX_NEW_PER_RUN) -> dict:
    keywords = load_keywords()
    fetcher = PoliteFetcher()
    sources = supabase_client.fetch_rows("sources", "id,url")
    source_id = next((s["id"] for s in sources
                      if (s.get("url") or "").rstrip("/") == SOURCE_URL.rstrip("/")), None)
    if not source_id and not dry_run:
        raise RuntimeError(
            f"no sources row for {SOURCE_URL}; apply the IO newsroom sources seed first")

    articles = discover_article_urls(fetcher)
    if not articles:
        raise RuntimeError(
            "IO newsroom sitemap yielded 0 article URLs: sitemap moved or "
            "markup changed. Refusing to record silence.")
    log.info("[io-newsroom] %d article URLs in sitemap", len(articles))

    stats = {"articles": len(articles), "new": 0, "inserted": 0,
             "skipped_duplicate": 0, "errors": 0}
    val = {"items": 0, "dated": 0, "award_titled": 0, "nonzero_body": 0}

    for url in articles:
        if stats["new"] >= limit:
            log.info("[io-newsroom] per-run cap (%d) reached; %d URLs remain for "
                     "future runs", limit, len(articles) - stats["articles"])
            break
        # URL-keyed hash: known articles skip without a fetch.
        if supabase_client.get_document_by_hash(content_hash(url, "news_release")):
            stats["skipped_duplicate"] += 1
            continue
        stats["new"] += 1
        try:
            resp = fetcher.get(url)
            if resp is None:
                continue
            payload = build_payload(url, resp.text, source_id, keywords)
            val["items"] += 1
            val["dated"] += 1 if payload["published_on"] else 0
            val["award_titled"] += 1 if AWARD_TITLE_RE.search(payload["title"] or "") else 0
            val["nonzero_body"] += 1 if payload["content"] else 0
            if dry_run:
                log.info("[dry-run] news_release pub=%s :: %s",
                         payload["published_on"], (payload["title"] or "")[:80])
            else:
                supabase_client.insert_document(payload)
            stats["inserted"] += 1
        except Exception:
            stats["errors"] += 1
            log.exception("[io-newsroom] article failed (%s); continuing", url)
            if stats["errors"] > ERROR_BUDGET:
                raise RuntimeError(
                    f"[io-newsroom] exceeded the error budget ({stats['errors']} "
                    f"article failures): systemic, not transient. Aborting.")

    # The enablement bar reads this line (docs/merx-windsor-design.md section
    # 9: >= 90% date parse on sampled items, nonzero award-titled items,
    # nonzero text bodies).
    n = val["items"] or 1
    log.info("VALIDATION [io-newsroom]: items=%d date_parsed=%d (%d%%) "
             "award_titled=%d nonzero_body=%d (%d%%)",
             val["items"], val["dated"], round(100 * val["dated"] / n),
             val["award_titled"], val["nonzero_body"],
             round(100 * val["nonzero_body"] / n))
    log.info("io-newsroom: %s%s", stats, " (DRY RUN)" if dry_run else "")
    if not dry_run and source_id and not stats["errors"]:
        supabase_client.update_source_last_collected(
            source_id, datetime.now(timezone.utc))
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Infrastructure Ontario newsroom collector")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and parse but write nothing")
    parser.add_argument("--limit", type=int, default=MAX_NEW_PER_RUN,
                        help=f"max NEW articles per run (default {MAX_NEW_PER_RUN})")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    collect(dry_run=args.dry_run, limit=args.limit)
    sys.exit(0)
