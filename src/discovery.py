"""Discovery engine — weekly propose-then-approve job.

Reads the last WINDOW_DAYS of collected documents and PROPOSES (never acts):
new sources, new entities, alias updates. Its entire write surface is the
discovered_sources / discovered_entities tables; it never inserts into
sources or organizations, never fetches a candidate domain, never schedules
anything. Approval happens in the web app (/discovery); wiring a collector to
an approved source remains a reviewed PR.

Design: docs/discovery-engine-design.md (approved), with the reviewed §8
parameters baked in below.

Verify with a zero-write run:  python -m src.discovery --dry-run
"""
import argparse
import json
import logging
import os
import re
import sys
import unicodedata
from datetime import date, timedelta
from typing import Optional
from urllib.parse import urlparse

import prompts

from . import supabase_client

log = logging.getLogger(__name__)

# §8-approved parameters. Constants so tuning is a one-line reviewed change.
WINDOW_DAYS = 30                 # rolling window
DOMAIN_MIN_DOCS = 5              # domain must appear in >=5 distinct documents…
DOMAIN_MIN_SOURCES = 2           # …coming from >=2 distinct sources
ENTITY_MIN_DOCS = 3              # entity must recur in >=3 documents
TIER2_MAX_DOCS = 50              # LLM triage cap per weekly run
TIER2_MODEL = os.environ.get("DISCOVERY_MODEL", "claude-haiku-4-5")
TIER2_MIN_BODY_CHARS = 500       # only rich-bodied docs go to the LLM
MAX_EVIDENCE_IDS = 10
MAX_SAMPLE_URLS = 5

HEURISTIC_STAMP = "heuristic@v1"
UNRESOLVED_STAMP = "unresolved-orgs@v1"

_URL_RE = re.compile(r"https?://[^\s\"'<>\)\]]+", re.IGNORECASE)

_KIND_HINTS = [
    ("board", re.compile(r"board|minutes|agenda|meeting", re.I)),
    ("newsroom", re.compile(r"news|release|media|newsroom|rss|atom", re.I)),
    ("association", re.compile(r"association|federation|chiefs|caclea|oacp|capb", re.I)),
]

_SYSTEM = (
    "You are the Signal North discovery triage engine. "
    "Respond only with JSON matching the provided schema."
)

_ENTITY_KINDS = ["organization", "person_appointment", "company_canada_intent"]
_CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entity_kind": {"type": "string", "enum": _ENTITY_KINDS},
                    "name": {"type": "string"},
                    "detail": {"type": "string"},
                    "organization": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "role": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "evidence_doc_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["entity_kind", "name", "detail", "organization",
                             "role", "evidence_doc_ids"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["candidates"],
    "additionalProperties": False,
}


def normalize(name: str) -> str:
    """Accent/case/whitespace folding — same discipline as the org resolver."""
    collapsed = " ".join((name or "").split())
    decomposed = unicodedata.normalize("NFKD", collapsed)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def host_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def is_blocked(host: str, blocklist: set) -> bool:
    """host is blocked if it equals a blocklisted domain or is a subdomain."""
    return any(host == b or host.endswith("." + b) for b in blocklist)


def guess_kind(sample_urls: list) -> str:
    joined = " ".join(sample_urls)
    for kind, pattern in _KIND_HINTS:
        if pattern.search(joined):
            return kind
    return "publisher_other"


def suggest_name(domain: str) -> str:
    stem = domain.split(".")[0].replace("-", " ").replace("_", " ").title()
    return f"{stem} ({domain})"


