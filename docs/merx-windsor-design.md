# MERX-Ottawa and Windsor open-data tender collectors: design

Status: PROPOSED (design-first, approved targets 2026-07-20; structure
evidence from the read-only CI probe the same day, job 88502863474).

## 1. Scope

Two requests-based collectors on the CanadaBuys/board-minutes politeness
pattern (SignalNorthCollector UA, robots respected, 2s shared delay, loud
failure on empty). No Playwright, no accounts, no new schema.

| Target | Why | Provenance |
|---|---|---|
| opendata.citywindsor.ca/Tools/BidsAndTenders | City of Windsor bids incl. Windsor Police (WPS) items, with award results; structured open data beats scraping the Biddingo app | The city's own open-data catalogue: publisher-published by definition. robots.txt 404s (allow-all per RFC 9309) |
| merx.com/cityofottawa | City of Ottawa incl. Ottawa Police (OPS) procurement; four server-side tabs (Open, Closed, Bid Results, Awarded) | ottawa.ca links merx.com/cityofottawa, VERIFIED BY OPERATOR IN A HUMAN BROWSER 2026-07-20 (ottawa.ca WAF 403s our UA, so the chain is recorded here rather than machine-crawled). merx.com robots.txt explicitly allows "all well-behaved crawlers"; can_fetch True for the production UA, zero blocklist collisions |

## 2. Probe evidence the parsing rests on

Windsor (one server-side page, 352KB, no pagination; RSS alternative at
/RSS is banked, the HTML page is complete):

- 121 items, each: `PREFIX NN-YY, Title` then `Open: Jul 08, 2026 12:00 AM
  EST` / `Close: Aug 05, 2026 11:30 AM EST` (40 carry `(Extended)`), a
  tender-letter PDF at /Tools/DownloadTender/{GUID}, free-text description,
  and for 59 items a `View Unofficial Results` PDF (the award record).
- Prefix distribution: RFT 69, RFP 28, EOI 7, RFPQ 6. Reference shape
  `\d{1,3}-\d{2}` (e.g. 86-26, 25-26); the 2-digit year suffix is the
  bid year.

MERX-Ottawa (tab pages server-side, 25 items/page, `pageNumber=N` "Next"
pagination):

