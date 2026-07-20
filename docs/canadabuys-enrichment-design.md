# CanadaBuys tender enrichment design (Wave 2)

Status: DESIGN for approval, 2026-07-20. Supersedes the banked pre-design
notes (2026-07-19); the banked UNSPSC requirements are folded in below.
Code follows in a separate PR after approval.

## The headline finding: a parsing change, not a collection change

Probed the live open-data CSV from CI on 2026-07-20 (the exact file the
daily collector already downloads,
`newTenderNotice-nouvelAvisAppelOffres.csv`). **Every field we want is
already in it.** No scraping, no per-notice fetches, no new source:

| Wanted | CSV column (verified live) | Sample value |
|---|---|---|
| Close date | `tenderClosingDate-appelOffresDateCloture` | `2026-07-27T23:59:00` |
| Buyer | `contractingEntityName-nomEntitContractante-eng` | `Department of National Defence (DND)` |
| Reference | `solicitationNumber-numeroSollicitation` | `W6399-27-TR05` |
| Description | `tenderDescription-descriptionAppelOffres-eng` | full paragraph text |
| UNSPSC codes | `unspsc` (+ `unspscDescription-eng`) | `*25132100\n*72151600` (multi-code) |

Also present and useful: `amendmentNumber`/`amendmentDate` (notice
versioning), `tenderStatus` (Open/...), `expectedContractStartDate`/
`EndDate`, `noticeType`, `procurementMethod`, regions, GSIN, and the
CanadaBuys row id `referenceNumber` (`cb-126-...`) we already use for URLs.

Today `process_tender_notices` PARSES description, reference, and unspsc
for keyword filtering, then discards them at insert, storing only title,
URL, publication date, and the defence flag. Enrichment for new documents
is therefore: stop discarding.

## A defect this design fixes: the federal tender event date is wrong

`published_on` for federal tenders is currently the PUBLICATION date. But
the editorial model treats a tender's event date as its CLOSE date: the
brief renders `tender_notice` dates as "Tender closes ..." / "Bids
closed ..." (date-label section 7.4), the timing window classes tenders as
imminent by a future published_on, and Peel tenders already store the close
date. Consequences today: a federal tender can NEVER be imminent (its
publication date is always in the past), and any federal tender that
reaches the brief shows "Bids closed <publication date>", which is false.

**Proposal: `published_on` = the close date (date part) for federal
tender_notice documents**, aligning them with Peel and with every reader-
facing label. The publication date is preserved inside the content header
(below). This follows the standing event-date discipline: the close date
IS the tender's event.

## Storage mapping (documents table)

| Column | Source | Notes |
|---|---|---|
| `title` | `title-titre-eng` | unchanged |
| `published_on` | `tenderClosingDate` date part | THE FIX above; `date_precision='day'` |
| `reference_number` | `solicitationNumber` | column exists (2026-07-13 migration); the procurement spine hard key, same semantics as federal contracts and the proposer |
| `content` | structured header + `tenderDescription-eng` | existing column; gives extraction a real body |
| `unspsc_codes` | `unspsc`, parsed | NEW column, `text[]` (below) |
| `buyer_name` | `contractingEntityName-eng` (falling back to `endUserEntitiesName-eng` when the contracting entity is a shared-services buyer and the end user is present) | NEW column, raw as published; resolution to canonical orgs stays downstream |
| `url` | unchanged template on `referenceNumber` | |

The content header is a short labeled block ahead of the description so the
extractor and any human reader see the structured facts in one place:
solicitation number, buyer, publication date, close date, status, notice
type, procurement method, expected contract start/end, regions, UNSPSC
codes with their English descriptions. Facts only, no invented text; empty
fields omitted.

### New columns (one small migration)

- `documents.unspsc_codes text[]` with a GIN index. Array because a tender
  lists several codes (the live sample carries two). Text, not integer:
  codes are fixed-width identifiers with meaningful leading zeros.
- `documents.buyer_name text`. Raw buyer string for deterministic org
  resolution and reporting; NULL where a source has no structured buyer.
  Nothing may assume it is set (municipal and RSS sources leave it NULL).

