# Big 12 police board minutes: phase 2 design

Status: PROPOSED (probe results delivered and reviewed 2026-07-20; phase 2
approved for the five passing boards; the Ottawa timeboxed check ran the same
day and parked it, see verdicts below).

## 1. Scope and strategic frame

Where tenders hide under municipal buyers, board minutes are pure police
signal: budget approvals, contract-award resolutions, technology items. The
`src/board_minutes.py` collector is source-agnostic config rows, so this
phase is discovery + configuration, not new collection code. One bounded
parser extension (date formats, section 6) is the only code change beyond
config, mirroring the tier-1 tenders precedent where validation surfaced a
format divergence and the parser was extended before enablement.

Enabled by this design (all passed the four-pass CI probe: publisher-linked
provenance, fetchable with the production PoliteFetcher, robots respected,
text PDFs confirmed by extraction):

| Board | Listing | Volume | Note |
|---|---|---|---|
| York Regional Police Services Board | yrpsb.ca | ~230 (2017+) | minutes + merged agenda packages |
| Durham Regional Police Services Board | durhampoliceboard.ca | ~174 | archive page back to ~2021 |
| Halton Police Board | haltonpoliceboard.ca | ~30 | AGENDAS ONLY: minutes are .docx (skipped by design); the agenda meeting books carry the staff reports, which is the signal |
| Waterloo Regional Police Services Board | wrps.on.ca | ~15 current | archive path 403s (recorded); current meetings collectible |
| Greater Sudbury Police Services Board | gsps.ca | ~206 | agendas + minutes + media releases |

Backfill is FULL DEPTH, no cutoff (operator call: nine years of board history
is backtest fuel worth the one-time cost; see section 9).

## 2. Config rows (BOARDS entries in src/board_minutes.py)

Same shape as the existing TPSB and Peel entries. Exact values from the
probes:

```python
{
    "name": "York Regional Police Services Board",
    "source_name_candidates": [
        "York Regional Police Services Board - Meetings",
        "York Regional Police Services Board", "YRPSB"],
    "source_id_env": "YRPSB_SOURCE_ID",
    "listing_urls": ["https://www.yrpsb.ca/meetings",
                     "https://www.yrpsb.ca/meetings-archives"],
    # The archives page links per-year pages /meetings-archives-2017..2025
    # (~25-27 docs each). One-level expansion reaches them all; the per-year
    # links are plain-http URLs on the same host, which expansion accepts.
    "listing_expand_prefixes": ["/meetings-archives-"],
    "doc_url_patterns": [r"/usercontent/.+\.pdf$"],
},
{
    "name": "Durham Regional Police Services Board",
    "source_name_candidates": [
        "Durham Regional Police Services Board - Meetings",
        "Durham Regional Police Services Board",
        "Durham Region Police Services Board", "DRPSB"],
    "source_id_env": "DRPSB_SOURCE_ID",
    "listing_urls": [
        "https://durhampoliceboard.ca/archived-board-meetings-agendas-and-minutes/",
        "https://durhampoliceboard.ca/"],
    # 174 candidate documents on the archive page alone. Some documents live
    # on reports.drps.ca; off-host PDFs are already allowed by
    # find_document_links when the path ends .pdf.
    "doc_url_patterns": [r"/upload_files/.+\.pdf$"],
},
{
    "name": "Halton Police Board",
    "source_name_candidates": [
        "Halton Police Board - Meetings",
        "Halton Police Board", "Halton Regional Police Services Board"],
    "source_id_env": "HALTON_PB_SOURCE_ID",
    "listing_urls": ["https://haltonpoliceboard.ca/meetings/"],
    # WordPress: /meetings/ lists per-meeting pages (/meetings/june-25-2026/)
    # carrying "Download Agenda" links. Minutes are .docx and are skipped by
    # BINARY_DOC_EXT (recorded limitation, approved: the agenda meeting
    # books, 46-138pp text PDFs, carry the full staff reports).
    "listing_expand_prefixes": ["/meetings/"],
    # One observed agenda URL lacks a .pdf suffix, so the pattern does not
    # require the extension; office binaries are excluded upstream.
    "doc_url_patterns": [r"/wp-content/uploads/.+"],
},
{
    "name": "Waterloo Regional Police Services Board",
    "source_name_candidates": [
        "Waterloo Regional Police Services Board - Meetings",
        "Waterloo Regional Police Services Board",
        "Waterloo Regional Police Service Board", "WRPSB"],
    "source_id_env": "WRPSB_SOURCE_ID",
    "listing_urls": ["https://www.wrps.on.ca/police-service-board-meetings"],
    # Per-meeting /resource/ pages each link one PDF in the service's own S3
    # bucket (wrps-public.s3.ca-central-1.amazonaws.com). Those are off-host
    # PDFs with agenda-named text/URLs, caught by the generic name pattern;
    # no extra doc_url_patterns needed. The meetings-archive path 403s
    # through a wrps.ca redirect (recorded); current listing only.
    "listing_expand_prefixes": ["/resource/"],
},
{
    "name": "Greater Sudbury Police Services Board",
    "source_name_candidates": [
        "Greater Sudbury Police Services Board - Meetings",
        "Greater Sudbury Police Services Board",
        "Greater Sudbury Police Service Board", "GSPSB"],
    "source_id_env": "GSPSB_SOURCE_ID",
    "listing_urls": [
        "https://www.gsps.ca/about-gsps/greater-sudbury-police-service-board/board-meetings/"],
    "doc_url_patterns": [r"/media/.+"],
},
```

