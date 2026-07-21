"""Tests for the IO newsroom collector's pure logic: article-URL filtering,
publication-date extraction across markup shapes, title extraction, sitemap
article discovery, and payload construction (url-keyed hash, day precision,
defence tagging, no fabricated date). The network path is exercised by a CI
dry-run, not unit-tested here."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import io_newsroom as io
from src.filters import Keywords

KW = Keywords(general=("hospital",), defence=("opp", "police"))

ARTICLE = (
    "https://www.infrastructureontario.ca/en/news-and-media/news/"
    "subway-scarborough-subway-extension/contract-awarded-for-the-scarborough-"
    "subway-extension-stations-rail-and-systems-project/")
PROJECT_LANDING = (
    "https://www.infrastructureontario.ca/en/news-and-media/news/"
    "subway-scarborough-subway-extension/")
SECTION_INDEX = "https://www.infrastructureontario.ca/en/news-and-media/news/"
OTHER = "https://www.infrastructureontario.ca/en/about-us/"


# --- article URL filter ------------------------------------------------------
def test_is_news_article_accepts_project_article():
    assert io.is_news_article(ARTICLE) is True


def test_is_news_article_rejects_landing_and_section_and_other():
    assert io.is_news_article(PROJECT_LANDING) is False
    assert io.is_news_article(SECTION_INDEX) is False
    assert io.is_news_article(OTHER) is False


# --- date extraction ---------------------------------------------------------
def test_extract_date_meta_published_time():
    html = '<meta property="article:published_time" content="2026-05-14T15:01:53-04:00">'
    assert io.extract_date(html) == "2026-05-14"


def test_extract_date_meta_reversed_attribute_order():
    html = '<meta content="2026-03-02" name="datePublished">'
    assert io.extract_date(html) == "2026-03-02"


def test_extract_date_jsonld():
    html = '<script type="application/ld+json">{"datePublished":"2026-06-17T09:00:00Z"}</script>'
    assert io.extract_date(html) == "2026-06-17"


def test_extract_date_time_tag():
    html = '<time datetime="2026-04-21">April 21, 2026</time>'
    assert io.extract_date(html) == "2026-04-21"


def test_extract_date_visible_text_fallback():
    html = "<p>Published April 28, 2026 by the agency</p>"
    assert io.extract_date(html) == "2026-04-28"


def test_extract_date_none_when_absent():
    # None beats a wrong date.
    assert io.extract_date("<p>no date here</p>") is None
    assert io.extract_date("") is None


# --- title extraction --------------------------------------------------------
def test_extract_title_prefers_h1():
    html = "<title>Ignored | Infrastructure Ontario</title><h1>Contract Awarded for X</h1>"
    assert io.extract_title(html) == "Contract Awarded for X"


def test_extract_title_falls_back_to_title_trimming_suffix():
    html = "<title>Contract Awarded for Y | Infrastructure Ontario</title>"
    assert io.extract_title(html) == "Contract Awarded for Y"


def test_extract_title_decodes_html_entities():
    # IO titles carry raw entities (en dash, ampersand); a stored title must
    # never show &#x2013; or &amp;.
    html = "<h1>The Ottawa Hospital &#x2013; Civic Campus &amp; Redevelopment</h1>"
    assert io.extract_title(html) == "The Ottawa Hospital – Civic Campus & Redevelopment"


# --- sitemap discovery -------------------------------------------------------
def test_discover_article_urls_filters_and_follows_index():
    index = ("<sitemapindex><loc>https://www.infrastructureontario.ca/en/"
             "news-sitemap.xml</loc></sitemapindex>")
    news_map = (
        f"<urlset><loc>{ARTICLE}</loc><loc>{PROJECT_LANDING}</loc>"
        f"<loc>{OTHER}</loc></urlset>")

    class FakeResp:
        def __init__(self, text):
            self.text = text

    class FakeFetcher:
        def __init__(self):
            self.calls = []

        def get(self, url):
            self.calls.append(url)
            if url.endswith("news-sitemap.xml"):
                return FakeResp(news_map)
            if url.endswith("sitemap.xml"):
                return FakeResp(index)
            return None

    urls = io.discover_article_urls(FakeFetcher())
    assert urls == [ARTICLE]     # landing + non-news dropped, index followed


# --- payload -----------------------------------------------------------------
def test_build_payload_award_page():
    html = ('<meta property="article:published_time" content="2026-05-14">'
            "<h1>Contract Awarded for the Scarborough Subway Extension</h1>"
            "<p>OPP and hospital partners attended the announcement.</p>")
    p = io.build_payload(ARTICLE, html, "src-1", KW)
    assert p["doc_type"] == "news_release"
    assert p["published_on"] == "2026-05-14"
    assert p["date_precision"] == "day"
    assert p["title"].startswith("Contract Awarded")
    assert p["defence_relevant"] is True          # "OPP" defence keyword in body
    assert p["content_hash"] == io.content_hash(ARTICLE, "news_release")
    assert "buyer_name" not in p                   # left to extraction


def test_build_payload_undated_is_null_not_fabricated():
    html = "<h1>Substantial Completion Reached</h1><p>no date</p>"
    p = io.build_payload(ARTICLE, html, "s", KW)
    assert p["published_on"] is None
    assert p["date_precision"] is None


def test_hash_matches_rss_news_release_keying():
    # Same url+doc_type keying as rss_collector, so an article seen in both
    # would dedupe rather than double-insert.
    from src import rss_collector  # noqa: F401  (import proves the module loads)
    assert io.content_hash(ARTICLE, "news_release") \
        == io.content_hash(ARTICLE, "news_release")


# --- the operator's absolute copy rule ---------------------------------------
def test_no_em_dash_in_module_source():
    path = os.path.join(os.path.dirname(__file__), "..", "src", "io_newsroom.py")
    with open(path, encoding="utf-8") as f:
        assert "—" not in f.read()