### UNSPSC normalization (banked requirements honored)

- Split the CSV value on `*`, trim, keep values matching `^\d{8}$`,
  de-duplicate preserving order. Store full 8-digit codes only.
- Segment rollup (first 2 digits) stays DERIVED at query time, never
  stored, per the banked decision.
- Signals do not get a codes column; they join through the document. The
  three payoffs (watchlist backbone, factual "who bids" basis, backtest
  category spine) all read document-side.
- Municipal fallback unchanged: bids&tenders publishes no UNSPSC; keyword
  tagging remains, and no schema or query may assume codes exist.

## Amendments: refresh in place, never duplicate

CanadaBuys re-publishes a notice on amendment (`amendmentNumber` 001+,
`amendmentDate` set) - and amendments routinely change the CLOSE DATE,
which is now our event date. Proposal:

- Dedup key stays the notice (`content_hash` on `referenceNumber`, as
  today) so one solicitation = one document.
- When a row arrives whose hash matches an existing tender document AND
  carries a higher amendment number, the collector REFRESHES that document
  in place: close date, status, content, codes. The header notes the
  amendment number and date.
- This is a correction of the same published notice (the portal itself
  shows one amended notice), not a deletion of history; keep-all applies to
  documents, and the notice's latest truth is what the brief must carry. A
  stale close date on a live tender is a wrong date shown to a reader.

## Backfill of the existing title-only stock

The daily file contains only NEW notices (6 rows on probe day), so it
cannot backfill the existing title-only federal tender documents. Proposal:

- One-time (and optionally weekly) pass against CanadaBuys' complete
  open-tenders CSV (the `tenderNotice-avisAppelOffres.csv` companion file;
  exact URL verified by probe at build time, same open-data directory).
- Match existing `tender_notice` documents by the `referenceNumber`
  embedded in their URL; fill content, close date, codes, buyer,
  reference_number. Idempotent, additive, manual workflow_dispatch with a
  dry-run default (same pattern as relink-vendors).
- Notices no longer in the open file (closed since collection) stay
  title-only and age out of the brief window naturally; the backfill run
  reports how many it filled and how many it could not, honestly.

## Downstream effects (why this is the Wave 2 opener)

1. **Dedup and the procurement spine**: `reference_number` on federal
   tenders makes tender-award clustering a genuine hard key end to end
   (proposer already reads the column).
2. **The brief's federal tender items become real action items**: correct
   "Tender closes <future date>" labels, eligible for the imminent window
   and the lens, with buyer_name reducing unresolved-buyer degradation.
3. **Extraction quality**: the extractor sees a real body instead of a
   title, which should lift confidence and materiality fidelity (the
   calibration audit will show it; the prompt already warns about
   title-only input).
4. **UNSPSC becomes queryable**: watchlist filtering by code prefix, the
   factual "who plausibly bids" read, and the backtest category spine all
   get their structured field. (Consuming it in brief_copy and watchlists
   is follow-up work, not this PR.)

## What this design does NOT do

- No scraping and no per-notice page fetches; CSVs only.
- No attachments download.
- No change to signals schema; codes and buyer join through documents.
- No watchlist matching semantics (decided with the subscriber design).
- No municipal UNSPSC; keyword fallback stays.
- No LLM involvement anywhere; the whole change is deterministic parsing.

## Implementation plan (one build PR after approval)

1. Migration `documents_unspsc_buyer.sql`: `unspsc_codes text[]` + GIN
   index, `buyer_name text`, comments.
2. `src/canadabuys.py`: `parse_unspsc_codes()` helper (pure, tested).
3. `src/main.py process_tender_notices`: build the content header, store
   the five fields, close-date-as-event-date, amendment refresh.
4. `src/backfill_tender_details.py` + manual workflow (dry-run default).
5. Tests: unspsc parsing (multi-code, malformed, empty), event-date
   mapping, amendment refresh vs duplicate insert, header assembly,
   backfill matching; CSV fixtures use the probed real column names.

Cost: zero new network calls on the daily path (same file), zero LLM cost.
The backfill is one extra CSV download per run.
