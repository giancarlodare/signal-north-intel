# Demand-voice layer — design (operator 2026-08-02; design only, no build)

The gap this closes: everything we collect is the formal record, inside an
administrative process. Nothing captures what is being CALLED FOR, upstream
of a business case. The worked example: public calls for drone-as-first-
responder capability after the Toronto consulate shooting — months ahead of
any procurement document, exactly what a vendor sells against, invisible to
the corpus. A tender means the subscriber is already late; this layer is
where they are early.

## The design's spine: weight by who is asking

Ordering by evidentiary weight is the whole design. Proposed `asker_weight`
dimension on this layer's signals (parallel to, never mixed with,
evidence_grade, which stays a claim about the procurement record):

| weight | asker | examples |
|---|---|---|
| 5 | Institutional ask, accountable author, response expected | Coroner's inquest recommendation; OCPC direction; AG Ontario VFM recommendation; public inquiry |
| 4 | Sector association, on the record | OACP / OAFC / PAO / OAPC pre-budget submission or position paper |
| 3 | Named official of a service | chief's public statement, service release, deputation BY a service |
| 2 | Trade/vendor press | Blue Line, Vanguard, vendor Canadian-entry announcements |
| 1 | Ambient | local incident-and-reaction coverage, residents quoted |

Weight 1 is CONTEXT: collected, linkable, never surfaced as a standalone
item. A resident quoted in an article is atmosphere; a jury addressing the
Solicitor General by name is a signal.

## Sources (ranked, with collection posture)

Layer members, robots verdicts from the coverage probe run (see the
coverage report for the measured table):

1. **Coroner's inquest recommendations** (ontario.ca, verdicts-and-
   recommendations pages). Public, dated, addressed to named services with
   expectation of response. Strongest single source; publishes continuously
   at low volume. The RESPONSES (services answering the jury) are
   themselves commitment-grade material.
2. **Pre-budget submissions** (OACP, OAFC, PAO, OAPC; provincial and
   municipal). Annual, literally a list of asks.
3. **Association position papers / statements** (same four sites).
4. **OCPC reports; AG Ontario VFM audits** touching policing/fire/EMS;
   public inquiry recommendations.
5. **Council delegations/deputations** on public-safety items — reached by
   the council-agenda adapter (keystone), zero extra collection here.
6. **Chiefs' and services' own releases** — service newsrooms/RSS.
7. **Trade press** (Blue Line, Canadian Firefighter, Canadian Security,
   Canadian Defence Review, Vanguard, Esprit de Corps) — RSS only.
8. **Vendor announcements** — doubles as the foreign-entrant feed for the
   commercial pipeline.
9. **Local news** — weight 1, context only.

## Copyright and robots, non-negotiable

RSS or explicitly permitted feeds only. We store metadata (title, date,
link, source, asker classification) and never reproduce article text on a
member-facing surface; the member reads the publisher, we point. Any site
whose robots or terms forbid collection is reported as a coverage boundary
on the coverage page, not worked around. (CanLII precedent applies.)

## Surfacing: labelled, never blended

A demand-voice item is a different CLAIM from a procurement item: "this is
being asked for" vs "this is being procured." Distinct doc types
(`inquest_recommendation`, `prebudget_submission`, `position_paper`,
`demand_press`), a distinct visual register in the brief, and the asker
weight shown. It never enters the procurement ranking.

## How it scores without swamping the brief

This layer will out-volume everything else we collect. Three containments:

1. **Its own section, fixed budget.** The brief structure the operator
   named: *pressure → money → ask → purchase* (what's being called for,
   what grants are open, what services are formally asking for, what's
   being procured). Each section has its own selection; demand-voice items
   compete only with each other for a capped number of slots.
2. **Weight floor for surfacing.** Weight >= 4 defaults into the brief;
   weight 3 needs a corroborating item (a second asker or a matching grant/
   budget line); weights 1-2 surface only as context links attached to a
   stronger item, never standalone.