# ---------------------------------------------------------------------------
# Detector 1: new source domains (pure heuristic, no LLM, no fetching)
# ---------------------------------------------------------------------------
def detect_source_domains(documents: list, known_hosts: set, blocklist: set) -> list:
    """Domains referenced in stored bodies that we don't collect from.

    Returns proposals meeting the §8 thresholds: >=DOMAIN_MIN_DOCS distinct
    documents from >=DOMAIN_MIN_SOURCES distinct sources.
    """
    by_domain: dict = {}
    for doc in documents:
        text = doc.get("content") or ""
        if not text:
            continue
        seen_here: set = set()
        for url in _URL_RE.findall(text):
            host = host_of(url)
            if not host or host in seen_here:
                continue
            if is_blocked(host, blocklist) or is_blocked(host, known_hosts) or host in known_hosts:
                continue
            seen_here.add(host)
            entry = by_domain.setdefault(host, {"doc_ids": set(), "source_ids": set(),
                                                "sample_urls": []})
            entry["doc_ids"].add(doc["id"])
            entry["source_ids"].add(doc.get("source_id"))
            if len(entry["sample_urls"]) < MAX_SAMPLE_URLS and url not in entry["sample_urls"]:
                entry["sample_urls"].append(url)

    proposals = []
    for domain, entry in by_domain.items():
        if len(entry["doc_ids"]) < DOMAIN_MIN_DOCS:
            continue
        if len(entry["source_ids"]) < DOMAIN_MIN_SOURCES:
            continue
        proposals.append({
            "domain": domain,
            "suggested_name": suggest_name(domain),
            "kind": guess_kind(entry["sample_urls"]),
            "sample_urls": entry["sample_urls"],
            "evidence_document_ids": sorted(entry["doc_ids"])[:MAX_EVIDENCE_IDS],
            "mention_count": len(entry["doc_ids"]),
            "source_count": len(entry["source_ids"]),
            "proposed_by": HEURISTIC_STAMP,
        })
    proposals.sort(key=lambda p: -p["mention_count"])
    return proposals


# ---------------------------------------------------------------------------
# Detector 2 tier 1: recurring unresolved org names (free, deterministic)
# ---------------------------------------------------------------------------
def detect_unresolved_orgs(signals: list, org_lookup: dict) -> list:
    """signals rows with needs_org_resolution grouped by normalized name.

    org_lookup maps normalized canonical/alias -> (org_id, canonical_name);
    a near-match (containment either way) becomes an alias_update proposal.
    """
    grouped: dict = {}
    for s in signals:
        raw = (s.get("unresolved_org_name") or "").strip()
        if not raw:
            continue
        key = normalize(raw)
        entry = grouped.setdefault(key, {"name": raw, "doc_ids": set()})
        if s.get("document_id"):
            entry["doc_ids"].add(s["document_id"])

    proposals = []
    for key, entry in grouped.items():
        if len(entry["doc_ids"]) < ENTITY_MIN_DOCS:
            continue
        match = _near_match(key, org_lookup)
        base = {
            "name": entry["name"],
            "normalized_name": key,
            "evidence_document_ids": sorted(entry["doc_ids"])[:MAX_EVIDENCE_IDS],
            "mention_count": len(entry["doc_ids"]),
            "proposed_by": UNRESOLVED_STAMP,
        }
        if match:
            org_id, canonical = match
            proposals.append({**base, "entity_kind": "alias_update",
                              "existing_organization_id": org_id,
                              "detail": {"add_alias_to": canonical}})
        else:
            proposals.append({**base, "entity_kind": "organization", "detail": {}})
    proposals.sort(key=lambda p: -p["mention_count"])
    return proposals


def _near_match(normalized_name: str, org_lookup: dict) -> Optional[tuple]:
    """Exact-normalized => already known (no proposal needed => return None
    upstream via exact check). Containment either way => alias candidate."""
    if normalized_name in org_lookup:
        return org_lookup[normalized_name]
    for known, target in org_lookup.items():
        if len(known) >= 8 and (known in normalized_name or normalized_name in known):
            return target
    return None


