"""Signal extraction pipeline (Anthropic Claude API + versioned prompt library).

Reads captured documents, sends each through the Claude Messages API with the
versioned extraction prompt (prompts/extraction), and writes structured signals.

Design decisions (vs. the PR #6 original this replaces):
- Uses the Anthropic Claude API, not an OpenAI-compatible endpoint.
- Pulls the prompt from the versioned prompt library and stamps the prompt
  version onto every row (signals.extracted_by = "extraction@v1"), so provenance
  survives a model swap and is never a stale model string.
- Uses structured outputs (output_config.format + a JSON schema) so the model is
  constrained to valid JSON and valid signal_type / confidence enum values —
  no fragile ```-fence parsing, no invalid-enum insert failures.
- Uses the project's supabase_client REST helpers, not supabase-py.
- Does NOT drop signals whose organization can't be resolved. It stores them with
  organization_id = NULL, the raw name in unresolved_org_name, and
  needs_org_resolution = true, so they surface for manual resolution instead of
  vanishing. (Requires the additive migration in
  migrations/2026-07-09_signals_unresolved_org.sql.)

Run manually with `python -m src.signal_extractor`. It is intentionally NOT wired
into any scheduled workflow — nothing runs autonomously pre-ethics-gate.
"""
import json
import logging
import os
import unicodedata
from typing import Callable, Optional

import prompts

from . import supabase_client
from . import taxonomy

log = logging.getLogger(__name__)

# Default model. Overridable via EXTRACTION_MODEL (e.g. claude-sonnet-5 or
# claude-haiku-4-5 for cheaper high-volume runs). See the PR for the cost note.
DEFAULT_MODEL = os.environ.get("EXTRACTION_MODEL", "claude-opus-4-8")

_SYSTEM = (
    "You are the Signal North procurement-intelligence extraction engine. "
    "Respond only with JSON matching the provided schema."
)

# Valid signal_type enum labels (mirrors the DB enum). Kept here so the schema
# constrains the model to values the signals.signal_type column will accept.
SIGNAL_TYPES = [
    "budget_allocation", "capital_plan_item", "funding_program", "mandate_direction",
    "policy_announcement", "legislative_change", "procurement_reform", "board_decision",
    "pilot_program", "rfi_pre_rfp", "tender_published", "contract_award",
    "leadership_change", "inquiry_recommendation", "vendor_activity", "funding_announcement",
    "political_pressure", "media_coverage_wave", "oversight_recommendation",
    "election_commitment", "transfer_program", "contract_expiry", "vehicle_refresh", "other",
]
CONFIDENCE_LEVELS = ["confirmed", "probable", "speculative"]


def _nullable(json_type: str) -> dict:
    return {"anyOf": [{"type": json_type}, {"type": "null"}]}


_SIGNAL_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "signal_type": {"type": "string", "enum": SIGNAL_TYPES},
        "summary": {"type": "string"},
        "confidence": {"type": "string", "enum": CONFIDENCE_LEVELS},
        "materiality": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "organization_name": _nullable("string"),
        "category_slug": _nullable("string"),
        "amount_min_cad": _nullable("number"),
        "amount_max_cad": _nullable("number"),
        "expected_timing": _nullable("string"),
        "defence_relevant": {"type": "boolean"},
        "quote_or_line": _nullable("string"),
    },
    "required": [
        "title", "signal_type", "summary", "confidence", "materiality",
        "organization_name", "category_slug", "amount_min_cad", "amount_max_cad",
        "expected_timing", "defence_relevant", "quote_or_line",
    ],
    "additionalProperties": False,
}
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"signals": {"type": "array", "items": _SIGNAL_ITEM_SCHEMA}},
    "required": ["signals"],
    "additionalProperties": False,
}


def _normalize(name: str) -> str:
    """Normalize a name for matching: collapse whitespace, strip diacritics,
    lowercase. Accent-insensitive so the model emitting "Surete du Quebec"
    resolves to a "Sûreté du Québec" record — French resolution shouldn't depend
    on the model reproducing accents exactly."""
    collapsed = " ".join((name or "").split())
    decomposed = unicodedata.normalize("NFKD", collapsed)
    ascii_folded = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ascii_folded.lower()


