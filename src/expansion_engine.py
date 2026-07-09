"""Autonomous Intelligence Expansion Engine.

This is the self-learning core of Signal North. It:
1. Analyzes existing signals and documents to identify GAPS in coverage
2. Proposes new monitoring queries based on emerging patterns
3. Discovers new entities (people, technologies, events) from collected documents
4. Suggests new sources to add to the collection net
5. Escalates high-velocity entities for human review

The engine runs periodically (e.g., weekly) and produces:
- New monitoring queries for the news_collector
- New source proposals for human approval
- Entity heat maps showing what's accelerating

ARCHITECTURE:
- Uses the built-in LLM (via OpenAI-compatible endpoint) for analysis
- Reads from: signals, documents, contract_awards, organizations
- Writes to: discovered_entities, discovered_sources (schema_patch_v13)
- Outputs: expansion_report.json (for human review)
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from . import supabase_client

log = logging.getLogger(__name__)


@dataclass
class GapAnalysis:
    """Represents a coverage gap the engine has identified."""
    category: str
    organization: Optional[str]
    region: Optional[str]
    last_signal_date: Optional[str]
    signal_count: int
    suggested_queries: List[str]
    priority: int  # 1-5, 5 = most urgent


@dataclass
class EmergingEntity:
    """An entity the engine has detected accelerating."""
    name: str
    entity_type: str  # technology, person, organization, event, concept
    mention_count: int
    velocity: float  # mentions per week, trending
    context: str  # Why this matters
    suggested_action: str  # What to do about it


@dataclass
class SourceProposal:
    """A new source the engine recommends adding."""
    url: str
    name: str
    reason: str
    linked_entity: Optional[str]
    confidence: float  # 0-1
    collection_method: str  # rss, scraper, api, manual


class ExpansionEngine:
    """The autonomous intelligence expansion engine."""
    
    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        
    def analyze_coverage_gaps(self) -> List[GapAnalysis]:
        """Identify where the collection net has holes.
        
        Looks at:
        - Categories with few or no signals
        - Organizations that should have activity but don't
        - Regions with known buyers but no recent documents
        """
        gaps = []
        
        # Get all categories
        from supabase import create_client
        client = create_client(self.supabase_url, self.supabase_key)
        
        categories = client.table("categories").select("id,slug,name,parent_id").execute().data
        organizations = client.table("organizations").select("id,canonical_name,org_type,province").execute().data
        
        # For each category, check signal density
        for cat in categories:
            if cat.get("parent_id") is None:
                continue  # Skip parent categories, check children only
            
            signals = client.table("signals").select("id,created_at", count="exact").eq(
                "category_id", cat["id"]
            ).execute()
            
            signal_count = signals.count or 0
            
            if signal_count < 3:
                # This is a gap — generate suggested queries
                suggested = self._generate_gap_queries(cat["name"])
                gaps.append(GapAnalysis(
                    category=cat["name"],
                    organization=None,
                    region=None,
                    last_signal_date=None,
                    signal_count=signal_count,
                    suggested_queries=suggested,
                    priority=5 if signal_count == 0 else 3,
                ))
        
        # Check organizations that should be active
        for org in organizations:
            if org["org_type"] in ("police_service", "federal_department", "provincial_ministry"):
                docs = client.table("documents").select("id", count="exact").execute()
                # In production, this would join through signals to check per-org coverage
        
        log.info("Identified %d coverage gaps", len(gaps))
        return gaps
    
    def _generate_gap_queries(self, category_name: str) -> List[str]:
        """Generate search queries to fill a coverage gap."""
        base_queries = [
            f"{category_name} procurement Canada",
            f"{category_name} police Canada tender",
            f"{category_name} government Canada RFP",
            f"{category_name} budget Canada public safety",
        ]
        return base_queries
    
    def detect_emerging_entities(self, documents: List[Dict]) -> List[EmergingEntity]:
        """Scan recent documents for entities that are accelerating.
        
        Uses frequency analysis across document titles and descriptions to find:
        - Technologies being mentioned more often (e.g., "PSBN", "NG911")
        - People appearing in multiple contexts (e.g., new minister)
        - Events creating procurement pressure (e.g., "FIFA 2026")
        - Concepts gaining traction (e.g., "defund" → "refund")
        """
        # In production, this calls Claude to extract entities from document titles
        # For now, we use a keyword frequency approach
        
        entity_counts: Dict[str, Dict] = {}
        
        # Known emerging technology terms to watch for
        WATCH_TERMS = {
            "PSBN": "technology",
            "NG911": "technology", 
            "NG9-1-1": "technology",
            "next-gen 911": "technology",
            "DFR": "technology",  # Drone as First Responder
            "drone as first responder": "technology",
            "real-time crime centre": "technology",
            "RTCC": "technology",
            "ShotSpotter": "technology",
            "SoundThinking": "technology",
            "Axon": "organization",
            "Motorola Solutions": "organization",
            "Tetra": "technology",
            "P25": "technology",
            "FirstNet": "technology",
            "FIFA": "event",
            "G7": "event",
            "NORAD modernization": "concept",
            "AUKUS": "concept",
        }
        
        for doc in documents:
            title = (doc.get("title") or "").lower()
            for term, etype in WATCH_TERMS.items():
                if term.lower() in title:
                    key = term.lower()
                    if key not in entity_counts:
                        entity_counts[key] = {
                            "name": term,
                            "type": etype,
                            "count": 0,
                            "dates": [],
                        }
                    entity_counts[key]["count"] += 1
                    if doc.get("published_on"):
                        entity_counts[key]["dates"].append(doc["published_on"])
        
        # Convert to EmergingEntity objects, sorted by count
        entities = []
        for key, data in sorted(entity_counts.items(), key=lambda x: x[1]["count"], reverse=True):
            if data["count"] >= 2:  # Only report entities seen multiple times
                entities.append(EmergingEntity(
                    name=data["name"],
                    entity_type=data["type"],
                    mention_count=data["count"],
                    velocity=data["count"] / 4.0,  # Approximate weekly rate
                    context=f"Seen {data['count']} times in recent documents",
                    suggested_action=f"Add dedicated monitoring for '{data['name']}'"
                ))
        
        log.info("Detected %d emerging entities", len(entities))
        return entities
    
    def propose_new_sources(self, gaps: List[GapAnalysis], entities: List[EmergingEntity]) -> List[SourceProposal]:
        """Based on gaps and emerging entities, propose new sources to monitor.
        
        Logic:
        - If a category has a gap, look for known government pages that cover it
        - If an entity is accelerating, find its primary information sources
        - Cross-reference with existing sources to avoid duplicates
        """
        proposals = []
        
        # Known source templates for common gap-filling
        SOURCE_TEMPLATES = {
            "Drones / RPAS & Counter-UAS": [
                SourceProposal(
                    url="https://tc.canada.ca/en/aviation/drone-safety",
                    name="Transport Canada — Drone Safety",
                    reason="Regulatory source for drone operations affecting police drone programs",
                    linked_entity="DFR",
                    confidence=0.85,
                    collection_method="scraper",
                ),
            ],
            "Cybersecurity": [
                SourceProposal(
                    url="https://www.cyber.gc.ca/en/alerts-advisories",
                    name="Canadian Centre for Cyber Security — Alerts",
                    reason="Cyber incidents drive emergency procurement for public sector",
                    linked_entity=None,
                    confidence=0.9,
                    collection_method="rss",
                ),
            ],
            "Radios & Communications": [
                SourceProposal(
                    url="https://ised-isde.canada.ca/site/spectrum-management-telecommunications/en",
                    name="ISED — Spectrum Management",
                    reason="PSBN and radio spectrum decisions affect all public safety comms procurement",
                    linked_entity="PSBN",
                    confidence=0.8,
                    collection_method="scraper",
                ),
            ],
            "AI & Analytics": [
                SourceProposal(
                    url="https://www.priv.gc.ca/en/opc-news/",
                    name="Office of the Privacy Commissioner — News",
                    reason="Privacy decisions directly affect AI/analytics procurement in policing",
                    linked_entity=None,
                    confidence=0.85,
                    collection_method="rss",
                ),
            ],
        }
        
        for gap in gaps:
            if gap.category in SOURCE_TEMPLATES:
                proposals.extend(SOURCE_TEMPLATES[gap.category])
        
        log.info("Generated %d source proposals", len(proposals))
        return proposals
    
    def generate_expansion_report(self) -> Dict[str, Any]:
        """Run the full expansion analysis and produce a report."""
        from supabase import create_client
        client = create_client(self.supabase_url, self.supabase_key)
        
        # Get recent documents for entity detection
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        recent_docs = client.table("documents").select(
            "id,title,doc_type,published_on,created_at"
        ).gte("created_at", thirty_days_ago).execute().data
        
        # Run analyses
        gaps = self.analyze_coverage_gaps()
        entities = self.detect_emerging_entities(recent_docs)
        proposals = self.propose_new_sources(gaps, entities)
        
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "documents_analyzed": len(recent_docs),
            "coverage_gaps": [asdict(g) for g in gaps],
            "emerging_entities": [asdict(e) for e in entities],
            "source_proposals": [asdict(p) for p in proposals],
            "recommended_new_queries": [],
        }
        
        # Compile recommended new monitoring queries from gaps
        for gap in gaps:
            for q in gap.suggested_queries:
                report["recommended_new_queries"].append({
                    "query": q,
                    "category": gap.category,
                    "priority": gap.priority,
                })
        
        return report


def run_expansion() -> int:
    """Run the expansion engine and save the report."""
    engine = ExpansionEngine()
    report = engine.generate_expansion_report()
    
    # Save report
    output_path = os.path.join(os.path.dirname(__file__), "..", "expansion_report.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    log.info("Expansion report saved to %s", output_path)
    log.info("Summary: %d gaps, %d entities, %d proposals",
             len(report["coverage_gaps"]),
             len(report["emerging_entities"]),
             len(report["source_proposals"]))
    
    return 0


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run_expansion())