# ---------------------------------------------------------------------------
# Detector 2 tier 2: LLM triage over rich-bodied docs (capped, Haiku)
# ---------------------------------------------------------------------------
def llm_candidates(documents: list, model: str = TIER2_MODEL) -> tuple:
    """Run discovery@v1 over rich-bodied docs. Returns (candidates, stamp)."""
    import anthropic  # lazy so the module imports without the SDK

    rich = [d for d in documents
            if len(d.get("content") or "") >= TIER2_MIN_BODY_CHARS][:TIER2_MAX_DOCS]
    if not rich:
        return [], prompts.prompt_stamp("discovery")

    prompt_text, stamp = prompts.get_prompt("discovery")
    blob = "\n\n".join(
        f"[doc:{d['id']}] {d.get('title', '')}\n{(d.get('content') or '')[:6000]}"
        for d in rich
    )
    filled = prompt_text.replace("{documents}", blob)

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": filled}],
        output_config={"format": {"type": "json_schema", "schema": _CANDIDATE_SCHEMA}},
    )
    if resp.stop_reason == "refusal":
        log.warning("Discovery triage refused")
        return [], stamp
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(text)

    valid_ids = {d["id"] for d in rich}
    candidates = []
    for c in data.get("candidates", []):
        evidence = [i for i in c.get("evidence_doc_ids", []) if i in valid_ids]
        if not evidence:        # provenance rule: no evidence, no proposal
            continue
        candidates.append({**c, "evidence_doc_ids": evidence[:MAX_EVIDENCE_IDS]})
    return candidates, stamp


def merge_llm_candidates(candidates: list, stamp: str, org_lookup: dict) -> list:
    """Merge by (kind, normalized name); drop below-threshold organizations.
    Appointments/intent keep a lower bar (>=1 doc) — they are single events by
    nature, and the human review is the filter."""
    merged: dict = {}
    for c in candidates:
        key = (c["entity_kind"], normalize(c["name"]))
        entry = merged.setdefault(key, {"doc_ids": set(), "detail": c.get("detail") or "",
                                        "organization": c.get("organization"),
                                        "role": c.get("role"), "name": c["name"]})
        entry["doc_ids"].update(c["evidence_doc_ids"])

    proposals = []
    for (kind, norm), entry in merged.items():
        count = len(entry["doc_ids"])
        if kind == "organization":
            if count < ENTITY_MIN_DOCS or norm in org_lookup:
                continue
        detail: dict = {"summary": entry["detail"]}
        if entry.get("organization"):
            detail["organization"] = entry["organization"]
        if entry.get("role"):
            detail["role"] = entry["role"]
        proposals.append({
            "entity_kind": kind,
            "name": entry["name"],
            "normalized_name": norm,
            "detail": detail,
            "evidence_document_ids": sorted(entry["doc_ids"])[:MAX_EVIDENCE_IDS],
            "mention_count": count,
            "proposed_by": stamp,
        })
    return proposals


# ---------------------------------------------------------------------------
# Upserts: propose new, refresh proposed, never touch reviewed
# ---------------------------------------------------------------------------
def upsert_source_proposal(proposal: dict, dry_run: bool) -> str:
    existing = supabase_client.fetch_rows_where(
        "discovered_sources", "id,status,evidence_document_ids",
        {"domain": f"eq.{proposal['domain']}"}, limit=1)
    if existing:
        row = existing[0]
        if row["status"] != "proposed":
            return "skipped_reviewed"      # approved/rejected are never touched
        if dry_run:
            return "would_refresh"
        merged_evidence = sorted(set(row.get("evidence_document_ids") or [])
                                 | set(proposal["evidence_document_ids"]))[:MAX_EVIDENCE_IDS]
        supabase_client.update_row("discovered_sources", row["id"], {
            "mention_count": proposal["mention_count"],
            "source_count": proposal["source_count"],
            "sample_urls": proposal["sample_urls"],
            "evidence_document_ids": merged_evidence,
            "last_seen_on": date.today().isoformat(),
        })
        return "refreshed"
    if dry_run:
        return "would_propose"
    supabase_client.insert_row("discovered_sources", proposal)
    return "proposed"