- Listing item URL carries the MERX id: `/solicitations/<tab>/<slug>/0000NNNNNN`.
- The abstract page (server-side, verified on 0000281771) exposes:
  Solicitation Type (`RFT - Request for Tender`), **Solicitation Number**
  (`19224-68051-T01`, Ottawa's own reference), Title (`OPS/Breaching
  Kits`), **Closing Date** (`2024/12/02 03:00:00 PM EST`), status text
  ("This solicitation is CLOSED"), contact, and Bid Results / Award tabs.

## 3. Collectors

### src/tenders_windsor.py (single-page parse)

- Fetch the one page; parse per-item blocks from the DOM. Emit per item a
  `tender_notice`: reference_number = `NN-YY` (prefix stored in title),
  published_on = CLOSE date (day precision; the `(Extended)` close is the
  current truth and refreshes in place, CanadaBuys-amendment style),
  url = the tender-letter PDF (the publisher artifact; listing URL as
  fallback when absent), content = the item's description text,
  buyer_name = "City of Windsor".
- Items with `View Unofficial Results` additionally emit an `award_notice`
  keyed on the same reference (content_hash includes doc_type + status so
  the lifecycle inserts fresh), url = the results PDF. No award date is
  published; published_on stays the close date (same convention as the
  bids&tenders awarded rung; never fabricate).
- LOUD FAILURE: 0 parsed items raises (the page always carries a year-plus
  of activity).

### src/tenders_merx.py (tab enumeration + per-item abstract)

- Stage 1: page through `open-bids` and `awarded-bids` (and `bidresults-bids`
  for award documents) via `pageNumber=N` until no Next; collect MERX ids.
- Stage 2: for each id NOT already in the corpus (content_hash check
  first, so the steady state fetches only new items), fetch the abstract
  and parse Solicitation Number, Title, Closing Date, Type, status.
  reference_number = the Ottawa Solicitation Number (the hard key Ottawa
  itself uses); the MERX id rides in the URL. published_on = closing date
  (day). buyer_name = "City of Ottawa" (already in ORG_SEED).
- Per-run NEW-item cap (25, board-minutes style) drains the awarded
  backlog politely over days; a bound of 1000 caps the initial history.
- LOUD FAILURE: open-bids page 1 with 0 solicitation links raises;
  abstract parse failures count toward an error budget (25) then raise.

## 4. Sources, orgs, tagging

- Sources migration: two URL-key-guarded rows (the Windsor endpoint URL
  and merx.com/cityofottawa), gov_website/municipal/scraper/daily.
- ORG_SEED: add City of Windsor (municipality, ON). City of Ottawa exists.
- defence_relevant tagging (keep-all unchanged): add the police service
  acronyms the probes surfaced to the defence keyword list: WPS (Windsor
  Police Service items title as "WPS ..."), OPS (Ottawa lists police items
  under EPS/OPS/). Without them, "92-26 WPS Collision Repair" tags
  non-defence because the word "police" never appears.

## 5. Validation before enablement (tier-1 bars)

CI dry-run per collector before the migration applies and the build PR
merges, VALIDATION log line per collector:

- Windsor: >= 90% of items parse reference AND close date; >= 40 items
  (order of magnitude of the probe's 121); unofficial-results docs
  nonzero.
- MERX: >= 90% of sampled abstracts parse Solicitation Number AND Closing
  Date; open tab nonzero; awarded tab nonzero.
- Below the bar: diagnose and extend before enabling, never enable-and-hope.

## 6. Scheduling

Both are light requests collectors: two new steps in daily-collect (no
Chromium), after board_minutes, sharing the politeness pattern. Windsor is
1 fetch + ~0 new-item fetches steady state; MERX is ~4-8 listing pages +
only NEW abstracts (a few/day steady state, capped 25 during backfill).

## 7. Banked, not built

- Biddingo platform (JS app, /m/ buyer pages client-rendered) joins the
  render-capable evaluation alongside eScribe (docs/big12-boards-design.md
  section 10). Windsor's open-data mirror makes Biddingo unnecessary for
  Windsor. biddingo.com/m/drps CONFIRMED PUBLIC by operator browser
  2026-07-20 ("Doing Business with Durham Regional Police Service", 38
  bids, no sign-in, DRPS-2026-002-style references, Awarded/Closed
  statuses incl. an awarded vehicle towing and storage contract); the
  requests probe's empty page was client-side rendering, not a soft-404.
  DRPS is therefore the evaluation's highest-value target: a police
  service's full public bid history with awards. Evaluation stays banked;
  probe-only holds.
- Ottawa Quotations Portal (under-$100K standing offers, ottawa.ca):
  secondary, banked per operator instruction.
- opendata.citywindsor.ca/RSS: alternative feed if the HTML page ever
  degrades.
- MERX other-buyers slug search (cityofwindsor and cityofgreatersudbury
  confirmed to exist) waits until these two collectors are proven.

## 8. Infrastructure Ontario as a MERX buyer target (PARKED 2026-07-21, provenance not established)

Operator discovery: merx.com/infrastructureontario is a public MERX buyer
page carrying OPP procurement, notably "PDC for Ontario Provincial Police
Modernization Phase Three" (MERX id 0000261577). This is the first public,
collectable surface for OPP-related buying: the provincial arc runs through
IO for facilities, and the Ontario Tenders Portal itself is closed to
automation (see the ROADMAP OPP entry: Jaggaer host, robots Disallow /esop).

CI probe (2026-07-21, job 88525460550), read-only:

- Tab structure IDENTICAL to Ottawa's and parses with the existing
  tenders_merx functions unchanged: open-bids 4 ids, awarded-bids 50+ ids
  across 2+ pages (the OPP Modernization item sits on awarded page 2, with
  another OPP item, "Architectural Design Services for Project Connect -
  OPP Comp...", beside it), bidresults-bids 4 ids. Pagination behaves; the
  merx:{id} hash namespace is buyer-agnostic because MERX ids are
  platform-global.
- Abstract caveat: IO's solicitation numbers use a different shape
  (24-1432, not Ottawa's NNNNN-NNNNN-LNN), and only 1 of 3 sampled
  abstracts carried the labeled field; the Ottawa page-title fallback will
  not match IO's shape. Enabling IO therefore needs its OWN validation
  round against the 90% bars, likely a small per-buyer reference-shape
  extension.
- PROVENANCE NOT ESTABLISHED, checked BOTH ways (recorded like the DRPS
  bids&tenders park): the machine crawl of infrastructureontario.ca
  (homepage + /en/partner-with-us/procurement/) found zero links to MERX,
  and the OPERATOR'S HUMAN BROWSE of infrastructureontario.ca including
  the procurement pages (2026-07-21) could not clearly find a link to the
  MERX buyer page either. A branded public buyer page is strong evidence
  but does not qualify; IO is PARKED pending provenance.

Two revival paths, banked:

1. A deeper targeted crawl of IO's site on a quiet day: the link may live
   on a project-specific or vendor-resources page both checks missed.
2. The data.ontario.ca probe for an OTP open dataset (see the ROADMAP OPP
   entry), which would cover provincial procurement including OPP
   regardless of the IO question.

Build shape if provenance ever passes: parameterize tenders_merx by buyer
config rows ({slug, buyer_name, source_url, reference shapes}), one sources
migration row, Infrastructure Ontario (crown_corp) + Ontario Provincial
Police in ORG_SEED, then the validation dry-run before enablement.