3. **Arc composition upgrade.** The demand arc gains a rung BELOW intent:
   `called_for` (rung 1 in taxonomy terms is 'chatter'; an inquest
   recommendation is chatter with an accountable author, so the arc can
   begin at a jury's ask and end at an award). This is what makes
   "pressure -> purchase" one composable story rather than two lists.

## Costs (collect-only)

RSS polling + inquest/association page checks: tens of items/day at peak,
KBs each (metadata only). Storage negligible. No LLM at collection; asker
classification is deterministic from source (the source IS the asker class
for 1-4; only weight-3 statements need any judgment, deferrable to the
extraction budget later, gated as usual).

## Build order (when approved)

1. Coroner inquests + AG Ontario + OCPC (highest weight, lowest volume,
   plain document pages).
2. Association sites x4 (pre-budget season is annual; position papers
   trickle).
3. Trade press RSS (six feeds).
4. Vendor announcements (rides discovery + trade press initially).
Council deputations arrive free with the council-agenda adapter. Local news
already partially exists via Google News coverage monitor, re-labelled
weight 1.

Gated: everything above is a new-source build; nothing collects until the
operator approves this design.

## Addendum (operator 2026-08-02, same day)

**Coroner's inquest documents confirmed top priority.** Scope includes the
verdicts, the jury recommendations, and the published RESPONSES from named
services and ministries. Where the Office of the Chief Coroner publishes
and the archive depth are on the coverage probe / operator worklist.

**University research as a forward signal.** Not a literature sweep:
CIPSRT (public-safety personnel), Rescu and Sunnybrook Prehospital
Medicine (EMS), TMU / U of T Criminology / Ontario Tech / Western
(policing), DRDC (defence, connects to IDEaS), and the SSHRC + CIHR award
databases — a funded project says what is being studied years before
findings publish. Award databases are structured downloads (ledger-shaped,
like Sunshine).

**News catalogue is enumerated, not sampled** — tiers: trade press (adds
Fire Fighting in Canada, Canadian Paramedicine), national (CBC, CTV,
Global, CP, Globe, Post), provincial/Queen's Park (TVO, QP Briefing,
iPolitics), regional dailies one per fleet market, hyperlocal networks
(Village Media, Metroland) which cover councils nobody else does, and
international trend-leaders (Police1, GovTech, Route Fifty, Defense News,
Breaking Defense, Shephard). Robots/feed verdicts per source come from the
coverage probe; paywalled/disallowing dailies are coverage boundaries.

**Filtering architecture (the actual design problem).** NO keyword
keep-filter on news — the sewer-CCTV lesson, and news is noisier than
tenders. Three layers: (1) source-level curation and weighting, which does
most of the work before anything is read; (2) a cheap-model relevance
CLASSIFIER, scoped together with the extraction cascade — the cascade is
what makes this layer affordable at all; (3) author-authority weighting as
already ruled. Classifier cost is estimated in the catalogue table
delivered with the coverage report.

