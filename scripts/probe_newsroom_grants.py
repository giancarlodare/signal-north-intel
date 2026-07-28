"""Newsroom grant-announcement probe (operator 2026-07-28, folded into the
grants-near-zero investigation): the newsroom is where grants get ANNOUNCED,
so a parked newsroom is both a coverage gap and the missing cross-check on
thin grant flow.

Read-only, three parts:
  1. ONTARIO: hunt the structured endpoint behind the news.ontario.ca JS
     shell before any render machinery earns its keep: robots, the shell
     itself, its JS bundles greppd for api URLs, and the known candidate
     API shapes. If a JSON endpoint exists, the collector is a requests
     build, no rendering needed.
  2. FEDERAL FEEDS WE COLLECT: query the same GC news API the collectors
     use and count how many of the last 50 items per department are
     funding/grant announcements, with samples, so we know whether grant
     news actually flows through the channel we already read.
  3. CORPUS CROSS-CHECK: how many collected news_release docs carry
     funding/grant language, so parts 1-2 can be compared against what
     actually landed.

CI only (sandbox blocks external hosts).
"""
import json
import os
import re
import sys
import time
import urllib.robotparser

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import supabase_client

UA = "SignalNorthIntel/1.0"
FUND = re.compile(r"\b(fund|funding|grant|grants|invest|investment|contribution)\w*",
                  re.IGNORECASE)


def get(url, **kw):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30, **kw)
    print(f"\n=== {url}\n    status={r.status_code} "
          f"type={r.headers.get('content-type', '?')[:40]} bytes={len(r.content)}")
    return r


def part1_ontario():
    print("\n" + "=" * 70 + "\nPART 1: Ontario Newsroom structured-endpoint hunt\n" + "=" * 70)
    rp = urllib.robotparser.RobotFileParser()
    r = get("https://news.ontario.ca/robots.txt")
    rp.parse(r.text.splitlines())
    ok = rp.can_fetch(UA, "https://news.ontario.ca/en/")
    print(f"    robots allows /en/: {ok}")
    if not ok:
        print("    STOP: robots disallows; park stands.")
        return

    time.sleep(2)
    shell = get("https://news.ontario.ca/en/").text
    api_urls = sorted(set(re.findall(
        r'https?://[^"\'\s]*(?:api|json)[^"\'\s]*', shell)))[:10]
    print("    api-ish URLs in shell:", api_urls or "none")
    bundles = re.findall(r'src="(/[^"]+\.js[^"]*)"', shell)[:4]
    for b in bundles:
        time.sleep(2)
        js = get(f"https://news.ontario.ca{b}").text
        hits = sorted(set(re.findall(
            r'["\'](/api/[^"\']{3,60}|https?://[^"\']*api[^"\']{0,60})["\']', js)))[:12]
        print(f"    endpoints in bundle {b[:44]}:", hits or "none")

    for cand in ("https://news.ontario.ca/api/v1/releases?language=en&pageSize=5",
                 "https://news.ontario.ca/newsroom/api/releases?language=en",
                 "https://api.news.ontario.ca/api/v1/releases?language=en"):
        time.sleep(2)
        try:
            r = get(cand)
            if "json" in (r.headers.get("content-type") or ""):
                body = r.text[:400].replace("\n", " ")
                print(f"    JSON! first 400 chars: {body}")
        except requests.RequestException as e:
            print(f"    failed ({type(e).__name__})")


def part2_federal():
    print("\n" + "=" * 70 + "\nPART 2: GC news API, funding density per collected dept\n" + "=" * 70)
    api = ("https://api.io.canada.ca/io-server/gc/news/en/v2"
           "?dept={dept}&sort=publishedDate&orderBy=desc&pick=50&format=json")
    for dept in ("publicsafetycanada", "departmentofnationaldefence",
                 "royalcanadianmountedpolice"):
        time.sleep(2)
        try:
            r = get(api.format(dept=dept))
            items = r.json().get("feed", {}).get("entry", [])
        except (requests.RequestException, ValueError):
            print("    fetch/parse failed")
            continue
        funders = [i for i in items
                   if FUND.search(str(i.get("title", "")) + str(i.get("teaser", "")))]
        print(f"    {dept}: {len(items)} recent items, "
              f"{len(funders)} funding/grant-flavoured")
        for i in funders[:5]:
            print(f"      - {str(i.get('title', ''))[:80]}")


def part3_corpus():
    print("\n" + "=" * 70 + "\nPART 3: corpus cross-check, news_release funding language\n" + "=" * 70)
    docs = supabase_client.fetch_all_rows_where(
        "documents", "id,title,published_on,created_at",
        {"doc_type": "eq.news_release"})
    funders = [d for d in docs if FUND.search(d.get("title") or "")]
    print(f"    news_release docs in corpus: {len(docs)}; "
          f"funding/grant-flavoured titles: {len(funders)}")
    for d in sorted(funders, key=lambda d: str(d.get("published_on")),
                    reverse=True)[:10]:
        print(f"      - {str(d.get('published_on'))[:10]}  {(d.get('title') or '')[:76]}")


def main() -> int:
    part1_ontario()
    part2_federal()
    part3_corpus()
    return 0


if __name__ == "__main__":
    sys.exit(main())
