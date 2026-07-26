# Federal House of Commons Hansard collector: design (design-first)

Status: PROPOSED (design-first, 2026-07-26; operator request folding federal
Hansard into the upstream-intent legislative layer). NOT built; probe-first
before the build, propose-then-approve before any enablement. The Ontario
collector (docs/hansard-design.md, src/hansard.py) is the pattern; this is
the federal equivalent one level up.

## 1. Why

Federal public-safety and defence procurement intent surfaces in committee
long before CanadaBuys: SECU and SECD estimates exchanges, minister
statements, and committee reports precede budget lines and RFPs by months.
The federal corpus already carries the DOWNSTREAM (CanadaBuys tenders,
federal contract awards, federal grant awards), so the legislative layer
closes the federal arc the same way Ontario Hansard closes the provincial
one.

## 2. Targets (narrow and high-value, not the firehose)

Priority order (operator 2026-07-26):

1. **SECU** (Standing Committee on Public Safety and National Security):
   evidence/transcripts and reports, the federal public-safety intent vein.
2. **SECD** (Standing Senate Committee on National Security, Defence and
   Veterans Affairs): the defence-procurement intent vein.
3. House Hansard daily debates, scope-filtered (public-safety / defence /
   procurement terms) exactly like the Ontario scope filter.
4. LEGISinfo bill tracking for public-safety/defence bills (banked within
   this design; a bill's progress is legislative_change signal).

## 3. Surfaces to probe (read-only, before the build)

- `ourcommons.ca`: committee pages (Evidence, Reports) for SECU; Hansard
  daily debates (Publication Search / sitting-day pages). Known to publish
  XML/HTML publications; the probe confirms server-side collectability,
  robots posture, URL shapes, and date fields.
- `sencanada.ca`: SECD transcripts (Senate committees publish evidence
  pages).
- `parl.ca` / LEGISinfo: bill-status pages (JSON API exists; probe confirms).

The probe reports per surface: robots, server-side vs JS, dated-URL shape,
and whether committee evidence is enumerable from a publisher index (the
ola.org pattern). Build proceeds only on surfaces that pass.

## 4. Collector shape (conditional on the probe)

`src/hansard_federal.py` on the Ontario pattern: publisher-indexed discovery
(committee evidence lists first, then scoped daily Hansard), per-run NEW cap,
content_hash(url, doc_type), scope filter AHEAD of storage (public-safety /
defence / procurement terms tuned federally: RCMP, CBSA, CSC, DND, CAF,
procurement, capital), published_on from the sitting date at day precision
(never fabricated), loud-fail on a zero-item committee index. Reuses the
`legislative_debate` doc_type (same enum value; jurisdiction on the source
row distinguishes federal). One URL-guarded sources row per chamber surface.

## 5. Validation + enablement

CI validation dry-run with the standard bars (>= 90% date parse on kept docs,
scope filter keeping a sane fraction, nonzero bodies, projected per-run
extraction volume) and the single-go gate before enabling. Extraction budget
restated at the Aug 4 checkpoint alongside the Ontario Hansard number.

## 6. Sequencing

Runs behind the Ontario Hansard build in the upstream-intent sequence
(docs/upstream-intent-scale-design.md section 7): Ontario proves the
legislative-layer pattern end-to-end (collector, scope filter, extraction,
brief rendering) before the federal build spends its probe.
