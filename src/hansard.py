"""Ontario Hansard + committee documents collector (docs/hansard-design.md,
design merged in #104; upstream-intent legislative layer).

Legislative debate and committee estimates are upstream INTENT signal: a
minister's statement, an estimates exchange, or a committee recommendation
often precedes the budget line and the tender by months. The target is narrow
and high-value (Solicitor General / community-safety and infrastructure /
capital statements), not the whole Hansard firehose.

Probe evidence (CI job 89676754793): ola.org is server-side HTML, plainly
requests-collectable. The per-session house-documents index lists per-DAY
debate pages by date (URL carries YYYY-MM-DD); the committee-documents index
lists committee documents (estimates, reports).

SCOPE FILTER, NOT KEEP-ALL (the Hansard exception, like the RSS scope terms):
a full day's Hansard is mostly off-topic debate. A document is stored only if
its text matches the SolGen/community-safety or infrastructure/capital scope
terms; keywords.txt then tags defence_relevant on top. This is what keeps the
corpus and the Opus extraction budget focused (the design's cost note): only
scope-matching sitting days are stored and extracted.

Politeness is the board-minutes pattern (shared PoliteFetcher). Per-run
NEW-item cap drains the session archive over days; content_hash(url,
doc_type) is checked BEFORE fetching a transcript, so known days cost one
index fetch total.

LOUD FAILURE: the session index yielding zero dated debate URLs raises (the
Assembly always has a current session).

    python -m src.hansard --dry-run   # fetch + parse + filter, write nothing
    python -m src.hansard             # collect for real
"""
import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from . import supabase_client
from .board_minutes import PoliteFetcher, extract_links, html_to_text
from .filters import Keywords, evaluate, load_keywords
from .hashing import content_hash

log = logging.getLogger(__name__)

BASE = "https://www.ola.org"
# Current parliament/session, overridable without a code change when a new
# session opens (HANSARD_PARLIAMENT=44 HANSARD_SESSION=1).
PARLIAMENT = os.environ.get("HANSARD_PARLIAMENT", "43")
SESSION = os.environ.get("HANSARD_SESSION", "1")
SESSION_INDEX = (f"{BASE}/en/legislative-business/house-documents/"
                 f"parliament-{PARLIAMENT}/session-{SESSION}/")
COMMITTEE_INDEX = f"{BASE}/en/legislative-business/committees/documents"
SOURCE_URL = "https://www.ola.org/en/legislative-business/house-documents"
DOC_TYPE = "legislative_debate"

MAX_STORED_CHARS = 60000   # sitting days are long; the scope filter has already
                           # earned the storage, and the extractor reads content
NEW_PER_RUN = 25           # board-minutes style archive drain
ERROR_BUDGET = 10          # per-item failures tolerated before loud abort

# The dated per-day transcript URL as ola.org actually links it (CI diagnostic
# 2026-07-26, job 89795333961): .../parliament-43/session-1/2024-12-11/hansard
# The bare dated directory also exists; both shapes match.
DATED_URL = re.compile(
    rf"/parliament-{PARLIAMENT}/session-{SESSION}/"
    rf"(\d{{4}})-(\d{{2}})-(\d{{2}})(?:/hansard)?/?$")

# Scope terms (docs/hansard-design.md): SolGen / community-safety +
# infrastructure / capital. A transcript is stored only if it matches one.
SCOPE_TERMS = [
    # public safety arc
    "solicitor general", "community safety", "public safety", "police",
    "policing", "opp", "correctional", "corrections", "emergency services",
    "911", "victim services", "firearms", "auto theft", "bail",
    # infrastructure / capital arc
    "infrastructure", "capital plan", "capital budget", "procurement",
    "capital investment", "infrastructure ontario",
]


def matches_scope(text: str) -> list:
    low = (text or "").lower()
    return [t for t in SCOPE_TERMS if t in low]


CHUNK_CHARS = 1200   # section granularity when the text carries no newlines


