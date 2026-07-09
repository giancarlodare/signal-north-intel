"""Signal Extraction Pipeline.

This is the CRITICAL PATH item: it reads captured documents and uses Claude
to extract structured signals from them. Without this, documents sit in the
database but never become intelligence.

Flow:
1. Query documents with status='captured' (not yet processed)
2. For each document, fetch its content (title + any available text)
3. Send to Claude with the extraction prompt
4. Parse Claude's structured response into signal records
5. Insert signals into the database
6. Update document status to 'extracted'

The extraction prompt enforces:
- Signal type taxonomy (from schema enums)
- Confidence levels (confirmed/probable/speculative)
- Materiality scoring (1-5)
- Organization resolution (match to existing orgs)
- Category assignment
- Defence-relevance tagging
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from . import supabase_client

log = logging.getLogger(__name__)

# The extraction prompt — this IS the intellectual property
EXTRACTION_PROMPT = """You are the Signal North intelligence extraction engine. Your job is to read a government document (tender notice, award notice, news release, board minutes, or budget document) and extract structured intelligence signals from it.

DOCUMENT TO ANALYZE:
Title: {title}
Type: {doc_type}
Source: {source_name}
Published: {published_on}
URL: {url}
Content/Description: {content}

INSTRUCTIONS:
Extract every procurement-relevant signal from this document. For each signal, provide:

1. **title**: One-line headline (max 100 chars)
2. **signal_type**: MUST be one of: budget_allocation, capital_plan_item, funding_program, mandate_direction, policy_announcement, legislative_change, procurement_reform, board_decision, pilot_program, rfi_pre_rfp, tender_published, contract_award, leadership_change, inquiry_recommendation, vendor_activity, funding_announcement, political_pressure, media_coverage_wave, oversight_recommendation, election_commitment, transfer_program, contract_expiry, vehicle_refresh
3. **summary**: 2-4 sentences explaining what this means for vendors. Be specific and decision-useful.
4. **confidence**: confirmed (stated plainly in document), probable (strong inference), speculative (pattern-based)
5. **materiality**: 1-5 (5 = a BD lead should act this week; 1 = background context)
6. **organization_name**: The buying organization (use canonical name if you recognize it)
7. **category_slug**: Best match from: body-worn-cameras, digital-evidence, records-cad, alpr, drones-rpas, ai-analytics, cyber, radios-comms, surveillance, forensics, protective-equipment, uniforms, use-of-force, fleet, facilities, training-centres, training-services, consulting, managed-services, c4isr, uncrewed-defence, soldier-systems
8. **amount_min_cad**: Dollar amount if stated (numeric, no symbols)
9. **amount_max_cad**: Upper range if stated
10. **expected_timing**: When the procurement might happen (free text)
11. **defence_relevant**: true/false — is this relevant to defence/military?
12. **quote_or_line**: The exact line or figure from the document supporting this signal

