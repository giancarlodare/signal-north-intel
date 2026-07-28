# MERX breadth: the provincial agency layer (design)

Status: DESIGN, awaiting operator approval. Nothing is built.
Program: coverage program, provincial front (operator go 2026-07-28 on the
three legitimate routes; this is route 1). Evidence base: passes 7-8 in
docs/opp-provincial-procurement-design.md.

## What this covers, and what it honestly does not

Ontario's standalone agencies, crown corporations, and transit bodies own
their procurement and post it publicly on MERX, whose robots.txt explicitly
welcomes well-behaved crawlers (CI-verified when the Ottawa collector was
built). Pass 7 confirmed live public buyer pages for Metrolinx,
Infrastructure Ontario, and the City of Toronto, and confirmed OEB's own
public-tenders page links every item to a public MERX detail page,
including security-relevant work (threat-risk assessment upgrades, access
card and detection systems). Current opportunities AND awarded history are
both exposed, so this feeds arc reconstruction as well as forward coverage.

NOT covered by this design and stated on the coverage map as a disclosed
boundary: direct ministry and OPP OPERATIONAL solicitations, which live on
the robots-forbidden Ontario Tenders Portal. OPP's CAPITAL arc is expected
to flow through Infrastructure Ontario on MERX (IO builds and renovates
OPP facilities); step 1 verifies that empirically instead of asserting it.

## Step 1, the two OPP checks (probe, before anything else)

1. Enumerate the Infrastructure Ontario buyer page (open + awarded tabs)
   and count OPP-named projects, with samples. This turns "OPP capital via
   IO" from inference into evidence, or kills it honestly.
2. Search the MERX public cross-buyer open-solicitations list for
   "Ontario Provincial Police" as a named buyer or entity, to confirm
   there is no direct OPP presence being assumed away.

Step 1 also enumerates candidate buyer slugs from the public list (the
LCBO and UofT guesses 404ed; real slugs are discoverable, not guessable).

## Collector shape

`src/tenders_merx.py` already implements the per-buyer-page pattern for
Ottawa (tabbed listing walk, per-tab pagination via the listing's own Next
link, per-run NEW-item caps, loud failure on empty tabs, content-hash
dedupe, robots re-check per run). Breadth is a ROSTER extension of that
collector, not a new engine:

* BUYERS list gains entries: {slug, name, org_key}, starting roster OEB,
  Metrolinx, Infrastructure Ontario; more added per-buyer as they clear
  the gates below.
* Buyer attribution: the buyer page IS the buyer, same as Ottawa; org
  resolution via ORG_SEED entries per buyer.
* IO nuance: IO posts on behalf of end users (hospitals, OPP, courts), so
  IO items keep IO as buyer_name and the end user surfaces through
  extraction, same as CanadaBuys end-user handling.

## Gates, per buyer (nothing enables in bulk)

1. PROVENANCE: the buyer's own official site must link its MERX presence
   (OEB's public-tenders page does this literally; Metrolinx and IO
   doing-business pages checked in step 1). Recorded per buyer.
2. VALIDATION BARS: CI dry-run per buyer: non-zero open rows, reference
   and date parse rates at the tier-1 bars, awarded tab present and
   parsing. Diagnose-and-extend on any miss, never enable-and-hope.
3. OPERATOR GO + seed paste per buyer (URL-keyed, idempotent), exactly the
   tier-2/tier-3 ritual.

## Self-maintenance and cost

Enabled buyers join the existing MERX step in daily-collect (the Ottawa
collector already runs there), so the source self-maintains. Collection is
requests-only, 2s politeness, no LLM. Forward extraction rides the capped
daily pass. AWARDED HISTORY DRAINS ARE COST-GATED: each buyer's awarded
backlog is sized in the validation run and comes to the operator as a
measured envelope before any drain; nothing spends silently.

## Deliverables on approval

1. Step-1 probe run and its report (OPP checks + slug discovery).
2. Roster + ORG_SEED extension with per-buyer provenance notes.
3. Per-buyer CI validation dry-runs, bars reported.
4. Paste-ready source seed migration for the buyers that clear.
5. Coverage map update wording for the operator's approval, claiming only
   what validated.
