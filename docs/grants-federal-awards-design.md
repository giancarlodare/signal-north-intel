# Federal grant awards ingest — design proposal (NOT built)

**Status: awaiting operator approval.** Per instruction (2026-07-11), the
grant-award ingest is design-first: nothing below is implemented, and nothing
ingests until this design is approved. The program collectors
(`grants_ontario`, `grants_pscanada`) are independent and already built.

## What the source actually is (CI-probe-verified 2026-07-11)

The proactive-disclosure page every department links to (PS Canada's routes
to `search.open.canada.ca/grants/?owner_org=ps-sp`) is a search UI over ONE
consolidated dataset owned by TBS:

- Dataset: **Proactive Disclosure – Grants and Contributions**,
  `open.canada.ca/data/en/dataset/432527ab-7aac-45b5-81d6-7597107a7013`
- The consolidated CSV resource is **2.26 GB**
  (`…/resource/1d15a62f-5656-49ad-8c88-f40ce689d831/download/grants.csv`) —
  every department, every year, both languages of every text field.
- There is **no per-department CSV** (probe: package_search finds only the
  consolidated dataset plus unrelated provincial ones).
- The resource is loaded into CKAN's **datastore** (`datastore_active:
  true`), and the filtered API works:
  `GET /data/en/api/action/datastore_search?resource_id=1d15a62f-…&filters={"owner_org":"ps-sp"}`
  returned `success: true` with **3,476 total** ps-sp records. (The
  UNfiltered probe of the same endpoint timed out at 60s — filters are not
  optional at this table's size.)

Record fields (probe sample): `ref_number` (e.g. `GC-2017-Q3-00001`),
`amendment_number`, `amendment_date`, `agreement_type` (G/C),
`recipient_legal_name`, `recipient_operating_name`, `recipient_city/
province/country`, `prog_name_en`, `prog_purpose_en`, `agreement_title_en`,
`agreement_value`, `agreement_start_date`, `agreement_end_date`,
`description_en`, `expected_results_en`, `naics_identifier`, `owner_org`,
`owner_org_title`. Full schema: `open.canada.ca/data/recombinant-published-schema/grants.json`.

## Proposed design

**`src/grants_federal_awards.py`, weekly** (rides `weekly-discovery.yml`,
after the PS Canada programs step). Departments hardcoded, propose-then-
approve as always:

```python
DEPARTMENTS = ["ps-sp", "rcmp-grc", "dnd-mdn", "cbsa-asfc"]
```

1. **Fetch** per department via `datastore_search` with
   `filters={"owner_org": dept}`, `sort=agreement_start_date desc`,
   `limit=100` + offset paging. 2s polite delay between requests, same
   User-Agent as every collector.
2. **Stop early on known ground:** newest-first ordering + content_hash
   dedupe means a page whose records are ALL already stored ends that
   department's scan — steady-state weekly cost is one or two requests per
   department, regardless of history size.
3. **Identity:** `content_hash(ref_number, "grant_award",
   amendment_number)`. An amendment re-discloses the same `ref_number` with
   `amendment_number+1` — that is a real event (values change) and inserts
   as a fresh document; the unamended original stays.
4. **Document mapping** (`doc_type='grant_award'`):
   - `title`: `agreement_title_en` (fallback `prog_name_en`) + recipient
   - `published_on` = `agreement_start_date` (day precision); null when the
     record has none — never the disclosure quarter as a fake day.
   - `content`: structured text of the English fields (program, purpose,
     recipient + location, value, start/end, expected results, amendment
     info). French fields used only when the English field is empty.
   - keywords.txt runs **tag-only** (the department filter IS the scope);
     `defence_relevant` tagging still applies.
5. **Recency window for the first ingest:** records with
   `agreement_start_date >= 2024-04-01` (last two fiscal years), so the
   baseline is a few hundred extractor-bound docs, not ~15 years of history
   (ps-sp alone is 3,476 records back to 2016). Deeper backfill stays a
   separate operator decision. No value floor — sub-threshold awards being
   invisible to tender monitoring is the point.

## Open questions for the operator

1. **Record URL / provenance.** The datastore API is not a page a human can
   open. The search UI deep-links records (something like
   `search.open.canada.ca/grants/record/…`) — the exact format needs one
   build-phase probe. Options: (a) the record's search.open.canada.ca page
   (publisher-run UI over the publisher's dataset), or (b) the dataset landing
   page + `ref_number` in the title. Recommend (a) once verified.
   [Both are Government of Canada properties, so the provenance rule holds
   either way.]
2. **Departments beyond the minimum four?** (e.g. `csc-scc` Correctional
   Service, `jus` Justice.) Easy to add later; each is one config line.
3. **The 2024-04-01 window** — right cut, or deeper?
4. RCMP/DND/CBSA record counts weren't probed (only ps-sp). If DND turns out
   to be enormous even within the window, the per-run cap (25 new docs/dept,
   backlog pages through — the board-collector pattern) keeps extraction
   costs bounded. Proposed default: yes, cap at 25/dept/run.

## Rejected alternatives

- **Downloading grants.csv (2.26 GB) weekly and filtering locally** — wasteful
  and slow in CI; the datastore API serves the same rows filtered.
- **Scraping search.open.canada.ca result pages** — it's a JS search UI over
  the same data; the dataset API is the honest machine interface.
- **Unfiltered datastore scans** — probe-verified to time out.