Board naming note: the CSPA (2024) renamed many "Police Services Boards" to
"Police Service Boards" and some brands differ from statute (haltonpoliceboard.ca
brands as "Halton Police Board"). Canonical names above follow each board's
own current branding; both spellings ride along as aliases in ORG_SEED so
extraction resolves either. The validation dry-run (section 8) is the check
that the configured names match what the documents actually say.

## 3. Parked boards, recorded in BOARDS (enabled: False)

Same parking pattern as the DRPS tenders row: the verdict travels with the
config so revival is a flag flip plus a re-probe, not archaeology.

```python
# PARKED (probe 2026-07-20, four passes; see docs/big12-boards-design.md):
# {"name": "Hamilton Police Service Board", "enabled": False,
#  "parked_reason": "hamiltonpsb.ca agendas-and-materials listing is "
#     "JS-rendered (Umbraco); zero server-side documents. Revive via the "
#     "banked render-capable collection evaluation."},
# {"name": "Niagara Regional Police Service Board", "enabled": False,
#  "parked_reason": "documents live on pub-niagarapolice.escribemeetings.com "
#     "(eScribe JS shell, 4 links in raw HTML). Revive via eScribe adapter."},
# {"name": "London Police Service Board", "enabled": False,
#  "parked_reason": "no meeting documents server-side anywhere; "
#     "calendar.londonpolice.ca exposes events only; londonpoliceboard.ca "
#     "does not resolve. Revive via a targeted re-probe of a board-meeting "
#     "calendar detail page."},
# {"name": "Windsor Police Service Board", "enabled": False,
#  "parked_reason": "windsorpolice.ca/about/wps-board carries zero document "
#     "links; minutes presumably with the city clerk (citywindsor.ca) but "
#     "not publisher-linked from the board page. Provenance not established."},
# {"name": "Ottawa Police Services Board", "enabled": False,
#  "parked_reason": "timeboxed check 2026-07-20: ottawapoliceboard.ca "
#     "per-year meetings pages (2011-2025) link every per-meeting agenda to "
#     "pub-ottawa.escribemeetings.com Meeting.aspx (eScribe). Parked per the "
#     "one-probe rule. Revive via eScribe adapter."},
```

## 4. ORG_SEED additions (src/resolve_orgs.py)

Every enabled board AND its police service resolves canonically from day
one. Boards use the accepted `police_board` org_type; services use
`police_service`; all municipal/ON. York Regional Police is already seeded
(tier 1); only its board is added.

| Canonical name | org_type | Key aliases |
|---|---|---|
| York Regional Police Services Board | police_board | YRPSB, York Region Police Services Board, York Regional Police Service Board |
| Durham Regional Police Services Board | police_board | DRPSB, Durham Region Police Services Board, Durham Regional Police Service Board |
| Halton Police Board | police_board | Halton Regional Police Services Board, Halton Police Services Board |
| Waterloo Regional Police Services Board | police_board | WRPSB, Waterloo Regional Police Service Board |
| Greater Sudbury Police Services Board | police_board | GSPSB, Greater Sudbury Police Service Board |
| Durham Regional Police Service | police_service | DRPS, Durham Regional Police |
| Halton Regional Police Service | police_service | HRPS, Halton Police, Halton Regional Police |
| Waterloo Regional Police Service | police_service | WRPS, Waterloo Regional Police |
| Greater Sudbury Police Service | police_service | GSPS, Greater Sudbury Police |

