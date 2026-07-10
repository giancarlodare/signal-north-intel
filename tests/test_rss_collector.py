import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import rss_collector as rc
from src.filters import Keywords

KEYWORDS = Keywords(general=("body-worn camera", "drone"), defence=("armoured",))

FEED = {
    "name": "Testroom",
    "feed_url": "https://news.example.gc.ca/feed.atom",
    "allowed_hosts": ["news.example.gc.ca"],
    "scope_terms": [],
    "source_name_candidates": ["Testroom"],
    "source_id_env": "TESTROOM_SOURCE_ID",
}

LONG_BODY = ("The ministry announced a body-worn camera expansion. " * 20).strip()


def _entry(title, summary, link, date=(2026, 7, 10, 12, 0, 0, 0, 0, 0)):
    return SimpleNamespace(title=title, summary=summary, link=link,
                           published_parsed=date)


class FakeFetcher:
    def __init__(self, pages=None):
        self.pages = pages or {}
        self.requested = []

    def get(self, url):
        self.requested.append(url)
        page = self.pages.get(url)
        return SimpleNamespace(text=page) if page is not None else None


def _wire(monkeypatch, existing_hashes=frozenset()):
    inserted = []
    monkeypatch.setattr(rc.supabase_client, "get_document_by_hash",
                        lambda h: {"id": "x"} if h in existing_hashes else None)
    monkeypatch.setattr(rc.supabase_client, "insert_document",
                        lambda p: inserted.append(p) or {"id": "new"})
    return inserted


def test_keyword_filter_is_on_for_every_feed(monkeypatch):
    """The Manus bug: empty filter_terms collected everything. Now an entry
    that matches no keywords is dropped even when scope_terms is empty."""
    inserted = _wire(monkeypatch)
    entries = [
        _entry("Minister visits cheese factory", LONG_BODY.replace("body-worn camera", "dairy"),
               "https://news.example.gc.ca/cheese"),
        _entry("Body-worn camera expansion announced", LONG_BODY,
               "https://news.example.gc.ca/bwc"),
    ]
    stats = rc.collect_feed(FEED, entries, "src-1", KEYWORDS, FakeFetcher(),
                            limit=10, dry_run=False)
    assert stats["dropped_filter"] == 1
    assert stats["inserted"] == 1
    assert inserted[0]["url"] == "https://news.example.gc.ca/bwc"


def test_offsite_links_are_dropped(monkeypatch):
    """Provenance rule: publisher URLs only — aggregator/redirect hosts never land."""
    inserted = _wire(monkeypatch)
    entries = [
        _entry("Drone program", LONG_BODY, "https://news.google.com/articles/abc123"),
        _entry("Drone program", LONG_BODY, ""),
        _entry("Drone program", LONG_BODY, "https://news.example.gc.ca/drone"),
    ]
    stats = rc.collect_feed(FEED, entries, "src-1", KEYWORDS, FakeFetcher(),
                            limit=10, dry_run=False)
    assert stats["dropped_offsite"] == 2
    assert [d["url"] for d in inserted] == ["https://news.example.gc.ca/drone"]


def test_scope_terms_apply_on_top_of_keywords(monkeypatch):
    inserted = _wire(monkeypatch)
    feed = dict(FEED, scope_terms=["police"])
    entries = [
        _entry("Drone hobby fair", LONG_BODY.replace("ministry", "hobby club"),
               "https://news.example.gc.ca/fair"),                     # keyword yes, scope no
        _entry("Police drone unit", "Police drone unit expands. " + LONG_BODY,
               "https://news.example.gc.ca/police-drone"),             # both
    ]
    stats = rc.collect_feed(feed, entries, "src-1", KEYWORDS, FakeFetcher(),
                            limit=10, dry_run=False)
    assert stats["dropped_filter"] == 1 and stats["inserted"] == 1
    assert inserted[0]["url"].endswith("police-drone")


def test_truncated_summary_triggers_full_body_fetch(monkeypatch):
    inserted = _wire(monkeypatch)
    url = "https://news.example.gc.ca/trunc"
    fetcher = FakeFetcher(pages={
        url: "<html><body><p>Full release: the body-worn camera "
             "program will roll out to all frontline officers.</p></body></html>"
    })
    entries = [_entry("Body-worn camera rollout", "Body-worn camera…", url)]
    stats = rc.collect_feed(FEED, entries, "src-1", KEYWORDS, fetcher,
                            limit=10, dry_run=False)
    assert stats["bodies_fetched"] == 1
    assert fetcher.requested == [url]
    assert "frontline officers" in inserted[0]["content"]


def test_long_summary_skips_body_fetch(monkeypatch):
    inserted = _wire(monkeypatch)
    fetcher = FakeFetcher()
    entries = [_entry("Body-worn camera rollout", LONG_BODY,
                      "https://news.example.gc.ca/full")]
    rc.collect_feed(FEED, entries, "src-1", KEYWORDS, fetcher, limit=10, dry_run=False)
    assert fetcher.requested == []                      # no fetch needed
    assert inserted[0]["content"].startswith("The ministry announced")


def test_dedupe_and_dry_run(monkeypatch):
    from src.hashing import content_hash
    url = "https://news.example.gc.ca/bwc"
    inserted = _wire(monkeypatch, existing_hashes={content_hash(url, "news_release")})
    entries = [_entry("Body-worn camera expansion", LONG_BODY, url)]
    stats = rc.collect_feed(FEED, entries, "src-1", KEYWORDS, FakeFetcher(),
                            limit=10, dry_run=False)
    assert stats["skipped_duplicate"] == 1 and inserted == []

    inserted2 = _wire(monkeypatch)
    entries2 = [_entry("Body-worn camera expansion", LONG_BODY,
                       "https://news.example.gc.ca/new")]
    stats2 = rc.collect_feed(FEED, entries2, "src-1", KEYWORDS, FakeFetcher(),
                             limit=10, dry_run=True)
    assert stats2["inserted"] == 1 and inserted2 == []  # dry run writes nothing


def test_looks_truncated():
    assert rc.looks_truncated("Short teaser…")
    assert rc.looks_truncated("Short.")
    assert rc.looks_truncated(LONG_BODY + " [...]")
    assert not rc.looks_truncated(LONG_BODY)


def test_resolve_source_id(monkeypatch):
    assert rc.resolve_source_id(FEED, [{"id": "s1", "name": " testroom "}]) == "s1"
    monkeypatch.setenv("TESTROOM_SOURCE_ID", "env-id")
    assert rc.resolve_source_id(FEED, []) == "env-id"