def _split_sections(body: str) -> list:
    """Paragraphs when the text has newline structure; otherwise fixed-size
    chunks split at sentence boundaries. html_to_text flattens ola.org pages
    to nearly newline-free text (CI diagnostic 2026-07-26: sections_kept=22/22
    because each transcript arrived as ONE paragraph), so newline splitting
    alone cannot compress; the chunk fallback restores real granularity."""
    paras = [p.strip() for p in (body or "").split("\n") if p.strip()]
    if len(paras) > 3:
        return paras
    text = " ".join(paras)
    out, start = [], 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        if end < len(text):
            dot = text.rfind(". ", start + CHUNK_CHARS // 2, end)
            if dot != -1:
                end = dot + 1
        out.append(text[start:end].strip())
        start = end
    return [c for c in out if c]


def scope_sections(body: str, context: int = 1) -> tuple:
    """SECTION-LEVEL filter (operator 2026-07-26): a full sitting day almost
    always mentions 'police' somewhere, so document-level scope keeps ~every
    day and blows the extraction budget. Split into sections (paragraphs, or
    sentence-boundary chunks when the text is newline-free) and keep only the
    scope-matching ones plus `context` neighbors on each side (contiguous
    runs merged). Returns (kept_text, hits, kept_paras, total_paras): the
    stored document is the policing/capital passages, not 200 pages of
    unrelated debate."""
    paras = _split_sections(body)
    keep = set()
    hits: list = []
    for i, p in enumerate(paras):
        h = matches_scope(p)
        if h:
            hits.extend(x for x in h if x not in hits)
            for j in range(max(0, i - context), min(len(paras), i + context + 1)):
                keep.add(j)
    if not keep:
        return "", [], 0, len(paras)
    out, prev = [], None
    for i in sorted(keep):
        if prev is not None and i > prev + 1:
            out.append("[...]")
        out.append(paras[i])
        prev = i
    return "\n".join(out), hits, len(keep), len(paras)


def dated_debate_urls(html: str, base_url: str) -> list:
    """(iso_date, absolute_url) pairs from the session index, newest first."""
    out, seen = [], set()
    for url, _text in extract_links(html, base_url):
        m = DATED_URL.search(urlparse(url).path)
        if not m:
            continue
        iso = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        if url in seen:
            continue
        seen.add(url)
        out.append((iso, url))
    out.sort(reverse=True)
    return out


def _committee_links(html: str, base_url: str, cap: int = 40) -> list:
    """ola.org committee links on a page: (text, url), /documents index and
    off-site excluded."""
    out, seen = [], set()
    for url, text in extract_links(html, base_url):
        path = urlparse(url).path
        if "/committees/" not in path or path.rstrip("/").endswith("/documents"):
            continue
        if urlparse(url).netloc and "ola.org" not in urlparse(url).netloc:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append((" ".join((text or "").split())[:120], url))
        if len(out) >= cap:
            break
    return out


def committee_doc_urls(fetcher: PoliteFetcher, cap: int = 40) -> list:
    """(title, url) committee DOCUMENT links. The committee-documents index
    links parliament-level index pages, not documents (CI diagnostic
    2026-07-26), so this follows one extra hop: index -> parliament pages ->
    the actual estimates/report documents. Committee docs carry no URL date;
    the page date is parsed after fetch (NULL when genuinely absent)."""
    resp = fetcher.get(COMMITTEE_INDEX)
    if resp is None:
        return []
    first = _committee_links(resp.text or "", COMMITTEE_INDEX)
    parl = [(t, u) for t, u in first if "parliament" in f"{t} {u}".lower()]
    docs = [(t, u) for t, u in first if (t, u) not in parl]
    for _t, purl in parl[:2]:     # current + previous parliament
        presp = fetcher.get(purl)
        if presp is None:
            continue
        for t, u in _committee_links(presp.text or "", purl):
            if "parliament" in f"{t} {u}".lower():
                continue
            docs.append((t, u))
            if len(docs) >= cap:
                return docs
    return docs[:cap]


# The page's own date line, e.g. "Thursday 12 December 2024" or ISO in meta.
PAGE_DATE = re.compile(
    r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+(\d{4})\b")
_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], 1)}


def page_date(text: str) -> Optional[str]:
    m = PAGE_DATE.search(text or "")
    if not m:
        return None
    d, mon, y = int(m.group(1)), _MONTHS[m.group(2)], int(m.group(3))
    if not (1 <= d <= 31):
        return None
    return f"{y:04d}-{mon:02d}-{d:02d}"


def build_payload(url: str, title: str, body: str, published_on: Optional[str],
                  source_id: Optional[str], keywords: Keywords,
                  scope_hits: list) -> dict:
    result = evaluate(title, body[:MAX_STORED_CHARS], "", keywords)
    return {
        "source_id": source_id,
        "url": url,
        "title": title[:500],
        "doc_type": DOC_TYPE,
        "status": "captured",
        "published_on": published_on,
        # documents.date_precision is NOT NULL (day|month); published_on=None
        # carries the null-date signal (never fabricate), per the #103 fix.
        "date_precision": "day",
        "reference_number": None,
        "content_hash": content_hash(url, DOC_TYPE),
        # Scope hits lead the body so the extractor and a reviewer see WHY this
        # sitting day was kept.
        "content": (f"[scope: {', '.join(scope_hits)}]\n" + body)[:MAX_STORED_CHARS] or None,
        "defence_relevant": result.defence_relevant,
        "buyer_name": None,   # ministry resolved from the prose at extraction
    }