Parked boards' orgs are NOT seeded now; they arrive with their unparking PR
so the seed never references a source that does not exist.

## 5. Sources seed migration

`migrations/<date>_big12_boards_source_seed.sql`, same URL-key-guarded shape
as the tier-1 tenders seed: five rows, `name` = the board's primary
source_name_candidate, `url` = the primary listing URL, source_type
`gov_website`, jurisdiction `municipal`, collector `scraper`, cadence
`daily`. Idempotent, re-runnable, parked boards deliberately absent.

## 6. Date-format parser extension (the one code change)

The probes surfaced three date shapes `guess_meeting_date` cannot parse,
all in filenames (link text is often just "View" or "Download Agenda"):

| Shape | Example (observed) | Board |
|---|---|---|
| Underscore-separated day-first | `19_JAN_2021_AGENDA_...` | Durham |
| Hyphen-separated month-first | `...-meeting-june-25-2026-...` | Halton |
| Compact day-first | `gspsb-agenda-public_28jan2026.pdf` | Sudbury |

Extension: generalize the month-name patterns' separator class from `\s` to
`[-_\s]` and add a compact `(\d{1,2})(mon)(20\d{2})` day-first pattern. The
listing-context capture remains the first fallback and "None beats a wrong
date" is unchanged: nothing is fabricated, unparseable stays NULL. Each
observed filename above becomes a unit test; existing TPSB/Peel test vectors
must stay green (regression guard).

## 7. Scheduling and stagger

board_minutes runs inside daily-collect (6:17am America/Toronto), sequential
with one shared 2s politeness delay; daily-tenders is separate at :47, so no
contention. Going from 2 to 7 boards:

- Backfill window (~10 days): per-run cap stays MAX_DOCS_PER_BOARD = 25, so
  a full run adds at most 5 x 25 documents ≈ +10-12 minutes of polite
  fetching. The cap counts NEW documents, so the multi-year archives (York
  ~230, Sudbury ~206, Durham ~174) drain over roughly ten daily runs.
- Steady state: ~12-13 new documents/month across all five, a couple of
  minutes per run.

No new workflow and no cron change needed; the sequential-in-one-process
pattern is the stagger.

## 8. Validation before enablement (same bar discipline as tier 1)

From CI, `python -m src.board_minutes --dry-run` with the new rows, before
the migration is applied and before the build PR merges:

- every enabled board lists real minutes/agenda candidates (nonzero, in the
  right order of magnitude vs the probe volumes);
- sampled bodies extract nonzero chars (text, not scan);
- dates parse to day or month precision on >= 90% of listed candidates
  (the parser-extension test in the wild); below the bar means diagnose and
  extend before enabling, never enable-and-hope;
- a board with zero candidates fails that board loudly (existing failures
  list turns the run red naming the board).

Enablement order after approval: apply migration, merge build PR, run
resolve_orgs once for the new orgs, then the next daily-collect begins the
backfill.

## 9. Extraction cost (restated from phase 1)

Opus 4.8 at $5/M input, $25/M output; bodies capped at 60k chars.

- One-time full-depth backfill: ~655 documents ≈ $50-90, dominated by
  merged agenda packages at the body cap; spread over ~10 days by the
  per-run cap.
- Steady state: ~12-13 documents/month ≈ $1-2/month.

## 10. Banked, not built: render-capable collection (Wave 2-later)

Four boards are parked behind JS-rendered listings. Two are confirmed
eScribe tenants (Niagara: pub-niagarapolice.escribemeetings.com; Ottawa:
pub-ottawa.escribemeetings.com, confirmed by the 2026-07-20 timeboxed
check). Hamilton is Umbraco with a JS agendas listing; London is a
CivicPlus-style calendar with no documents surfaced server-side.

The banked evaluation: one render-capable collection build. An
eScribe-specific adapter (replaying the portal's Meeting.aspx/document
endpoints, or a headless render like the bids&tenders adapter) certainly
unlocks Niagara + Ottawa; whether the same build covers Hamilton and London
depends on their platforms and is part of the evaluation. This is where the
render-service question genuinely applies. Explicitly out of scope for
phase 2; nothing in this design depends on it.
