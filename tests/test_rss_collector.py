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


def _run_wiring(monkeypatch, parse_results):
    """Wire run() with fake feeds: parse_results maps feed name -> entries
    list or Exception."""
    monkeypatch.setattr(rc.supabase_client, "fetch_rows",
                        lambda t, s, limit=10000: [
                            {"id": "s-ps", "name": "Public Safety Canada — News"},
                            {"id": "s-dnd", "name": "Department of National Defence — News"},
                            {"id": "s-rcmp", "name": "RCMP — News"},
                            {"id": "s-on", "name": "Ontario Newsroom — Solicitor General"}])
    monkeypatch.setattr(rc.supabase_client, "get_document_by_hash", lambda h: None)
    monkeypatch.setattr(rc.supabase_client, "insert_document", lambda p: {"id": "d"})
    monkeypatch.setattr(rc.supabase_client, "update_source_last_collected",
                        lambda sid, when: None)
    monkeypatch.setattr(rc, "load_keywords", lambda: KEYWORDS)
    monkeypatch.setattr(rc, "PoliteFetcher", lambda: FakeFetcher())

    class Parsed:
        def __init__(self, entries):
            self.entries = entries
            self.bozo = 0
            self.bozo_exception = None

    def fake_parse(url):
        for name, result in parse_results.items():
            if name in url or any(name in f["feed_url"] for f in rc.FEEDS
                                  if f["name"] == name and f["feed_url"] == url):
                pass
        # match by configured feed_url
        for f in rc.FEEDS:
            if f["feed_url"] == url:
                result = parse_results[f["name"]]
                if isinstance(result, Exception):
                    raise result
                return Parsed(result)
        raise AssertionError(f"unexpected feed url {url}")

    monkeypatch.setattr(rc, "_parse_feed", fake_parse)


GOOD_ENTRY = [_entry("Body-worn camera expansion", LONG_BODY,
                     "https://www.canada.ca/en/news/1")]


def test_one_rotten_feed_does_not_fail_run(monkeypatch):
    _run_wiring(monkeypatch, {
        "Public Safety Canada — News": GOOD_ENTRY,
        "Department of National Defence — News": RuntimeError("parse error"),
        "RCMP — News": GOOD_ENTRY,
    })
    assert rc.run(limit=5, dry_run=True) == 0     # 2 ok, 1 failed -> continue


def test_all_feeds_failing_is_systemic_and_fails(monkeypatch):
    _run_wiring(monkeypatch, {
        "Public Safety Canada — News": RuntimeError("parse error"),
        "Department of National Defence — News": RuntimeError("parse error"),
        "RCMP — News": RuntimeError("parse error"),
    })
    assert rc.run(limit=5, dry_run=True) == 1     # systemic -> page


def test_parked_feed_is_skipped(monkeypatch):
    calls = []
    _run_wiring(monkeypatch, {
        "Public Safety Canada — News": GOOD_ENTRY,
        "Department of National Defence — News": GOOD_ENTRY,
        "RCMP — News": GOOD_ENTRY,
    })
    orig = rc._parse_feed
    monkeypatch.setattr(rc, "_parse_feed", lambda url: calls.append(url) or orig(url))
    rc.run(limit=5, dry_run=True)
    assert not any("ontario" in u for u in calls)  # parked feed never fetched


def test_link_path_filter_scopes_multi_department_feed(monkeypatch):
    """DND pulls the unfiltered GC feed; only its own URL-path entries land."""
    inserted = _wire(monkeypatch)
    feed = dict(FEED, link_path_contains="/department-national-defence/")
    entries = [
        _entry("Body-worn camera pilot for MPs", LONG_BODY,
               "https://news.example.gc.ca/en/housing-infrastructure/news/x"),
        _entry("Armoured vehicle project advances", LONG_BODY,
               "https://news.example.gc.ca/en/department-national-defence/news/y"),
    ]
    stats = rc.collect_feed(feed, entries, "src-1", KEYWORDS, FakeFetcher(),
                            limit=10, dry_run=False)
    assert stats["dropped_filter"] == 1
    assert [d["url"] for d in inserted] == [
        "https://news.example.gc.ca/en/department-national-defence/news/y"]
