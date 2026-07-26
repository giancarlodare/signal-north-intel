"""Front 2 one-service precision proof (Peel Regional Police).

Fetches a sample of Peel Regional Police news releases + Peel Police Services
Board statements, runs a STRICT intent classifier (Claude, structured output),
and prints each item's label + confidence + evidence so precision and the
false-positive / false-negative sets can be adjudicated by hand. This is the
gate that decides whether the upstream intent extraction scales to all services
(docs/upstream-intent-layer-design.md section 4): it proves the extraction
separates genuine procurement/funding intent from press-release noise BEFORE
scaling.

Read-only against the sources (robots honored, 2s politeness); the only writes
are Claude API calls. Prints a table, stores nothing.

    python scripts/prove_intent_peel.py                    # news/statements only
    python scripts/prove_intent_peel.py --board-docs 12    # fold in corpus board
                                                           # budget/agenda docs
"""
import argparse
import json
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, ".")

from src import supabase_client
from src.board_minutes import PoliteFetcher, extract_links, html_to_text

LISTINGS = [
    ("PRP news releases", "https://www.peelpolice.ca/news-feed/news-releases/",
     "/news-feed/posts/"),
    ("PRP featured stories", "https://www.peelpolice.ca/news-feed/featured-stories/",
     "/news-feed/posts/"),
    ("PPSB news + updates", "https://www.peelpoliceboard.ca/news-and-updates/",
     "/news-and-updates/posts/"),
]

MODEL = os.environ.get("EXTRACTION_MODEL", "claude-opus-4-8")
MAX_BODY = 6000

_SYSTEM = (
    "You are a strict procurement-intelligence classifier for a police service's "
    "public communications. Your job is signal-vs-noise: most posts are noise "
    "(arrests, community events, hiring, awards ceremonies, safety tips, incident "
    "updates). A SMALL fraction genuinely telegraph future buying or funding a "
    "vendor could act on. Classify each into exactly one label:\n"
    "- procurement_intent: the service signals acquiring goods/services/"
    "technology/vehicles/facilities. This covers BOTH senses, and the realized "
    "sense is easy to miss so weight it explicitly:\n"
    "    * FUTURE intent: it will or is planning to acquire (a pilot, an upcoming "
    "RFP, a technology adoption, a fleet/capital/infrastructure plan).\n"
    "    * REALIZED acquisition: it INTRODUCES / DEPLOYS / LAUNCHES / ADOPTS / "
    "ROLLS OUT / IMPLEMENTS a tool, system, technology, platform, or service. A "
    "realized deployment is still procurement_intent (not noise): it confirms the "
    "buy in that category and implies follow-on, expansion, and maintenance buys "
    "a vendor can act on. Example: 'Police introduce an AI tool to support 911 "
    "operators' is procurement_intent (realized), NOT noise.\n"
    "- funding_intent: the service signals seeking or receiving funding, a grant, "
    "or a budget increase for a program that implies future buying.\n"
    "- pressure_signal: a demand-pressure indicator (a crime trend, a capacity "
    "strain, a rising incident category) that raises the likelihood of future "
    "buying but names no purchase.\n"
    "- noise: everything else, including arrests, charges, appeals for witnesses, "
    "community events, hiring, ceremonies, and general public relations.\n"
    "Be conservative: default to noise unless there is a CONCRETE procurement or "
    "funding signal in the text. Precision matters more than recall. Put the exact "
    "triggering phrase in 'evidence' (empty for noise)."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string",
                  "enum": ["procurement_intent", "funding_intent",
                           "pressure_signal", "noise"]},
        "confidence": {"type": "number"},
        "rationale": {"type": "string"},
        "evidence": {"type": "string"},
    },
    "required": ["label", "confidence", "rationale", "evidence"],
    # Anthropic structured outputs require additionalProperties:false on every
    # object (matches src/signal_extractor.py's schema); without it the API
    # rejects output_config with a 400.
    "additionalProperties": False,
}