**Association layer — its own source class, previously absent entirely.**
Chiefs/command (CACP, OACP + provincial equivalents, CAFC, OAFC, PCC,
OAPC), labour (CPA, PAO, OPPA, TPA and large locals, OPFFA/IAFF, CUPE and
OPSEU paramedic locals), governance (CAPG, OAPSB — boards are where the
best arcs already come from), municipal lobbying (AMO, ROMA, Ontario Big
City Mayors, MARCO, FCM), training/standards (CPKN, OPC, CPC, OFC, JIBC),
oversight/adjacent (CACOLE, CANASA, CADSI). Collected per body:
submissions and briefs, position papers, resolutions, media releases,
annual reports, and conference programmes + exhibitor lists (the last
flagged COMMERCIAL, for the operator's pipeline, not the product).

**The scope rule, designed in rather than assumed:** the advocacy layer is
collected NATIONALLY (cheap, and national bodies shape provincial asks);
procurement coverage claims stay ONTARIO + FEDERAL. The data model carries
the distinction (advocacy sources tagged `claim_scope='advocacy-national'`
vs procurement `claim_scope='procurement-on-fed'`) and the coverage page
states both claims separately, so collecting a CACP submission can never
imply national procurement coverage.

## Second batch of source classes (operator 2026-08-02, later the same day)

Assessed in the coverage probe (`new-classes` roster) and assigned here by
shape. Design first, no build, per the instruction.

**The four prioritised:**

1. **Community Safety and Well-Being Plans** — mandatory for all 444
   Ontario municipalities, all public: a demand document by legislative
   mandate, currently untouched. No single portal exists; the plans live on
   municipal sites and in council agendas, so this class RIDES the
   council-agenda/municipal adapter (keystone) plus a one-time enumeration
   pass, rather than a new collector. Volume ~444 documents plus revision
   cycles; multi-year freshness; storage trivial. Weight-5-adjacent in this
   layer's terms: an accountable institutional statement of local need.
2. **TB proactive disclosure of contracts over $10k** — partially covered
   ALREADY: our six federal contract-award feeds ride exactly this rail
   (search.open.canada.ca/contracts). The ask is a widening: the all-
   department bulk dataset (quarterly structured CSV) through the existing
   CSV-ingest adapter. Feeds the prospect universe directly. Ledger-shaped;
   quarterly; lag one quarter.
3. **CITT decisions** — bid-protest rulings exposing how contracts were
   actually decided. Low volume, high value, continuous publication;
   nothing else in the record shows evaluation mechanics.
4. **VOR / standing-offer lists** — who is pre-qualified to sell to whom.
   Ontario VOR directory (public page layer; the intranet VOR detail is
   robots-DISALLOWED per the July probe and stays a boundary); federal
   standing offers ride CanadaBuys data we already collect.

**Police:** Inspectorate of Policing inspections (new under CSPA); SIU and
LECA reports; statutory service strategic/business plans (the police
equivalent of a fire master plan — rides the board/service adapter, and
the board seeding just approved reaches most of them).

**Fire:** Fire Underwriters Survey grading — NOTE: FUS is a private
insurance-industry body and its gradings may not be public; if so, that is
a boundary stated plainly, not a scrape target. NFPA standards updates
(cycle-setters; track update announcements, standards text is paywalled
and stays unreproduced). Inter-municipal fire protection agreements — in
council agendas, rides the keystone adapter.

**EMS:** Ornge — its own aircraft/equipment procurement, absent from the
roster until now. Regional base hospital programs (medical-direction
standards that drive purchases) — enumeration belongs on the operator
worklist with the coverage rows.

**Defence:** Canadian Commercial Corporation; ISED ITB obligations
database (who owes offsets — published, structured); National
Shipbuilding Strategy documents (canada.ca); NATO NSPA (where Canadian
firms bid; international host, robots verdict from the probe).

**Vendors:** individual company newsrooms as first-class feeds (per-vendor
RSS, rides the trade-press collector shape); SEDAR+ and SEC EDGAR filings
— public vendors disclose Canadian wins before anyone reports them. EDGAR
is public-domain with a documented API; SEDAR+ terms need reading before
any collection and may be a boundary.

**Council:** COMMITTEE minutes are first-class in the council-agenda
design, not an afterthought — budget and protective-services committees
are where the discussion happens; council ratifies. (Carried into the
council-agenda design doc as a requirement.)

**Provincial:** Ontario Regulatory Registry — proposed regulations posted
for comment before law; pure forward signal, low volume, continuous.
Confirmed a FEED, not a scrape: ontariocanada.com/registry (also
regulatoryregistry.gov.on.ca) publishes RSS plus email alerts. The
Environmental Registry (ero.ontario.ca) is a separate system to assess.

## Worklist resolutions folded in (operator 2026-08-02, evening)

**Inspectorate of Policing is TOP-TIER demand-voice**, not merely an
oversight row: iopontario.ca publishes inspection reports, Spotlight
Reports, annual reports, and the Policing Insight Statement — a survey of
every Ontario chief and board. Weight 5 in this layer's terms.

**OPFFA** (ontariofirefighters.org, UnionActive platform) carries two
demand-voice assets beyond releases: an annual legislative conference at
Queen's Park (a demand-voice event in itself) and Section 21 /
cancer-prevention material tying directly to the fire decontamination
procurement driver.

**Rescu -> CanROC.** rescu.cc (St. Michael's, 24 hospitals across Southern
Ontario) has evolved into CanROC, a national resuscitation-sciences network
with sustained Heart and Stroke funding; CanROC is the better entity to
track for EMS research.

**FNCPA** (First Nations Chiefs of Police Association) exists as an
organisation — it holds a CACP board seat — and joins the chiefs layer.

**First Nations policing route-in correction.** FN services procure through
tripartite agreements under the federal First Nations Policing Policy
(Public Safety Canada FNIPP, ~52/48 federal/provincial), not municipal
budgets. Their own sites showing little is expected, not a boundary
verdict; assess the FEDERAL funding and agreement layer as the route in.
Scale: Anishinabek Police alone runs 109 sworn officers across 12
detachments; NAPS is larger. Real buyers.

**Transition-review status class.** A municipality studying OPP costing or
transition is a tracked coverage status (probe TRANSITION_REVIEW), not a
discovery-by-search. First member: Sarnia (council motion under debate,
2026-08) — also our only robots-DISALLOW roster host, so the one service we
cannot collect from may be about to stop being a buyer. The Sarnia story is
itself a demand arc: council motion -> costing study -> OCPC application ->
transition, with procurement consequences at both ends.
