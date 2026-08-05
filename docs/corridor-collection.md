# Corridor Intelligence — collection scope (operator 2026-08-05)

Second vertical: GTA construction/development procurement. Buyers: road
builders, sewer/watermain contractors, aggregates producers, GCs, developers.
Build Aug 17-30 alongside the grant writer; COLLECTION ON NOW because archives
cannot be backfilled. **Collect-only: no extraction, no product surfaces,
nothing displaces the fortnight queue.**

## 1. Keep-filter: construction term pack (LIVE)

The tender collectors' keep-filter was discarding civil-works documents at
collection -- noise for public safety, THE SIGNAL for Corridor, and permanent
loss on portals already visited daily. Landed 2026-08-05:

* `config/keywords.txt` gains a `# ---CONSTRUCTION---` section (operator's
  term pack + the §2 document classes). Bare "EA" held out (the bare-'rms'
  precedent: it matches "$5 ea."); the spelled-out forms carry it.
* Term pack over capture-all, deliberately: capture-all keeps rows matching
  NO pack (janitorial, insurance) that can never be domain-attributed, and
  Corridor's own ruling is that domain stays a dimension. The pack keeps the
  dimension mechanical (`construction_relevant` at collection) and the keep
  provenance recorded (`matched_keyword`). Missing-term recall is a
  one-line, versioned addition.
* **Extraction isolation (operator requirement, same day):** a construction-
  ONLY keep inserts as `status='captured_construction'`
  (`src/filters.py document_status`). The daily forward pass and
  extract-backfill both select exact `status='captured'`, verified as the
  only extraction selectors -- so the expensive morning cannot grow. A
  document matching BOTH core and construction packs stays on the core
  pipeline byte-identically. Corridor extraction later targets the held
  status under its own envelope. No migration: documents.status is
  unconstrained text (the 2026-07-09 'irrelevant' quarantine precedent).
* Storage delta: immaterial on the daily forward pass (rough order: a few
  hundred docs of first-pass backlog across the portals, then tens/day, at
  2-10 KB each -> single-digit MB/month). The MATERIAL case is awarded-
  HISTORY drains (Peel shows 2,779 awarded rows, York 2,654): under
  construction keeps those would grow multi-fold, and they remain dispatched,
  envelope-gated batches -- unchanged by this.

## 2. Council-agenda document classes (keep-side LIVE; classifier queued)

Demand-plan document classes, same pattern as fire master plans / CSWB:
asset management plans (O.Reg 588/17 -- mandatory for every Ontario
municipality, 10-year capital forecasts), water/wastewater master plans,
transportation master plans, development charges background studies, capital
budget documents. Their terms are in the construction pack now (keep-side);
the council-agenda adapter/classifier treatment rides the eScribe adapter
build.

## 3. Sources to probe (usual table: robots verdict, adapter fit, volume)

* Development application / site-plan registries: Toronto Application
  Information Centre + 905 equivalents.
* Ontario Land Tribunal decisions (approvals unlock servicing and roads).
* MTO capital program and contract awards.
* ERO -- already verified ALLOW: wire EA notices as a feed (build task, this
  is the one pre-cleared source).
* Trade press (demand-voice layer): Daily Commercial News (ConstructConnect),
  On-Site, ReNew Canada.
* Association layer (rides the demand-voice design): TARBA, ORBA, OSWCA,
  OSSGA, RCCAO pre-budget submissions and position papers.

## 4. Binding data-model rule: design→construction chain

The design-award → construction-tender linkage stays queryable as a chain per
buyer and asset class. The engineering-award-precedes-construction-tender
interval is Corridor's core arc and best product claim, derivable only if the
chain survives -- which is why the term pack includes the design-side terms
(engineering design services, consulting engineering, EA, detail design,
contract administration): both ends of the chain are captured from day one.
Unit-price extraction from awards (cost per metre of watermain, per lane-km)
is a later, envelope-gated decision. Collect, don't extract.

## 5. Domain stays a dimension

Construction is the FOURTH domain alongside police/fire/EMS/defence in the
categorization design, not a fork -- same ruling as before, now load-bearing
since this vertical launches from the same corpus. The
`construction_relevant` flag at collection is that dimension's first
mechanical expression.