def collect(dry_run: bool = True) -> dict:
    keywords = load_keywords()
    fetcher = PoliteFetcher()
    sources = supabase_client.fetch_rows("sources", "id,url")
    source_id = next((s["id"] for s in sources
                      if (s.get("url") or "").rstrip("/") == SOURCE_URL.rstrip("/")), None)
    if not source_id and not dry_run:
        raise RuntimeError(
            f"no sources row for {SOURCE_URL}; apply the Hansard migration first")

    stats = {"index_days": 0, "committee_links": 0, "new_fetched": 0,
             "inserted": 0, "skipped_duplicate": 0, "skipped_scope": 0,
             "errors": 0}
    val = {"date_parsed": 0, "nonzero_body": 0, "scope_kept": 0}

    resp = fetcher.get(SESSION_INDEX)
    if resp is None:
        raise RuntimeError(f"robots.txt would not allow {SESSION_INDEX}; "
                           f"refusing to record silence")
    days = dated_debate_urls(resp.text or "", SESSION_INDEX)
    stats["index_days"] = len(days)
    # LOUD FAILURE: the Assembly always has a current session with sittings.
    # Before raising, log a sample of what the index DID link so the failure
    # is diagnosable from the run log alone.
    if not days:
        links = [u for u, _ in extract_links(resp.text or "", SESSION_INDEX)]
        datish = [u for u in links if re.search(r"\d{4}-\d{2}-\d{2}", u)][:15]
        sessish = [u for u in links if "/session-" in u][:15]
        log.error("[hansard] index bytes=%d total_links=%d date-shaped=%d "
                  "session-shaped=%d; samples:",
                  len(resp.text or ""), len(links), len(datish), len(sessish))
        for u in datish or sessish or links[:15]:
            log.error("  %s", u)
        raise RuntimeError(
            f"[hansard] session index {SESSION_INDEX} yielded 0 dated debate "
            f"URLs: parliament/session config stale or markup changed. "
            f"Refusing to record silence.")

    committee = committee_doc_urls(fetcher)
    stats["committee_links"] = len(committee)

    # Queue: committee docs FIRST (estimates are the highest-value target,
    # docs/hansard-design.md), then daily debates newest-first.
    queue = [("committee", t or "(committee document)", u) for t, u in committee]
    queue += [("debate", f"Ontario Hansard, {iso} sitting", u) for iso, u in days]

    for kind, title, url in queue:
        if stats["new_fetched"] >= NEW_PER_RUN:
            break
        try:
            chash = content_hash(url, DOC_TYPE)
            if supabase_client.get_document_by_hash(chash):
                stats["skipped_duplicate"] += 1
                continue
            resp = fetcher.get(url)
            if resp is None:
                continue
            stats["new_fetched"] += 1
            body_full = html_to_text(resp.text or "")
            # SECTION-LEVEL SCOPE FILTER: keep only the scope-matching
            # passages (+1 paragraph of context each side). A day with no
            # matching passage is dropped entirely; a matching day stores the
            # policing/capital sections, not the whole transcript. This is
            # the cost control AND the extraction sharpener.
            body, hits, kept_paras, total_paras = scope_sections(body_full)
            if not hits:
                stats["skipped_scope"] += 1
                continue
            val["scope_kept"] += 1
            val["paras_kept"] = val.get("paras_kept", 0) + kept_paras
            val["paras_total"] = val.get("paras_total", 0) + total_paras
            m = DATED_URL.search(urlparse(url).path)
            # Date from the FULL body: the sitting-date line may sit outside
            # the scope-kept sections.
            published = (f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m
                         else page_date(body_full))
            if published:
                val["date_parsed"] += 1
            if body.strip():
                val["nonzero_body"] += 1
            payload = build_payload(url, title, body, published, source_id,
                                    keywords, hits)
            if dry_run:
                log.info("[dry-run] %-9s date=%s scope=%s :: %s",
                         kind, published, ",".join(hits[:3]), title[:60])
            else:
                supabase_client.insert_document(payload)
            stats["inserted"] += 1
        except Exception:
            stats["errors"] += 1
            log.exception("[hansard] item failed (%s); continuing", url)
            if stats["errors"] > ERROR_BUDGET:
                raise RuntimeError(
                    f"[hansard] exceeded the error budget ({stats['errors']} "
                    f"failures): systemic, not transient. Aborting.")

    # Enablement bar (docs/hansard-design.md): >= 90% date parse on kept docs,
    # scope filter keeps a sane fraction, nonzero bodies; projected extraction
    # volume = scope_kept per run.
    k = val["scope_kept"] or 1
    pt = val.get("paras_total", 0) or 1
    log.info("VALIDATION [hansard]: index_days=%d committee_links=%d "
             "new_fetched=%d scope_kept=%d scope_dropped=%d date_parsed=%d "
             "(%d%%) nonzero_body=%d (%d%%) sections_kept=%d/%d (%d%%)",
             stats["index_days"], stats["committee_links"], stats["new_fetched"],
             val["scope_kept"], stats["skipped_scope"],
             val["date_parsed"], round(100 * val["date_parsed"] / k),
             val["nonzero_body"], round(100 * val["nonzero_body"] / k),
             val.get("paras_kept", 0), val.get("paras_total", 0),
             round(100 * val.get("paras_kept", 0) / pt))
    log.info("hansard: %s%s", stats, " (DRY RUN)" if dry_run else "")
    if not dry_run and source_id:
        supabase_client.update_source_last_collected(
            source_id, datetime.now(timezone.utc))
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ontario Hansard collector")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch, parse, and filter but write nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    collect(dry_run=args.dry_run)
    sys.exit(0)