def _post_urls(fetcher, listing_url, post_marker, cap):
    if not fetcher.allowed(listing_url):
        print(f"  robots DISALLOWED: {listing_url}")
        return []
    try:
        r = fetcher.get(listing_url)
    except Exception as e:
        print(f"  ERROR {listing_url}: {type(e).__name__}: {str(e)[:100]}")
        return []
    if r is None:
        return []
    seen, out = set(), []
    for u, _ in extract_links(r.text or "", listing_url):
        if post_marker in urlparse(u).path and u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= cap:
            break
    return out


def _fetch_post(fetcher, url):
    try:
        r = fetcher.get(url)
    except Exception:
        return None
    if r is None:
        return None
    text = html_to_text(r.text or "")
    # crude title = the slug, humanized (the body carries the real signal)
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    title = slug.replace("-", " ")
    return {"url": url, "title": title, "body": text[:MAX_BODY]}


def _classify(client, post):
    prompt = (f"POST TITLE: {post['title']}\n\nPOST BODY:\n{post['body']}\n\n"
              "Classify this post.")
    resp = client.messages.create(
        model=MODEL, max_tokens=512, system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)


def _corpus_board_docs(n):
    """Peel board budget/agenda docs already in the corpus (board_minutes
    collector output): the doc mix where real buys first surface. Newest
    first, nonzero content."""
    rows = supabase_client.fetch_rows_where(
        "documents", "id,title,url,content,published_on",
        {"doc_type": "eq.board_minutes", "url": "ilike.*peelpoliceboard*",
         "content": "not.is.null"},
        limit=n * 3)
    rows.sort(key=lambda r: str(r.get("published_on") or ""), reverse=True)
    out = []
    for r in rows:
        body = (r.get("content") or "").strip()
        if not body:
            continue
        out.append({"url": r.get("url") or "", "title": (r.get("title") or "")[:120],
                    "body": body[:MAX_BODY], "listing": "PPSB board docs (corpus)"})
        if len(out) >= n:
            break
    return out


def main(limit, board_docs):
    import anthropic
    fetcher = PoliteFetcher()
    per_listing = max(3, limit // len(LISTINGS) + 1)
    posts = []
    for label, listing, marker in LISTINGS:
        urls = _post_urls(fetcher, listing, marker, per_listing)
        print(f"[{label}] {len(urls)} post urls")
        for u in urls:
            p = _fetch_post(fetcher, u)
            if p and p["body"].strip():
                p["listing"] = label
                posts.append(p)
            if len(posts) >= limit:
                break
        if len(posts) >= limit:
            break
    if board_docs:
        docs = _corpus_board_docs(board_docs)
        print(f"[PPSB board docs (corpus)] {len(docs)} docs folded in")
        posts.extend(docs)

    print("=" * 74)
    print(f"CLASSIFYING {len(posts)} Peel posts (model={MODEL})")
    print("=" * 74)
    client = anthropic.Anthropic()
    counts = {}
    for i, p in enumerate(posts, 1):
        try:
            c = _classify(client, p)
        except Exception as e:
            print(f"[{i}] CLASSIFY ERROR: {type(e).__name__}: {str(e)[:300]}")
            continue
        counts[c["label"]] = counts.get(c["label"], 0) + 1
        print(f"[{i}] {c['label'].upper():18s} conf={c.get('confidence')} "
              f":: {p['title'][:70]}")
        if c["label"] != "noise":
            print(f"     evidence: {c.get('evidence','')[:180]}")
            print(f"     rationale: {c.get('rationale','')[:180]}")
        print(f"     url: {p['url']}")
    print("=" * 74)
    print(f"LABEL COUNTS: {counts}")
    print("Adjudicate: of the non-noise labels, which are true intent (precision), "
          "and scan the noise for missed intent (false negatives).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Peel intent-extraction precision proof")
    parser.add_argument("--limit", type=int, default=24, help="news/statement posts to classify")
    parser.add_argument("--board-docs", type=int, default=0,
                        help="also classify N Peel board budget/agenda docs from the corpus")
    args = parser.parse_args()
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main(args.limit, args.board_docs)
    sys.exit(0)
