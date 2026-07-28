"""Public-safety relevance for regional-government feeds
(docs/public-safety-relevance-filter-design.md, operator 2026-07-27).

The truth-condition for the vertical-depth claim: regional governments
(Region of Peel, cities) publish police/fire/EMS/corrections tenders in the
SAME feed as general municipal procurement (watermains, roads, LTC supplies).
The buyer being "Region of Peel" is not enough; each ITEM needs its
public-safety relevance decided.

Two-part determination, precision over recall (a false include leaks a
watermain into a public-safety product, worse than a false exclude):

1. ORG-TYPE (primary): the signal's resolved END-USER organization is a
   public-safety org_type (police_service, police_board, corrections). The
   org resolver already resolves the end-user, so a "12 Division renovation"
   under Region of Peel that resolves to Peel Regional Police is caught here.
2. KEYWORD/FACILITY (fallback): when the end-user resolved to a multi-purpose
   buyer (a municipality/region/ministry) or did not resolve, the item's own
   title/description must name a public-safety service or facility. Reuses the
   config/keywords.txt public-safety terms plus facility patterns (police
   divisions, detention, fire hall, paramedic station).

Single-purpose public-safety buyers (a police service's own portal) pass
every item via org-type; multi-purpose buyers require the per-item test. This
IS the buyer-type awareness: the rule follows from the org_type, no separate
keep-all path needed.

Pure and unit-tested; no I/O. The brief lens and any member surface call
is_public_safety() to gate the member-facing default selection.
"""
import re

from .filters import Keywords, _word_pattern

# End-user org_types that ARE public-safety: any item whose resolved end-user
# is one of these is relevant by construction. police_service/police_board are
# the only public-safety org_types the corpus carries today (measured 2026-07-27
# over the Peel feed: municipality/police_service/police_board only); fire, EMS,
# and emergency management are DEPARTMENTS of a region/municipality, not
# separately-resolved orgs, so they are caught by the keyword/facility fallback.
# The unused types are listed anyway so that if the resolver ever types one, it
# gates by construction rather than depending on its title carrying a keyword.
# Every type here is public-safety by definition, so listing extras is
# precision-safe (it can never admit a general item).
PUBLIC_SAFETY_ORG_TYPES = frozenset(
    {"police_service", "police_board", "corrections",
     "fire_service", "ems", "emergency_management"})

# Buyer org_types that publish a MIX (general + public-safety), so an item
# resolving to one of these needs the per-item keyword/facility test.
MULTI_PURPOSE_ORG_TYPES = frozenset(
    {"municipality", "provincial_ministry", "federal_department"})

# Facility / service patterns the general keyword list does not already carry.
# Kept tight to avoid false positives (a "community safety zone" road sign is
# not policing; "fireproofing" is not a fire service). Police DIVISIONS are the
# key regional-feed tell ("12 Division", "22 Division renovation").
_FACILITY_PATTERNS = [
    re.compile(r"\b\d{1,2}\s+division\b", re.IGNORECASE),   # police divisions
    re.compile(r"\bdetention\b", re.IGNORECASE),
    re.compile(r"\bfire\s+(hall|station)\b", re.IGNORECASE),
    re.compile(r"\bpolice\s+(station|facility|headquarters|division)\b", re.IGNORECASE),
    re.compile(r"\bparamedic\s+station\b", re.IGNORECASE),
    re.compile(r"\bems\s+station\b", re.IGNORECASE),
]


def _keyword_hit(text: str, keywords: Keywords) -> bool:
    """WHOLE-WORD, case-insensitive keyword match. Substring matching put an
    Ottawa Transit "Bendix Air Brake Systems" tender on the public-safety
    homepage because 'ems' is inside 'Systems' (found 2026-07-27, the same
    class as the pilot's 'contracting' false positive). Word boundaries are
    mandatory anywhere the public-safety predicate feeds a member-facing or
    public surface."""
    if not text:
        return False
    # One matcher across the system (filters._word_pattern): whole-word
    # boundaries plus the 2026-07-28 plural tolerance, so this gate and the
    # collectors' keep/tag path can never disagree on what a keyword means.
    for kw in (*keywords.general, *keywords.defence):
        if kw and _word_pattern(kw).search(text):
            return True
    return False


def _facility_hit(text: str) -> bool:
    return any(p.search(text or "") for p in _FACILITY_PATTERNS)


def is_public_safety(org_type, title, keywords: Keywords,
                     description: str = "") -> bool:
    """True when the item is public-safety-relevant: its end-user org_type is a
    public-safety type, OR (fallback) its own text names a public-safety service
    or facility. `org_type` may be None (unresolved) -> fallback only."""
    if org_type in PUBLIC_SAFETY_ORG_TYPES:
        return True
    text = f"{title or ''} {description or ''}"
    return _keyword_hit(text, keywords) or _facility_hit(text)


def cluster_is_public_safety(members: list, keywords: Keywords) -> bool:
    """A cluster is public-safety-relevant if ANY member is. `members` are
    signal dicts carrying `title`, `defence_relevant`, and the resolved
    end-user `org_type` (added to the brief query). A defence_relevant member
    is public-safety by definition (dual-use is a subset)."""
    for s in members:
        if s.get("defence_relevant"):
            return True
        if is_public_safety(s.get("org_type"), s.get("title"), keywords,
                            s.get("description", "")):
            return True
    return False
