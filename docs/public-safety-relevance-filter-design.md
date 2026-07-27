# Public-safety relevance filter for regional-government feeds (operator 2026-07-27)

Status: BUILT and validated (2026-07-27). src/public_safety.py is the pure
predicate; the brief lens now gates on it; scripts/peel_public_safety_split.py
is the before/after report. The filter that makes the vertical-depth claim
true. GATE: this must land before the member portal goes live
(PORTAL_ENABLED flip), because a member seeing mostly watermains would
immediately doubt our public-safety depth.

## Validation result (measured over the live Peel corpus, 2026-07-27)

Ran scripts/peel_public_safety_split.py in CI against 1,262 resolved-to-Peel
signals. The split is clean and cuts on the right line:

- **Corpus split**: 668 public-safety / 594 general municipal.
- **Resolved org_type distribution**: municipality 647, police_service 388,
  police_board 227. The 615 police signals pass by org-type; ~53 more
  municipality-typed items pass on the keyword/facility fallback (fire/EMS
  text); the remaining 594 municipality items are correctly held.
- **NO fire_service / ems / emergency_management org_types exist** in the
  corpus: those services are DEPARTMENTS of the region, so they resolve to
  `municipality` and are caught by the keyword/facility fallback, not the
  org-type path. The org-type set lists them anyway (precision-safe) so a
  future resolver that types one gates by construction.
- **Precision confirmed on both sides**: HELD samples are all genuine general
  municipal (steam jennys, tree planting, sewage pump stations, Cisco
  networking, highway liners, LTC modifications); KEEP samples are all genuine
  public-safety (31 Division staffing, Hate Crime Unit, MCRRT crisis response,
  vehicle capital, FIFA 2026 deployment).
- **Member-facing published brief** (week 2026-07-20): 1 included item, the
  SOLGEN fire-protection grant, which survives (defence-tagged). The "24 items"
  the operator saw earlier were the OPERATOR-ALL RLS view (full corpus
  visibility), not the gated member set.

The lens leak is closed: a non-defence cluster now needs public-safety
relevance AND the materiality bar to default in, so a big general-municipal
item from a regional buyer is held rather than shipped on materiality alone.

## The problem (operator diagnosis, confirmed in code)

Regional governments (Region of Peel, and any region/large city) publish
police/fire/EMS/corrections tenders in the SAME feed as general municipal
procurement (watermains, road resurfacing, LTC supplies, SCADA). Today:

- **Signal layer**: the bids&tenders collector is keep-all, buyer-scoped
  (src/tenders_bidsandtenders.py:219 "Tag-only relevance: keep everything,
  mark defence_relevant if it matches"). For a regional buyer, buyer-scope
  is the whole region, not the public-safety slice. `buyer = "Region of
  Peel"` is not enough.
- **Brief lens**: apply_lens includes a cluster when `defence_relevant OR
  max_materiality >= 4` (src/brief_generator.py:236). The materiality
  branch is the leak: a $15M watermain (materiality 4-5) enters the draft
  for being big, not for being public-safety.
- **Member view today**: clean by composition-luck (this week's published
  brief has only the SOLGEN fire grant; watermains were held by the
  previously-featured lens), NOT by a robust filter. A future big
  non-police item would reach the member.

## The core need

A per-item PUBLIC-SAFETY RELEVANCE determination that isolates the
public-safety subset (police services + facilities, fire, EMS,
corrections, emergency management) from the general municipal procurement
that regional governments also publish. Broader than the existing
`defence_relevant` (dual-use tag); this is the whole vertical.

## Design (to build when approved)

### 1. Org-type-driven relevance (PRIMARY, reuses existing machinery)

The org resolver already resolves each signal's `organization_id` to the
END-USER, not just the buyer: a "12 Division renovation" tender under
Region of Peel can resolve to "Peel Regional Police". So:

> `public_safety_relevant := the resolved organization's org_type is a
> public-safety type` (police_service, police_board, fire_service, ems,
> corrections, emergency_management).

A Peel tender that resolves to Peel Regional Police -> relevant; one that
stays "Region of Peel" (general) -> not relevant. This leverages the
end-user detection we already do and is the cleanest gate. Requires: a
`public_safety` boolean (or an org_type membership set) on organizations,
human-confirmed like every org attribute.

### 2. Facility/keyword fallback (SECONDARY, catches construction-for-police)

The hard case: a generic CONSTRUCTION tender is public-safety-relevant
only if its end-user is a police/fire/corrections facility (12 Division,
fire hall, detention centre, paramedic station, 180 Derry). When org
resolution defaults to the general regional buyer, a title/description
detector flags relevance from public-safety facility markers: the existing
config/keywords.txt policing/corrections/fire/EMS terms PLUS facility
patterns ("N Division", "detention", "fire hall/station", "paramedic
station", known police addresses). Keyword-only is brittle (a "community
safety zone" road sign is not policing), so this is a fallback to org-type,
not the primary, and false-positive-prone matches stay defence_relevant=
tag-only rather than hard-included.

### 3. Buyer-type awareness (the structural rule)

Classify each buyer org as:
- **single-purpose public-safety** (a police service/board's own portal,
  e.g. a future London Police feed): keep-all is correct; everything they
  buy is public-safety by construction. No per-item filter.
- **multi-purpose** (Region of Peel, City of Toronto, any region/city):
  REQUIRE per-item public_safety_relevant. The buyer alone is insufficient.

This is the key insight: the relevance RULE depends on the buyer's
org_type. A per-buyer `is_multi_purpose` attribute drives which path runs.

### 4. Wire points

- **Brief lens**: replace the bare `max_materiality >= 4` branch with
  `public_safety_relevant AND max_materiality >= 4` for multi-purpose
  buyers, so a big watermain no longer passes for being big. Single-purpose
  buyers keep the current lens.
- **Member surface (Wave 3)**: the member vertical view (stage 2 data
  layer + optionally the RLS) gates on public_safety_relevant, so even a
  mis-composed brief cannot leak a general municipal item to the member.
  Defence in depth: fix the lens (composition) AND gate the member read.
- **Extraction**: the LLM already classifies; add the public_safety
  determination there (end-user org + facility detection) so the flag is
  set at signal creation, not recomputed.

## Validation (the go/no-go)

Re-run over the current Peel corpus: the 24 items should split into the
public-safety slice (12 Division renos, 180 Derry, arc-flash for police
facilities, the fire grant) vs the general slice (watermains, road
resurfacing, LTC supplies, SCADA, flow meters). If the split is clean, the
filter works; the member view then shows only the public-safety slice,
making the vertical-depth claim true.

## Gate

Blocks member portal go-live (PORTAL_ENABLED flip). Tracked as a task.
Not built now; scoped for operator approval.
