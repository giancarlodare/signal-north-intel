# Thin adjacent collection: allied munitions and industrial capacity

Status: **DESIGN SCOPE ONLY. Nothing probed, nothing built, nothing runs.**
Operator instruction 2026-07-28: scope the shape and the cost so the
decision can be made on numbers. This work sits BEHIND Signal North's
launch in priority and does not compete with it.

## 1. Why this is a "now or never cheaply" question

Archives cannot be built retroactively. A public tender notice, award, or
capacity announcement is reliably retrievable while it is current and
unreliably retrievable a year later: portals roll their windows, agencies
re-platform, and "past" tabs are the first thing to disappear. Collection
is also the CHEAP half of this stack. The expensive half is extraction, and
extraction can be deferred indefinitely over a corpus we already hold.

So the proposition is narrow: **start the clock on an archive now, process
it never (until there is a reason).**

## 2. What "thin" means precisely

Thin = **collect-only**. Explicitly excluded:
* no LLM extraction (this is the entire cost driver: measured $0.019 to
  $0.024 per document on our own corpus)
* no signal generation, no grading, no clustering
* no product surface, no member visibility, no RLS exposure
* no entity resolution beyond storing the publisher's raw name string

Included:
* the document record: publisher URL, title, dates with precision,
  reference number, source, jurisdiction, content hash for dedupe
* optionally the body text, capped (this is the storage decision, section 5)

The corpus sits inert. If a vertical is ever launched, the archive is
already deep; if it never is, we have spent storage and nothing else.

## 3. Candidate source landscape

**EVERY LINE BELOW IS UNVERIFIED.** I have not probed any of these hosts.
Reachability, robots posture, API terms, structure, volume, and licensing
are exactly what a probe round would establish, and nothing here should be
treated as a finding. Listing them is scoping, not evidence.

### 3a. Canada (highest overlap with what we already run)
| Candidate | Note | Status |
|---|---|---|
| CanadaBuys tender + award feeds | ALREADY COLLECTED for Signal North. A munitions/industrial slice may be a keyword scope change, not a new collector. Cheapest possible start. | in production, re-scopeable |
| Federal contract + grant award datastores (open.canada.ca) | ALREADY COLLECTED, department-scoped. Adding industrial departments is config. | in production, re-scopeable |
| Industrial and Technological Benefits / offset policy postings | Publisher and structure unknown | UNVERIFIED |
| Canadian Commercial Corporation announcements | Publisher and structure unknown | UNVERIFIED |
| Provincial industrial/mining registries | Highly heterogeneous | UNVERIFIED |

### 3b. Allied public procurement record
| Candidate | Expected shape | Status |
|---|---|---|
| US federal contract opportunities portal | public API expected | UNVERIFIED (robots + API terms) |
| US federal spending transaction data | bulk API expected, very high volume | UNVERIFIED |
| US DoD daily contract announcements | HTML newsroom, low volume, high signal | UNVERIFIED |
| UK Contracts Finder / Find a Tender | public API expected | UNVERIFIED |
| EU Tenders Electronic Daily | bulk data expected, very high volume | UNVERIFIED |
| NATO support and procurement agency notices | HTML expected | UNVERIFIED |
| Australia AusTender | HTML/API unknown | UNVERIFIED |

### 3c. Industrial capacity (not procurement)
| Candidate | Expected shape | Status |
|---|---|---|
| Corporate disclosure filings (CA/US regulators) | bulk archives expected, large | UNVERIFIED |
| Prime and tier-1 supplier newsrooms | RSS, our existing collector pattern | UNVERIFIED |
| Plant/facility investment announcements (govt economic-development newsrooms) | RSS/HTML, our existing pattern | UNVERIFIED |
| Export control / permit publications | unknown, likely restricted | UNVERIFIED |

**A doctrine note that applies specially here:** several of these are APIs
with TERMS OF USE, not just robots. For an API, the terms are the gate that
robots is for a website: registration requirements, rate limits,
redistribution restrictions, and attribution obligations must be read and
honored before a single call. A probe round must answer "what do the terms
permit" alongside "what does robots say." Bulk data being technically
downloadable is not permission.

## 4. What a probe round would cost and answer

One CI probe round, on the existing throwaway-branch pattern: read
robots.txt verbatim per host, read the published terms, fetch one page or
one API response, and report structure, volume indicators, and date
coverage. Read-only, no storage, no extraction.

Cost: **runner minutes only, effectively $0** (this repository is public,
so GitHub Actions minutes are unmetered). Effort: roughly one working
session per 4 to 6 hosts.

Output: a verdict table per host of the same kind Signal North uses today
(permitted / walled / needs-relationship), plus measured volume, which is
the input the storage model below actually needs.

## 5. Cost model (the decision-useful part)

Runtime and storage are cheap; the deferred processing liability is not.

**Runtime: ~$0.** Public repository, so Actions minutes are unmetered.
API-and-RSS collection needs no browser rendering, so an adjacent daily
pass is minutes, not the ~40 minutes our rendered municipal fleet takes.

