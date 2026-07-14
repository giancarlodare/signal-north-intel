# Board-Minutes Award Mining: Design (awarded rung from data we already hold)

## 0. Thesis

We already collect board minutes as `board_minutes` documents whose full text
sits in `documents.content` (Peel Police Services Board reports and Toronto
Police Services Board agendas). Buried in that text are award resolutions:
motions of the form "That the Board approve the award of RFP 2025-XX to
<vendor> in the amount of $<value>." Each one is an awarded-rung fact
(money committed on a named procurement) sitting in data we hold, behind no
scraping and no fragile portal tab.

This mines those resolutions into `award_notice` documents keyed on the
procurement reference number, so the awarded rung reconciles against the
in_market rung (the tender the award settles) on the same hard key the
demand-arc backtest already walks. It complements the portal collector rather
than replacing it: the portal gives the forward (in_market) signal, the minutes
give the settlement.

This is a design proposal. Nothing is collected or written until it is
approved, and the miner is not built until the validation probe in section 6
confirms the resolutions carry an extractable reference number.

## 1. Hard rules (non-negotiable, inherited)

1. **Provenance is the publisher.** The award fact's source is the board's own
   minutes PDF (already captured, already the `url` on the source document). No
   aggregator, no cross-sourcing.
2. **None beats a wrong answer.** If a resolution does not cite a procurement
   reference, we do not fabricate one. The award is still kept (it is real), but
   `reference_number` is null and it simply will not reconcile. We never invent
   a key to force a link.
3. **Keep-all with `defence_relevant` tagging.** Every award resolution is kept;
   police-facilities, security, and equipment awards are tagged, never dropped.
4. **Loud failure over silent empty.** A re-run over minutes known to contain
   awards that suddenly yields zero is a regression, not a quiet no-op (section
   5.4). The guard is calibrated to a measured baseline, not to a bare zero,
   because awards are sparse.
5. **content_hash dedup on the reference number.** Re-mining the same minutes
   must not duplicate an award.
6. **Canadian data residency preserved.** No new egress; this reads documents we
   already store.

## 2. Current state this builds on

- `board_minutes` documents exist with full text in `documents.content`
  (`src/board_minutes.py` collects them; a real extraction run has been done).
- `src/signal_extractor.py` already turns documents into signals against a
  constrained JSON schema, and already knows the `contract_award` signal_type
  (grade 5). Running it over `board_minutes` today can already surface award
  language as a signal.
- `src/taxonomy.py` floors `award_notice` documents at grade 5 (awarded) and
  grades the `contract_award` signal_type at 5.
- The procurement spine links tender to award on `documents.reference_number`.

The gap this closes: the generic extractor produces a *signal* but does not
populate `documents.reference_number`, so a minutes-derived award never lands on
the spine and never reconciles a prediction. Mining specifically pulls the
procurement reference out of the resolution and writes a `reference_number`.

## 3. What gets mined, and what it becomes

For each `board_minutes` document, the miner asks the LLM to find award
resolutions and, per resolution, extract a structured record:

| field | meaning | rule |
|-------|---------|------|
| `is_award` | this motion actually approves an award (vs recommends, defers, receives) | only `true` is emitted |
| `reference_number` | the procurement/RFP/tender number cited | null if not cited (never fabricated) |
| `vendor` | awarded supplier | null if not stated |
| `award_value` | dollar amount | null if not stated |
| `award_date` | the meeting/resolution date | falls back to the source doc's `published_on` |
| `title` | short description of what was awarded | required |

Each emitted award becomes a **net-new `award_notice` document** (not a mutation
of the minutes document):

- `doc_type = "award_notice"` -> taxonomy floors it at grade 5 (awarded).
- `reference_number` = the extracted procurement reference (the spine hard key,
  the link the demand-arc backtest walks). Null when not cited.
- `url` = the source minutes PDF url (honest provenance: the publisher of the
  award fact).
- `published_on` = the award/meeting date; `date_precision` honored (a
  month-only minute becomes "month").
- `defence_relevant` = `evaluate(...)` tag, keep-all.
- `content` = the resolution text (bounded), so the fact is auditable.
- `status = "captured"`, so the normal extractor then grades it at the award
  floor and it enters the corpus like any other document.