def upsert_entity_proposal(proposal: dict, dry_run: bool) -> str:
    existing = supabase_client.fetch_rows_where(
        "discovered_entities", "id,status,evidence_document_ids",
        {"entity_kind": f"eq.{proposal['entity_kind']}",
         "normalized_name": f"eq.{proposal['normalized_name']}"}, limit=1)
    if existing:
        row = existing[0]
        if row["status"] != "proposed":
            return "skipped_reviewed"
        if dry_run:
            return "would_refresh"
        merged_evidence = sorted(set(row.get("evidence_document_ids") or [])
                                 | set(proposal["evidence_document_ids"]))[:MAX_EVIDENCE_IDS]
        supabase_client.update_row("discovered_entities", row["id"], {
            "mention_count": proposal["mention_count"],
            "evidence_document_ids": merged_evidence,
            "detail": proposal.get("detail", {}),
        })
        return "refreshed"
    if dry_run:
        return "would_propose"
    supabase_client.insert_row("discovered_entities", proposal)
    return "proposed"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run(dry_run: bool = False, skip_llm: bool = False) -> int:
    since = (date.today() - timedelta(days=WINDOW_DAYS)).isoformat()
    stats: dict = {"documents": 0, "source_proposals": 0, "entity_proposals": 0,
                   "skipped_reviewed": 0, "errors": 0}

    try:
        documents = supabase_client.fetch_rows_where(
            "documents", "id,source_id,title,content",
            {"created_at": f"gte.{since}"})
        stats["documents"] = len(documents)

        sources = supabase_client.fetch_rows("sources", "id,name,url")
        known_hosts = {host_of(s["url"]) for s in sources if s.get("url")}
        blocklist = {b["domain"].lower() for b in
                     supabase_client.fetch_rows("discovery_blocklist", "domain")}

        orgs = supabase_client.fetch_rows("organizations", "id,canonical_name,aliases")
        org_lookup: dict = {}
        for o in orgs:
            org_lookup[normalize(o["canonical_name"])] = (o["id"], o["canonical_name"])
            for alias in (o.get("aliases") or []):
                org_lookup.setdefault(normalize(alias), (o["id"], o["canonical_name"]))

        # Detector 1 — source domains
        for proposal in detect_source_domains(documents, known_hosts, blocklist):
            outcome = upsert_source_proposal(proposal, dry_run)
            log.info("[source %s] %s (%d docs / %d sources)", outcome,
                     proposal["domain"], proposal["mention_count"], proposal["source_count"])
            if outcome == "skipped_reviewed":
                stats["skipped_reviewed"] += 1
            else:
                stats["source_proposals"] += 1

        # Detector 2 tier 1 — unresolved orgs
        signals = supabase_client.fetch_rows_where(
            "signals", "id,document_id,unresolved_org_name",
            {"needs_org_resolution": "eq.true", "created_at": f"gte.{since}"})
        entity_proposals = detect_unresolved_orgs(signals, org_lookup)

        # Detector 2 tier 2 — LLM triage (capped; optional)
        if not skip_llm and os.environ.get("ANTHROPIC_API_KEY"):
            try:
                candidates, stamp = llm_candidates(documents)
                entity_proposals.extend(merge_llm_candidates(candidates, stamp, org_lookup))
            except Exception:
                log.exception("LLM triage failed; heuristic proposals still apply")
                stats["errors"] += 1
        elif not skip_llm:
            log.warning("ANTHROPIC_API_KEY not set; skipping LLM triage tier")

        for proposal in entity_proposals:
            outcome = upsert_entity_proposal(proposal, dry_run)
            log.info("[entity %s] %s %r (%d docs)", outcome, proposal["entity_kind"],
                     proposal["name"], proposal["mention_count"])
            if outcome == "skipped_reviewed":
                stats["skipped_reviewed"] += 1
            else:
                stats["entity_proposals"] += 1

    except Exception:
        log.exception("Discovery run failed")
        return 1

    log.info("Discovery complete%s: %s", " (DRY RUN)" if dry_run else "", stats)
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Signal North discovery engine (propose-only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="detect and log proposals but write nothing")
    parser.add_argument("--skip-llm", action="store_true",
                        help="run only the free deterministic detectors")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(dry_run=args.dry_run, skip_llm=args.skip_llm))