**Storage, measured against our own row shapes:**
* metadata-only row: ~1.5 KB
* with body text at the tender cap (20 KB): ~20 KB
* with body text at the document cap (400 KB): only for rich documents,
  rare in this slice

| Annual volume (scoped) | Metadata only | With capped bodies |
|---|---|---|
| 50,000 docs | ~75 MB/yr | ~1 GB/yr |
| 150,000 docs | ~225 MB/yr | ~3 GB/yr |
| 500,000 docs (unscoped bulk) | ~750 MB/yr | ~10 GB/yr |

Managed Postgres pricing puts the metadata-only cases inside a single
low-tier plan indefinitely; capped bodies at high volume is where a storage
tier decision actually appears. **Recommendation: metadata-only by default,
bodies only for sources whose body IS the signal** (contract announcements,
newsroom items), which keeps the archive in the tens-to-low-hundreds of MB
per year.

**The deferred liability, stated plainly:** at our measured extraction rate
of ~$0.02/document, an archive of 150,000 documents represents roughly
**$3,000 of future extraction cost** if it were ever fully processed. That
is the real number behind "collect now, extract later." It is not a cost we
incur by collecting, but it is the cost we are optioning, and it should be
sized before the archive grows past the point where full processing stops
being an affordable choice. Scoped collection keeps that option cheap;
unscoped bulk collection quietly buys a $10,000+ future decision.

## 6. Shape requirement (ties to the generic entity model)

If this is ever built, it must not create a second parallel schema. It uses
the SAME `sources` / `documents` spine, distinguished by source rows and a
vertical tag, with no new public-safety-shaped or munitions-shaped tables.
Any new entity beyond organizations (facility, firm, input, program) enters
as a generic entity + relationship + sourced claim, per
`docs/generic-entity-model.md` (to be written when a second vertical is
real), never as a bespoke table.

This is the cheap-now-expensive-later property the operator named: the
adjacent archive is precisely the thing that would tempt a bespoke schema,
and precisely the thing that must not have one.

## 7. Decision points for the operator (nothing proceeds without these)

* **D1.** Probe round yes/no, and if yes, which 4 to 6 hosts first.
  Recommendation: start with the two that are ALREADY collectors
  (CanadaBuys scope change, federal datastores department change), because
  they cost nothing new and prove the shape.
* **D2.** Metadata-only vs capped bodies (recommendation: metadata-only,
  bodies only where the body is the signal).
* **D3.** Scoped-by-keyword vs unscoped bulk (recommendation: scoped; see
  the deferred-liability math).
* **D4.** Priority position. Recommendation and current standing
  instruction: BEHIND Signal North launch, revisited after September.

## 8. ADDENDUM — NATO 2026 Summit outputs (operator, 2026-08-05)

Collect-only, same disciplines, nothing jumps the fortnight queue. Context:
the Ankara summit launched a "Call to Action" directing private financial
institutions into defence investment, alongside the first PUBLIC NATO
Aggregated Demand Signal -- a structured statement of Allied capability
needs published specifically so capital can underwrite against it. BDC is
among the named institutions, which makes the Canadian response a live
thread. Strategically this validates the thesis (demand signals must be
legible before money moves) and points at a future CAPITAL-MARKETS reader
of the corpus. Collection choices preserve that option; nothing is built
for it now.

**New candidate sources (UNVERIFIED, same standing as section 3 -- robots
posture, structure, licensing all unprobed; they enter the same probe round
D1 governs, at queue position, never ahead of it):**

1. **NATO Aggregated Demand Signal (public version)** -- as a document
   class with REVISIONS TRACKED: each published revision is a fresh dated
   document, never an overwrite. It is the alliance-level analogue of our
   demand arcs.
2. **NATO Innovation Scale-Up Package materials** (2026 summit), including
   the NATO Engine and Drone Edge announcements -- capability-direction
   signals.
3. **BDC defence/security investment announcements** -- the Canadian
   institution named in the Call to Action; program structure and
   commitments are the domestic trace of the initiative.

**Priority bump, no scope change:** the ITB/offset obligations database,
Defence Investment Plan, Estimates, and ACAN/RFI recovery now serve TWO
readers -- the vendor reader we built for and the lender who would price
against them. Their queue positions are unchanged; their value is not.

**Data-model constraint (binding, costs nothing today):** where a defence
contract's full history is held (award, options exercised, extensions,
value changes), the chain stays QUERYABLE AS A CHAIN. The current federal
ingest already satisfies this -- `contracts_federal.py` writes the
procurement_id into indexed `documents.reference_number`, and its identity
rule (reference + value) inserts a re-disclosed amendment as a fresh dated
document while the original stays, with original_value / amendment_value
captured -- so the revenue trajectory is derivable by grouping on
reference_number in disclosure order. That behavior is now LOAD-BEARING:
re-disclosures are never collapsed into updates, and reference_number
remains the chain key. A contract's revenue trajectory over time is the
credit signal a capital reader would pay for.