def build_resolver(rows: list, key_fields: tuple, alias_field: Optional[str] = None) -> Callable[[str], Optional[str]]:
    """Build an exact-match (normalized) name -> id resolver.

    Deliberately NOT substring-matching: a naive substring match mis-attributes
    short names (e.g. "DND", "OPP") to unrelated rows. Coverage comes from the
    aliases column, not from loose matching.
    """
    lookup: dict = {}
    for row in rows:
        for field in key_fields:
            val = row.get(field)
            if val:
                lookup.setdefault(_normalize(val), row["id"])
        if alias_field:
            for alias in (row.get(alias_field) or []):
                if alias:
                    lookup.setdefault(_normalize(alias), row["id"])

    def resolve(name: str) -> Optional[str]:
        return lookup.get(_normalize(name)) if name else None

    return resolve


def build_signal_payload(raw: dict, document_id: str, stamp: str,
                         resolve_org: Callable[[str], Optional[str]],
                         resolve_cat: Callable[[str], Optional[str]],
                         doc_type: Optional[str] = None) -> dict:
    """Transform one raw LLM signal into a signals-table row payload.

    Pure function (no I/O) so it can be unit-tested without the API or DB.
    doc_type is the source document's type; it sets a floor on the demand-
    strength grade (src/taxonomy.py) and is passed by run_extraction.
    """
    org_name = (raw.get("organization_name") or "").strip()
    org_id = resolve_org(org_name) if org_name else None
    unresolved = bool(org_name) and org_id is None

    cat_slug = (raw.get("category_slug") or "").strip()
    cat_id = resolve_cat(cat_slug) if cat_slug else None

    try:
        materiality = int(raw.get("materiality", 3))
    except (TypeError, ValueError):
        materiality = 3
    materiality = min(max(materiality, 1), 5)

    signal_type = raw.get("signal_type") or "other"
    if signal_type not in SIGNAL_TYPES:
        signal_type = "other"
    confidence = raw.get("confidence") or "probable"
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "probable"

    return {
        "document_id": document_id,
        "organization_id": org_id,
        "category_id": cat_id,
        "signal_type": signal_type,
        "evidence_grade": taxonomy.grade(signal_type, doc_type or ""),
        "evidence_grade_version": taxonomy.TAXONOMY_VERSION,
        "title": (raw.get("title") or "Untitled signal")[:200],
        "summary": raw.get("summary") or "",
        "quote_or_line": raw.get("quote_or_line"),
        "amount_min_cad": raw.get("amount_min_cad"),
        "amount_max_cad": raw.get("amount_max_cad"),
        "expected_timing": raw.get("expected_timing"),
        "confidence": confidence,
        "materiality": materiality,
        "extracted_by": stamp,
        "reviewed": False,
        "needs_org_resolution": unresolved,
        "unresolved_org_name": org_name if unresolved else None,
    }


def fill_prompt(template: str, **values) -> str:
    """Substitute {name} placeholders without str.format().

    The prompt contains a literal JSON example ({"signals": [...]}), so
    str.format() would read it as a replacement field and raise KeyError. We
    replace only the known named tokens and leave every other brace untouched.
    """
    filled = template
    for key, value in values.items():
        filled = filled.replace("{" + key + "}", str(value))
    return filled


# Cap the body passed to Claude. Board minutes can run to hundreds of pages;
# the first N chars carry the agenda and decisions, and an unbounded body is
# an unbounded token bill. Tune with EXTRACTION_MAX_BODY_CHARS if needed.
MAX_BODY_CHARS = int(os.environ.get("EXTRACTION_MAX_BODY_CHARS", "60000"))


def extract_signals(doc: dict, source_name: str, model: str) -> tuple:
    """Call Claude to extract signals from one document. Returns (signals, stamp)."""
    import anthropic  # lazy so the module imports without the SDK installed

    prompt_text, stamp = prompts.get_prompt("extraction")
    # Rich doc types (board_minutes) store their full text in documents.content;
    # title-only doc types (CSV/RSS rows) fall back to the title as before.
    body = (doc.get("content") or "").strip() or doc.get("title", "")
    filled = fill_prompt(
        prompt_text,
        title=doc.get("title", "Unknown"),
        doc_type=doc.get("doc_type", "other"),
        source_name=source_name,
        published_on=doc.get("published_on", "Unknown"),
        url=doc.get("url", ""),
        content=body[:MAX_BODY_CHARS],
    )

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": filled}],
        output_config={"format": {"type": "json_schema", "schema": _RESPONSE_SCHEMA}},
    )
    if resp.stop_reason == "refusal":
        log.warning("Extraction refused for document %s", doc.get("id"))
        return [], stamp

    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(text)  # schema-constrained, so this is valid JSON
    return data.get("signals", []), stamp