Keeping it as a document (not writing a signal directly) means the award flows
through the exact same insert -> extract -> grade -> reconcile path as a portal
award would, with no special-case code downstream.

## 4. content_hash and identity

`content_hash(reference_number or source_doc_id, "award_notice", vendor or "")`.

- Keyed on the reference number when present, so the same award seen in two
  minutes documents (e.g. a report and the ratifying agenda) dedupes.
- Falls back to the source document id when there is no reference, so a
  reference-less award still dedupes against itself on re-run without colliding
  with a different reference-less award.

## 5. The miner

### 5.1 Shape

`src/award_mining.py`, a `board_minutes` -> `award_notice` pass:

- reads `board_minutes` documents (batch, same `get_documents_by_status` path,
  filtered to `doc_type=board_minutes`);
- calls the LLM with a pinned award-resolution schema (section 3), reusing the
  extractor's constrained-JSON discipline;
- builds `award_notice` payloads (section 3), dedups on `content_hash`, inserts;
- `--dry-run` renders and reports, writes nothing (same convention as the
  portal collector).

It is **source-agnostic**: it runs over every `board_minutes` document
regardless of board, so TPSB, Peel, and any future board are covered with no
per-board code. That is the multiplier, mirroring the portal's `{org, subdomain}`
rows.

### 5.2 Prompt discipline

The prompt targets award *motions* specifically and is told the difference
between:

- **award** ("approve the award of", "be awarded to") -> emit;
- **recommendation / receipt / deferral** ("recommend", "receive for
  information", "defer") -> do not emit.

This distinction is the whole risk of prose mining, so it is pinned with
few-shot examples drawn from the validation probe (section 6) and locked by a
golden-set test before the miner runs for real.

### 5.3 Grade honesty

A board resolution *approving* an award is the award decision: money committed
on a named procurement -> grade 5 (awarded) is defensible. A resolution that
only *recommends* an award is not emitted at all (it would be, at most, a
commitment, and mislabelling it awarded is the "wrong answer" we refuse). The
`is_award` gate enforces this at extraction, not after.

### 5.4 Loud-failure guard, calibrated

Awards are sparse, so a bare "zero rows = fail" guard would cry wolf. Instead:

1. the validation probe (section 6) measures a baseline: awards found per N
   minutes documents across the existing corpus;
2. the guard fires when a full re-run over that same known-award-bearing corpus
   yields **zero** awards, which can only mean the extraction path broke. A
   partial drop is logged, not raised; a total collapse raises.

This keeps the loud-failure principle (silent-empty is the failure we most fear)
without a false alarm every quiet week.

## 6. Validation first (build gate)

Per the standing rule that we do not blind-build unvalidated prose mining, the
miner is gated on a probe that must run and be reviewed before any code lands:

1. **Pull real award-resolution text.** Over the already-collected
   `board_minutes` documents, extract and surface the passages that match award
   language ("award", "awarded to", "RFP", "RFQ", "Tender No"). Report: how many
   documents contain award motions, and paste representative resolutions
   verbatim.
2. **Answer the two questions that decide feasibility:**
   - Do the resolutions cite a procurement reference number, and in what format?
     (This decides whether the awarded rung can reconcile at all, or only
     accrues unlinkable awards.)
   - Are award motions cleanly distinguishable from recommendations and receipts
     in the actual prose? (This decides whether the `is_award` gate is reliable
     or noisy.)
3. **Only then** pin the prompt with real few-shot examples, write the golden
   set, and build `src/award_mining.py`.

If the probe shows the resolutions do NOT carry references (awards present but
unkeyable), we report that honestly and reconsider: the awarded rung from
minutes would then be corpus-only (kept, tagged, but non-reconciling), and the
portal's Method-B `?status=Awarded` endpoint becomes the path to a keyed awarded
rung instead. We do not build a reconciling miner on top of data that cannot
reconcile.

## 7. Why this is the robust awarded rung

- **No fragile scraping.** It reads documents we already hold; nothing depends
  on a portal's JS grid or a tab-switch that may not fire.
- **Same spine, same hard key.** Awards land on `reference_number`, so they
  reconcile against tenders with no new plumbing.
- **Complements, not competes.** Portal = forward (in_market); minutes =
  settlement (awarded). Together they close the in_market -> awarded arc for
  Peel that the portal alone (Open-only, per its own honesty scope) cannot.

## 8. Open questions for the operator

1. **Reference-less awards:** keep them as corpus-only `award_notice` documents
   (tagged, non-reconciling), or hold them out entirely until a reference can be
   linked? Default proposed: keep them (they are real awards; corpus honesty),
   flagged as unlinkable.
2. **Grade of a "recommend to award":** proposed to emit nothing (not even a
   commitment) to keep the awarded rung clean. Confirm, or should a strong
   recommendation enter as a grade-3 commitment signal?
3. **Guard baseline:** set the loud-failure floor from the probe's measured
   award count, or run permanently in log-only mode until the corpus is larger?

## 9. Probe findings (2026-07-14): validation ran, status changed

Three read-only probes ran against live data before building anything. They
overturned the section 0 premise and split the awarded rung by board. Nothing
was written to Supabase.

### 9.1 Peel Police Services Board minutes: NO procurement awards
Census: 100 `board_minutes` documents, all Peel, zero TPSB. Of the 100, only
2 had any procurement-context "award" passage, 0 cited a reference. The Peel
documents we hold are **annual reports** (medals, scholarships, service awards,
the odd grant received), not procurement-decision minutes. The premise that
Peel police-board minutes carry contract-award resolutions is FALSE for the
data we hold. Coverage flag: the Peel Police Services Board source is the wrong
document class for the awarded rung and should be revisited in the coverage
strategy.

### 9.2 Method-B `?status=Awarded`: VALIDATED as Peel's awarded rung
Replaying the captured, CSRF-authorized Search call with the status flipped (and
paging preserved) returns HTTP 200 JSON of genuinely awarded bids, disjoint from
the Open set, e.g. `"Title":"2017-695N - Provision of a Public Safety LTE
Broadband Data System","Status":"Awarded"` with dates and a Vendor field. The
reference format is identical to the Open tenders (`2017-695N`), so awarded rows
hard-key to the in_market rung by reference. This is the clean, reconciling
awarded rung for Peel. It supersedes minutes-mining for Peel.

### 9.3 TPSB: access restored, real awards, but minute-keyed (not tender-keyed)
The WAF 415 that parked TPSB on 2026-07-11 is GONE: plain requests (even the
`SignalNorthCollector/1.0` UA) now gets HTTP 200 on robots.txt and the listing;
88 agenda/minutes PDFs are reachable and extract cleanly. TPSB minutes DO carry
real contract-award motions with vendor and value, e.g. "Approve a contract
award to Olin Canada ULC for ammunition in the amount of $622,000", "contract
award to The Manufacturers Life Insurance Company ... $52.1 Million". 7 of 8
sampled PDFs had procurement-context awards; 6 had motions.

BUT those awards are identified by a **board minute number** (`P2023-0428-7.0`),
not a procurement RFP/tender reference, and TPSB has no in_market (tender) rung
in our spine to reconcile against. So per section 6's own test, TPSB awards are
**corpus-only** awarded signals (real, gradeable at the award floor, dedupable
on the minute number, taggable) but NOT hard-key reconcilable. Rich content,
wrong key for reconciliation.

### 9.4 Status: miner PARKED; awarded rung pivots per board
- **Peel awarded rung:** build on Method-B `?status=Awarded` (section 9.2).
  Validation-first spike passed; ready to build on approval.
- **TPSB:** unpark the `board_minutes` collector (flip `enabled` True; access is
  restored) for coverage. A TPSB award-signal extractor is viable as a
  corpus-only awarded feed keyed on the minute number, not as a reconciling
  hard-keyed rung.
- **This miner (as specified, hard-key via procurement reference):** PARKED. Its
  reconciling premise holds for neither board we probed (Peel police: no awards;
  TPSB: awards but no tender reference). Not killed: it is revivable for any
  future board whose minutes cite a procurement reference (open question 1 in
  section 8 governs the corpus-only variant).