If the document contains NO procurement-relevant signals (e.g., it's about food services or office supplies unrelated to public safety), return an empty array.

RESPOND WITH VALID JSON ONLY — an array of signal objects. No markdown, no explanation outside the JSON.
"""

# Organizations lookup cache
_ORG_CACHE: Dict[str, str] = {}
_CAT_CACHE: Dict[str, str] = {}


def _load_org_cache():
    """Load organizations into memory for fuzzy matching."""
    global _ORG_CACHE
    if _ORG_CACHE:
        return
    
    from supabase import create_client
    client = create_client(
        os.environ.get("SUPABASE_URL", ""),
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )
    orgs = client.table("organizations").select("id,canonical_name,aliases").execute().data
    for org in orgs:
        _ORG_CACHE[org["canonical_name"].lower()] = org["id"]
        for alias in (org.get("aliases") or []):
            _ORG_CACHE[alias.lower()] = org["id"]


def _load_cat_cache():
    """Load categories into memory for matching."""
    global _CAT_CACHE
    if _CAT_CACHE:
        return
    
    from supabase import create_client
    client = create_client(
        os.environ.get("SUPABASE_URL", ""),
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )
    cats = client.table("categories").select("id,slug,name").execute().data
    for cat in cats:
        _CAT_CACHE[cat["slug"]] = cat["id"]
        _CAT_CACHE[cat["name"].lower()] = cat["id"]


def resolve_organization(name: str) -> Optional[str]:
    """Resolve an organization name to its UUID."""
    _load_org_cache()
    if not name:
        return None
    
    # Exact match
    lower = name.lower().strip()
    if lower in _ORG_CACHE:
        return _ORG_CACHE[lower]
    
    # Substring match
    for key, org_id in _ORG_CACHE.items():
        if key in lower or lower in key:
            return org_id
    
    return None


def resolve_category(slug: str) -> Optional[str]:
    """Resolve a category slug to its UUID."""
    _load_cat_cache()
    if not slug:
        return None
    return _CAT_CACHE.get(slug.lower().strip())


def extract_signals_from_document(doc: Dict, source_name: str) -> List[Dict]:
    """Use Claude/LLM to extract signals from a single document.
    
    Uses the OpenAI-compatible endpoint configured in the sandbox.
    """
    from openai import OpenAI
    
    client = OpenAI()  # Uses OPENAI_API_KEY and OPENAI_API_BASE from env
    
    prompt = EXTRACTION_PROMPT.format(
        title=doc.get("title", "Unknown"),
        doc_type=doc.get("doc_type", "other"),
        source_name=source_name,
        published_on=doc.get("published_on", "Unknown"),
        url=doc.get("url", ""),
        content=doc.get("title", ""),  # For now, we only have titles from CSV collection
    )
    
    try:
        response = client.chat.completions.create(
            model="claude-sonnet-4-20250514",
            messages=[
                {"role": "system", "content": "You are a procurement intelligence extraction engine. Respond only with valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000,
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON response
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        signals = json.loads(content)
        if not isinstance(signals, list):
            signals = [signals]
        
        return signals
        
    except json.JSONDecodeError as e:
        log.warning("Failed to parse Claude response as JSON: %s", e)
        return []
    except Exception as e:
        log.error("Claude extraction failed: %s", e)
        return []


def process_unextracted_documents(batch_size: int = 20) -> Dict[str, int]:
    """Process a batch of captured documents through the extraction pipeline.
    
    Returns stats on what was processed.
    """
    from supabase import create_client
    
    client = create_client(
        os.environ.get("SUPABASE_URL", ""),
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )
    
    stats = {"documents_processed": 0, "signals_created": 0, "errors": 0}
    
    # Get unprocessed documents
    docs = client.table("documents").select(
        "id,title,doc_type,url,published_on,source_id"
    ).eq("status", "captured").limit(batch_size).execute().data
    
    if not docs:
        log.info("No unprocessed documents found")
        return stats
    
    log.info("Processing %d documents", len(docs))
    
    for doc in docs:
        try:
            # Get source name for context
            source = client.table("sources").select("name").eq("id", doc["source_id"]).limit(1).execute().data
            source_name = source[0]["name"] if source else "Unknown"
            
            # Extract signals
            raw_signals = extract_signals_from_document(doc, source_name)
            
            if not raw_signals:
                # Mark as irrelevant if no signals found
                client.table("documents").update({"status": "extracted"}).eq("id", doc["id"]).execute()
                stats["documents_processed"] += 1
                continue
            
            # Insert each signal
            for raw in raw_signals:
                org_id = resolve_organization(raw.get("organization_name", ""))
                cat_id = resolve_category(raw.get("category_slug", ""))
                
                signal_payload = {
                    "document_id": doc["id"],
                    "organization_id": org_id,
                    "category_id": cat_id,
                    "signal_type": raw.get("signal_type", "other"),
                    "title": raw.get("title", "Untitled signal")[:200],
                    "summary": raw.get("summary", ""),
                    "quote_or_line": raw.get("quote_or_line"),
                    "amount_min_cad": raw.get("amount_min_cad"),
                    "amount_max_cad": raw.get("amount_max_cad"),
                    "expected_timing": raw.get("expected_timing"),
                    "confidence": raw.get("confidence", "probable"),
                    "materiality": min(max(int(raw.get("materiality", 3)), 1), 5),
                    "extracted_by": "claude-sonnet-4-20250514",
                    "reviewed": False,
                }
                
                # Only insert if we have a valid organization_id (required field)
                if not org_id:
                    log.warning("Skipping signal '%s' — could not resolve org '%s'",
                               raw.get("title", ""), raw.get("organization_name", ""))
                    continue
                
                try:
                    client.table("signals").insert(signal_payload).execute()
                    stats["signals_created"] += 1
                except Exception as e:
                    log.warning("Failed to insert signal: %s", e)
            
            # Update document status
            client.table("documents").update({"status": "extracted"}).eq("id", doc["id"]).execute()
            stats["documents_processed"] += 1
            
        except Exception as e:
            log.error("Error processing document %s: %s", doc["id"], e)
            stats["errors"] += 1
            # Mark as failed
            try:
                client.table("documents").update({
                    "status": "failed",
                    "error_detail": str(e)[:500]
                }).eq("id", doc["id"]).execute()
            except:
                pass
    
    return stats


def run_extraction(batch_size: int = 20) -> int:
    """Run the signal extraction pipeline."""
    stats = process_unextracted_documents(batch_size)
    log.info("Extraction complete: %s", stats)
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run_extraction())