def run_extraction(batch_size: int = 20, model: str = DEFAULT_MODEL, dry_run: bool = False,
                   doc_type: str | None = None, doc_types: list | None = None,
                   newest_first: bool = False) -> dict:
    """Process up to batch_size captured documents.

    doc_types (a list) scopes the run to several types at once; the daily forward
    path passes tender_notice/news_release/grant_program so the token budget goes
    to signal a brief can act on, leaving the award backlog to a separate pass.
    newest_first orders by event date descending, so a capped run drains the
    freshest documents first (a closing-soon tender before a month-old one).

    dry_run=True still calls Claude and resolves orgs (so you can verify the API
    integration, the extraction@v1 stamp, and resolution), but writes NOTHING:
    no signals inserted, no document status changed. Use it as a smoke test.
    """
    stats = {"documents_processed": 0, "signals_created": 0,
             "needs_org_resolution": 0, "errors": 0}

    resolve_org = build_resolver(
        supabase_client.fetch_rows("organizations", "id,canonical_name,aliases"),
        key_fields=("canonical_name",), alias_field="aliases",
    )
    resolve_cat = build_resolver(
        supabase_client.fetch_rows("categories", "id,slug,name"),
        key_fields=("slug", "name"),
    )

    # nullslast: undated documents sort after dated ones, so a capped forward run
    # never spends its budget on undated backlog ahead of a dated, closing-soon doc.
    order = "published_on.desc.nullslast" if newest_first else None
    docs = supabase_client.get_documents_by_status(
        "captured", batch_size, doc_type=doc_type, doc_types=doc_types, order=order)
    if not docs:
        log.info("No captured documents to process")
        return stats
    log.info("Processing %d documents%s", len(docs), " (DRY RUN — no writes)" if dry_run else "")

    for doc in docs:
        try:
            source_name = supabase_client.get_source_name(doc["source_id"])
            raw_signals, stamp = extract_signals(doc, source_name, model)
            for raw in raw_signals:
                payload = build_signal_payload(raw, doc["id"], stamp, resolve_org,
                                               resolve_cat, doc.get("doc_type"))
                if dry_run:
                    log.info(
                        "[dry-run] would insert: extracted_by=%s type=%s grade=%s conf=%s mat=%s "
                        "org_id=%s needs_org_resolution=%s unresolved=%r title=%r",
                        payload["extracted_by"], payload["signal_type"], payload["evidence_grade"],
                        payload["confidence"], payload["materiality"], payload["organization_id"],
                        payload["needs_org_resolution"], payload["unresolved_org_name"],
                        payload["title"],
                    )
                else:
                    supabase_client.insert_signal(payload)
                stats["signals_created"] += 1
                if payload["needs_org_resolution"]:
                    stats["needs_org_resolution"] += 1
            if not dry_run:
                supabase_client.update_document_status(doc["id"], "extracted")
            stats["documents_processed"] += 1
        except Exception as e:  # noqa: BLE001 - isolate per-document failures
            log.exception("Error processing document %s", doc.get("id"))
            stats["errors"] += 1
            if not dry_run:
                try:
                    supabase_client.update_document_status(doc["id"], "failed", str(e)[:500])
                except Exception:
                    log.exception("Could not mark document %s as failed", doc.get("id"))

    log.info("Extraction complete%s: %s", " (DRY RUN)" if dry_run else "", stats)
    return stats


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Signal North extraction pipeline")
    parser.add_argument("--limit", type=int, default=20,
                        help="max documents to process this run (default 20)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Claude model id (default {DEFAULT_MODEL})")
    parser.add_argument("--dry-run", action="store_true",
                        help="call Claude and resolve orgs but write nothing (smoke test)")
    parser.add_argument("--doc-type", default=None,
                        help="only process documents of this doc_type (e.g. board_minutes) — "
                             "lets rich-bodied types run without burning tokens on the "
                             "title-only backlog")
    parser.add_argument("--doc-types", default=None,
                        help="comma-separated doc_types to process this run (e.g. "
                             "tender_notice,news_release,grant_program): the daily "
                             "forward-signal path")
    parser.add_argument("--newest-first", action="store_true",
                        help="process the freshest event dates first, so a capped run "
                             "drains closing-soon documents ahead of stale ones")
    args = parser.parse_args()

    doc_types = [t.strip() for t in args.doc_types.split(",") if t.strip()] if args.doc_types else None

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run_extraction(batch_size=args.limit, model=args.model, dry_run=args.dry_run,
                            doc_type=args.doc_type, doc_types=doc_types,
                            newest_first=args.newest_first)
    sys.exit(0 if result["errors"] == 0 else 1)
